"""GET /lesson/{concept_id} (SSE micro-lesson + analogy + socratic), GET /hint/{question_id}."""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai import generators
from app.api.deps import get_db, graph_dep, require_student, sse, trace_id
from app.config import get_settings
from app.core.adaptive import bloom_target
from app.core.graph import ContentGraph
from app.core.student_state import load_attempts, load_rows
from app.db import models as m
from app.schemas.api import HintResponse, LessonPayload
from app.schemas.common import BLOOM_ORDER

router = APIRouter(tags=["tutor"])


def schedule_mastery_checks(db: Session, student_id: str, concept_id: str, misconception_id: str | None,
                            graph: ContentGraph) -> list[str]:
    """Remediation check (§9.4.3): 2 questions on the concept, one Bloom level higher than where they slipped."""
    s = get_settings()
    pending = db.scalars(
        select(m.ScheduledItem).where(
            m.ScheduledItem.student_id == student_id, m.ScheduledItem.kind == "remediation",
            m.ScheduledItem.concept_id == concept_id, m.ScheduledItem.status == "pending",
        )
    ).all()
    if pending:
        return [it.question_id for it in pending if it.question_id]

    attempts = load_attempts(db, student_id)
    on_concept = [a for a in attempts if a.concept_id == concept_id]
    failed = [a for a in on_concept if not a.is_correct]
    if failed and failed[-1].question_id in graph.questions:
        base = graph.questions[failed[-1].question_id].bloom_index
    else:
        levels = [graph.questions[q].bloom_index for q in graph.questions_by_concept.get(concept_id, [])]
        tuples = [(a.is_correct, a.confidence, graph.questions[a.question_id].bloom_index) for a in on_concept
                  if a.question_id in graph.questions]
        base, _ = bloom_target(tuples, levels)
    target = min(base + 1, len(BLOOM_ORDER) - 1)
    recent = {a.question_id for a in attempts[-s.recent_window :]}
    last_failed = failed[-1].question_id if failed else None
    qs = [graph.questions[q] for q in graph.questions_by_concept.get(concept_id, []) if q != last_failed]
    fresh = [q for q in qs if q.id not in recent] or qs

    def key(q):
        targeted = 0 if (misconception_id and misconception_id in q.targets) else 1
        below = 1 if q.bloom_index < target else 0
        return (below, abs(q.bloom_index - target), targeted, q.b)

    chosen = sorted(fresh, key=key)[:2]
    for i, q in enumerate(chosen, 1):
        db.add(m.ScheduledItem(
            student_id=student_id, kind="remediation", concept_id=concept_id, misconception_id=misconception_id,
            min_bloom=BLOOM_ORDER[target], question_id=q.id,
            reason=f"Mastery check {i}/{len(chosen)} on {graph.name(concept_id)}: one Bloom level up "
                   f"('{q.bloom_level}') from where you slipped.",
        ))
    db.flush()
    return [q.id for q in chosen]


def _chunks(text: str, words_per_chunk: int = 3):
    parts = text.split(" ")
    for i in range(0, len(parts), words_per_chunk):
        yield " ".join(parts[i : i + words_per_chunk]) + (" " if i + words_per_chunk < len(parts) else "")


@router.get("/lesson/{concept_id}", response_class=StreamingResponse,
            responses={200: {"model": LessonPayload, "content": {"text/event-stream": {}},
                             "description": "SSE: meta, delta*, lesson (LessonPayload), done"}})
def lesson(
    concept_id: str,
    student_id: str = Query(...),
    misconception_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    graph: ContentGraph = Depends(graph_dep),
    tid: str = Depends(trace_id),
) -> StreamingResponse:
    require_student(db, student_id)
    if concept_id not in graph.concepts:
        raise HTTPException(404, "unknown concept")
    rows = load_rows(db, student_id, graph)
    if misconception_id not in graph.misconceptions:
        active = rows[concept_id].active_misconception_ids or []
        misconception_id = active[0] if active else None
    check_ids = schedule_mastery_checks(db, student_id, concept_id, misconception_id, graph)
    attempts = load_attempts(db, student_id)
    db.commit()

    do_not_reveal = []
    for qid in [*check_ids, *(a.question_id for a in attempts[-1:])]:
        q = graph.questions.get(qid)
        if q and q.correct_option:
            do_not_reveal.append(q.correct_option.text)
    mc = graph.misconceptions.get(misconception_id or "")
    delay = get_settings().lesson_stream_delay_ms / 1000

    def gen():
        yield sse("meta", {
            "trace_id": tid, "concept_id": concept_id, "concept_name": graph.name(concept_id),
            "misconception_id": misconception_id, "misconception_text": mc.description if mc else None,
            "correct_belief": mc.correct_belief if mc else None, "replay_id": mc.replay_id if mc else None,
        })
        body, analogy, socratic, source = generators.micro_lesson(
            graph, concept_id, misconception_id, do_not_reveal, tid, student_id
        )
        for chunk in _chunks(body.lesson_md):
            yield sse("delta", {"text": chunk})
            if delay:
                time.sleep(delay)
        payload = LessonPayload(
            concept_id=concept_id, concept_name=graph.name(concept_id), misconception_id=misconception_id,
            lesson_md=body.lesson_md, worked_example=body.worked_example, analogy=analogy.analogy,
            socratic_questions=socratic.questions, citations=body.citations, mastery_check_question_ids=check_ids,
            replay_id=mc.replay_id if (mc and get_settings().flag_replay) else None, source=source,
        )
        yield sse("lesson", payload)
        yield sse("done", {"trace_id": tid})

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "x-trace-id": tid})


@router.get("/hint/{question_id}", response_model=HintResponse)
def get_hint(
    question_id: str,
    level: int = Query(default=1, ge=1, le=3),
    student_id: str | None = Query(default=None),
    graph: ContentGraph = Depends(graph_dep),
    tid: str = Depends(trace_id),
) -> HintResponse:
    if not get_settings().flag_hints:
        raise HTTPException(404, "hints disabled")
    if question_id not in graph.questions:
        raise HTTPException(404, "unknown question")
    text = generators.hint(graph, question_id, level, tid, student_id)
    return HintResponse(trace_id=tid, question_id=question_id, level=level, hint=text, xp_cost=get_settings().xp_hint_cost)
