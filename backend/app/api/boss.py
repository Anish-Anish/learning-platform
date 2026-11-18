"""GET /boss/{student_id}, POST /boss/{battle_id}/attempt."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, graph_dep, question_public, require_student, trace_id
from app.config import get_settings
from app.core import boss as bossmod
from app.core.attempts import AttemptError
from app.core.graph import ContentGraph
from app.db import models as m
from app.schemas.api import BossAttemptRequest, BossAttemptResponse, BossBattleOut

router = APIRouter(tags=["boss"])


def battle_out(b: m.BossBattle, graph: ContentGraph, tid: str) -> BossBattleOut:
    return BossBattleOut(
        trace_id=tid, id=b.id, student_id=b.student_id, name=b.name, taunt=b.taunt, hp=b.hp, max_hp=b.max_hp,
        status=b.status, misconception_ids=list(b.misconception_ids or []),
        questions=[question_public(graph.questions[q], graph) for q in b.question_ids if q in graph.questions],
        current_index=b.current_index, damage_per_hit=bossmod.damage_per_hit(b),
    )


@router.get("/boss/{student_id}", response_model=BossBattleOut)
def get_boss(
    student_id: str,
    battle_id: str | None = Query(default=None, description="Fetch a specific battle instead of create/get"),
    db: Session = Depends(get_db),
    graph: ContentGraph = Depends(graph_dep),
    tid: str = Depends(trace_id),
) -> BossBattleOut:
    if not get_settings().flag_boss:
        raise HTTPException(404, "boss battles disabled")
    require_student(db, student_id)
    if battle_id:
        b = db.get(m.BossBattle, battle_id)
        if b is None or b.student_id != student_id:
            raise HTTPException(404, "battle not found")
        return battle_out(b, graph, tid)
    try:
        b = bossmod.get_or_create(db, student_id, graph, tid)
    except bossmod.BossError as exc:
        raise HTTPException(409, str(exc)) from exc
    db.commit()
    return battle_out(b, graph, tid)


@router.post("/boss/{battle_id}/attempt", response_model=BossAttemptResponse)
def boss_attempt(
    battle_id: str,
    body: BossAttemptRequest,
    db: Session = Depends(get_db),
    graph: ContentGraph = Depends(graph_dep),
    tid: str = Depends(trace_id),
) -> BossAttemptResponse:
    b = db.get(m.BossBattle, battle_id)
    if b is None:
        raise HTTPException(404, "battle not found")
    student = require_student(db, b.student_id)
    try:
        ctx, dmg, cleared, extra, badges = bossmod.answer(
            db, b, student, graph, question_id=body.question_id, option_id=body.option_id,
            confidence=body.confidence, time_ms=body.time_ms, trace_id=tid,
        )
    except (bossmod.BossError, AttemptError) as exc:
        db.rollback()
        raise HTTPException(409, str(exc)) from exc
    q = graph.questions[body.question_id]
    out = BossAttemptResponse(
        trace_id=tid, is_correct=ctx.attempt.is_correct,
        correct_option_id=q.correct_option.id if q.correct_option else None, explanation=q.explanation,
        damage=dmg, hp=b.hp, max_hp=b.max_hp, status=b.status, current_index=b.current_index,
        xp_events=[*ctx.awards.xp, *extra.xp], badges=badges,
        cleared_misconception_ids=sorted(set(ctx.cleared) | set(cleared)), unlocks=[*ctx.awards.unlocks, *extra.unlocks],
    )
    db.commit()
    return out
