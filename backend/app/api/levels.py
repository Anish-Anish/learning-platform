"""Adventure mode endpoints (game layer) + study scroll + profile + class game results."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.ai.llm_client import llm_mode
from app.api.deps import get_db, graph_dep, require_student, trace_id
from app.core import diagnosis as dxmod
from app.core import levels as lv
from app.core.attempts import AttemptError, to_response
from app.core.graph import ContentGraph
from app.db import models as m
from app.schemas.api import (
    ClassGameResponse,
    ConceptDetail,
    LevelAnswerRequest,
    LevelAnswerResponse,
    LevelStartRequest,
    LevelStartResponse,
    PowerupResponse,
    ProfileResponse,
    WorldMapResponse,
)

router = APIRouter(tags=["adventure"])


@router.get("/students/{student_id}/world", response_model=WorldMapResponse)
def get_world(student_id: str, db: Session = Depends(get_db), graph: ContentGraph = Depends(graph_dep),
              tid: str = Depends(trace_id)) -> WorldMapResponse:
    require_student(db, student_id)
    out = lv.world_map(db, student_id, graph, tid)
    db.commit()
    return out


@router.get("/students/{student_id}/profile", response_model=ProfileResponse)
def get_profile(student_id: str, db: Session = Depends(get_db), graph: ContentGraph = Depends(graph_dep),
                tid: str = Depends(trace_id)) -> ProfileResponse:
    return lv.profile(db, require_student(db, student_id), graph, tid)


@router.get("/concepts/{concept_id}", response_model=ConceptDetail)
def get_concept(concept_id: str, graph: ContentGraph = Depends(graph_dep)) -> ConceptDetail:
    if concept_id not in graph.concepts:
        raise HTTPException(404, "unknown concept")
    return lv.concept_detail(graph, concept_id)


@router.post("/levels/{concept_id}/start", response_model=LevelStartResponse)
def start_level(concept_id: str, body: LevelStartRequest, db: Session = Depends(get_db),
                graph: ContentGraph = Depends(graph_dep), tid: str = Depends(trace_id)) -> LevelStartResponse:
    require_student(db, body.student_id)
    try:
        run = lv.start_run(db, body.student_id, graph, concept_id, restart=body.restart)
    except lv.LevelLocked as exc:
        raise HTTPException(409, f"Level locked. {exc}") from exc
    except lv.LevelError as exc:
        raise HTTPException(404, str(exc)) from exc
    best = lv.best_stars(db, body.student_id).get(concept_id, 0)
    out = LevelStartResponse(trace_id=tid, run=lv.run_out(run, graph), best_stars=best)
    db.commit()
    return out


def _run(db: Session, run_id: str) -> m.LevelRun:
    run = db.get(m.LevelRun, run_id)
    if run is None:
        raise HTTPException(404, "run not found")
    return run


@router.post("/levels/runs/{run_id}/fifty", response_model=PowerupResponse)
def use_fifty(run_id: str, db: Session = Depends(get_db), graph: ContentGraph = Depends(graph_dep),
              tid: str = Depends(trace_id)) -> PowerupResponse:
    run = _run(db, run_id)
    try:
        lv.use_fifty(db, run, graph)
    except lv.LevelError as exc:
        raise HTTPException(409, str(exc)) from exc
    out = PowerupResponse(trace_id=tid, run=lv.run_out(run, graph))
    db.commit()
    return out


@router.post("/levels/runs/{run_id}/answer", response_model=LevelAnswerResponse)
def answer_level(run_id: str, body: LevelAnswerRequest, background: BackgroundTasks, db: Session = Depends(get_db),
                 graph: ContentGraph = Depends(graph_dep), tid: str = Depends(trace_id)) -> LevelAnswerResponse:
    run = _run(db, run_id)
    student = require_student(db, run.student_id)
    previous_best = lv.best_stars(db, run.student_id).get(run.concept_id, 0)
    inline = llm_mode() == "offline"
    try:
        ctx = lv.answer(db, run, student, graph, option_id=body.option_id, confidence=body.confidence,
                        hints_used=body.hints_used, time_ms=body.time_ms, session_id=body.session_id,
                        trace_id=tid, inline=inline)
    except (lv.LevelError, AttemptError) as exc:
        db.rollback()
        raise HTTPException(409, str(exc)) from exc
    attempt = to_response(ctx, tid)
    out = LevelAnswerResponse(trace_id=tid, run=lv.run_out(run, graph), attempt=attempt,
                              best_stars=max(previous_best, run.stars), new_best=run.stars > previous_best)
    db.commit()
    if ctx.diagnosis is not None and ctx.diagnosis.status == "pending":
        background.add_task(dxmod.run_in_background, ctx.diagnosis.id, tid)
    return out


@router.get("/class/game", response_model=ClassGameResponse)
def class_game(student_id: str | None = Query(default=None, description="Only this student's runs"),
               db: Session = Depends(get_db), graph: ContentGraph = Depends(graph_dep),
               tid: str = Depends(trace_id)) -> ClassGameResponse:
    return lv.class_game(db, graph, tid, student_id)
