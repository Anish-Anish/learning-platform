"""POST /teach/{concept_id} (SSE bot reply), POST /teach/{session_id}/score."""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai import teach_bot
from app.api.deps import get_db, graph_dep, require_student, sse, trace_id
from app.config import get_settings
from app.core import gamification as gam
from app.core.graph import ContentGraph
from app.db import models as m
from app.db.session import SessionLocal
from app.guardrails.budget import rate_limited
from app.guardrails.input import check_free_text
from app.schemas.api import TeachMessageRequest, TeachScoreResponse, TeachTurnDone

router = APIRouter(tags=["teach"])


@router.post("/teach/{concept_id}", response_class=StreamingResponse,
             responses={200: {"model": TeachTurnDone, "content": {"text/event-stream": {}},
                              "description": "SSE: session, delta*, done (TeachTurnDone)"}})
def teach_message(
    concept_id: str,
    body: TeachMessageRequest,
    db: Session = Depends(get_db),
    graph: ContentGraph = Depends(graph_dep),
    tid: str = Depends(trace_id),
) -> StreamingResponse:
    s = get_settings()
    if not s.flag_teach_bot:
        raise HTTPException(404, "teach-the-bot disabled")
    student = require_student(db, body.student_id)
    if concept_id not in graph.concepts:
        raise HTTPException(404, "unknown concept")
    if rate_limited(f"teach:{student.id}"):
        raise HTTPException(429, "Slow down a little. Byte needs a moment to think!")

    sess = db.get(m.TeachSession, body.session_id) if body.session_id else None
    if sess is None or sess.student_id != student.id or sess.concept_id != concept_id:
        sess = m.TeachSession(student_id=student.id, concept_id=concept_id, transcript=[])
        db.add(sess)
    db.commit()
    session_id = sess.id
    transcript = list(sess.transcript or [])
    guard = check_free_text(body.message, extra_names=[student.display_name])
    delay = s.lesson_stream_delay_ms / 1000

    def gen():
        yield sse("session", {"session_id": session_id, "trace_id": tid})
        reply, flags, fallback = teach_bot.reply(graph, concept_id, transcript, guard.text, tid, student.id)
        for w in reply.reply.split(" "):
            yield sse("delta", {"text": w + " "})
            if delay:
                time.sleep(delay)
        new_t = [
            *transcript,
            {"role": "student", "text": guard.text, "flags": sorted(set(guard.flags))},
            {"role": "bot", "text": reply.reply, "on_topic": reply.on_topic},
        ]
        covered, missing = teach_bot.coverage(
            graph.concepts[concept_id].key_points, [t["text"] for t in new_t if t["role"] == "student"]
        )
        with SessionLocal() as wdb:
            row = wdb.get(m.TeachSession, session_id)
            if row is not None:
                row.transcript = new_t
                row.covered_points = covered
                wdb.commit()
        total = max(1, len(graph.concepts[concept_id].key_points))
        yield sse("done", {
            "session_id": session_id, "reply": reply.reply, "on_topic": reply.on_topic,
            "covered_points": covered, "missing_points": missing, "coverage": round(len(covered) / total, 3),
            "flags": sorted(set(flags)), "source": "fallback" if fallback else "llm",
        })

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "x-trace-id": tid})


@router.post("/teach/{session_id}/score", response_model=TeachScoreResponse)
def teach_score(
    session_id: str,
    db: Session = Depends(get_db),
    graph: ContentGraph = Depends(graph_dep),
    tid: str = Depends(trace_id),
) -> TeachScoreResponse:
    sess = db.get(m.TeachSession, session_id)
    if sess is None:
        raise HTTPException(404, "teach session not found")
    if not any(t["role"] == "student" for t in sess.transcript or []):
        raise HTTPException(422, "explain something first!")
    result, source = teach_bot.score(graph, sess.concept_id, list(sess.transcript), tid, sess.student_id)
    sess.score = result.score
    sess.covered_points = result.covered_points
    already = db.scalar(
        select(m.XPEvent.id).where(m.XPEvent.student_id == sess.student_id, m.XPEvent.kind == "teach_score",
                                   m.XPEvent.concept_id == sess.concept_id).limit(1)
    ) is not None
    awards = gam.teach_awards(result.score, sess.concept_id, graph.name(sess.concept_id), already)
    badges = gam.persist_awards(db, sess.student_id, awards)
    db.commit()
    return TeachScoreResponse(
        trace_id=tid, session_id=sess.id, concept_id=sess.concept_id, score=result.score,
        covered_points=result.covered_points, missing_points=result.missing_points,
        misconceptions_detected=result.misconceptions_detected, feedback=result.feedback,
        xp_events=awards.xp, badges=badges, source=source,
    )
