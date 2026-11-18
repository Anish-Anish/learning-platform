"""POST /attempts, GET /diagnoses/{id}."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.ai.llm_client import llm_mode
from app.api.deps import get_db, graph_dep, require_student, trace_id
from app.core import diagnosis as dxmod
from app.core.attempts import AttemptError, process_attempt, to_response
from app.core.graph import ContentGraph
from app.db import models as m
from app.guardrails.input import check_free_text
from app.observability.tracing import set_student_id
from app.schemas.api import AttemptRequest, AttemptResponse, DiagnosisOut

router = APIRouter(tags=["attempts"])


@router.post("/attempts", response_model=AttemptResponse)
def post_attempt(
    body: AttemptRequest,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    graph: ContentGraph = Depends(graph_dep),
    tid: str = Depends(trace_id),
) -> AttemptResponse:
    set_student_id(body.student_id)
    student = require_student(db, body.student_id)
    reasoning = check_free_text(body.reasoning_text).text if body.reasoning_text else None
    # Offline mode: the deterministic agent is instant, so run inline; online: background + client polls.
    inline = llm_mode() == "offline"
    try:
        ctx = process_attempt(
            db, graph, student=student, question_id=body.question_id, option_id=body.option_id,
            answer_text=body.answer_text, confidence=body.confidence, time_ms=body.time_ms,
            hints_used=body.hints_used, reasoning_text=reasoning, session_id=body.session_id, trace_id=tid,
            run_diagnosis_inline=inline,
        )
    except AttemptError as exc:
        db.rollback()
        raise HTTPException(422, str(exc)) from exc
    resp = to_response(ctx, tid)
    db.commit()
    if ctx.diagnosis is not None and ctx.diagnosis.status == "pending":
        background.add_task(dxmod.run_in_background, ctx.diagnosis.id, tid)
    return resp


@router.get("/diagnoses/{diagnosis_id}", response_model=DiagnosisOut)
def get_diagnosis(
    diagnosis_id: str,
    db: Session = Depends(get_db),
    graph: ContentGraph = Depends(graph_dep),
    tid: str = Depends(trace_id),
) -> DiagnosisOut:
    dx = db.get(m.Diagnosis, diagnosis_id)
    if dx is None:
        raise HTTPException(404, "diagnosis not found")
    return dxmod.to_out(dx, graph, tid)
