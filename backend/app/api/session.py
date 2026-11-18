"""POST /session/start, GET /next-question."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, graph_dep, question_public, require_student, trace_id
from app.core.adaptive import select_next
from app.core.graph import ContentGraph
from app.core.student_state import get_or_create_student, load_attempts, student_summary
from app.db import models as m
from app.schemas.api import NextQuestionResponse, SessionStartRequest, SessionStartResponse

router = APIRouter(tags=["session"])


def build_next(db: Session, student_id: str, graph: ContentGraph, tid: str) -> NextQuestionResponse:
    pick = select_next(db, student_id, graph)
    n_regular = sum(1 for a in load_attempts(db, student_id)
                    if a.boss_battle_id is None and a.concept_id in graph.concepts)
    total = len(graph.diagnostic_concepts)
    return NextQuestionResponse(
        trace_id=tid,
        question=question_public(graph.questions[pick.question_id], graph) if pick.question_id else None,
        reason=pick.reason,
        phase=pick.phase,  # type: ignore[arg-type]
        diagnostic_progress=min(n_regular, total),
        diagnostic_total=total,
    )


@router.post("/session/start", response_model=SessionStartResponse)
def start_session(
    body: SessionStartRequest,
    db: Session = Depends(get_db),
    graph: ContentGraph = Depends(graph_dep),
    tid: str = Depends(trace_id),
) -> SessionStartResponse:
    student = get_or_create_student(db, body.student_id)
    sess = m.Session(student_id=student.id)
    db.add(sess)
    db.flush()
    nxt = build_next(db, student.id, graph, tid)
    summary = student_summary(db, student)
    db.commit()
    return SessionStartResponse(trace_id=tid, session_id=sess.id, student=summary, next=nxt)


@router.get("/next-question", response_model=NextQuestionResponse)
def next_question(
    student_id: str = Query(...),
    db: Session = Depends(get_db),
    graph: ContentGraph = Depends(graph_dep),
    tid: str = Depends(trace_id),
) -> NextQuestionResponse:
    require_student(db, student_id)
    out = build_next(db, student_id, graph, tid)
    db.commit()  # persists scheduled-item question assignments
    return out
