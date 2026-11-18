"""Root Boss battle (W1): personalised challenge from the student's own confident-wrong history.

Questions are drawn from the bank (deterministic). Boss answers are real attempts (same event path).
Beating the boss clears its misconceptions (§9.3) and awards XP; the LLM only names the boss.
"""

from __future__ import annotations

import math

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.generators import boss_flavor
from app.config import get_settings
from app.core import gamification as gam
from app.core.attempts import clear_misconceptions, compute_awards, process_attempt
from app.core.graph import ContentGraph, QuestionInfo
from app.core.student_state import load_attempts, load_rows, recompute, unlocked_set
from app.db import models as m
from app.db.models import utcnow


class BossError(ValueError):
    pass


def pick_misconceptions(db: Session, student_id: str, graph: ContentGraph) -> list[str]:
    rows = load_rows(db, student_id, graph)
    attempts = load_attempts(db, student_id)
    out: list[str] = []
    for r in rows.values():
        for mid in r.active_misconception_ids or []:
            if mid not in out:
                out.append(mid)
    for a in reversed(attempts):
        mid = a.selected_misconception_id
        if mid and not a.is_correct and a.confidence == "sure" and mid not in out:
            out.append(mid)
    return out[:3]


def pick_questions(
    graph: ContentGraph, mids: list[str], recent: set[str], weak_concepts: list[str], n: int,
    familiar: set[str] | None = None,
) -> list[QuestionInfo]:
    """Questions targeting the misconceptions (round-robin across them, unseen first), restricted to concepts
    the student has met (`familiar`), then filled from the misconception / weak concepts. Sorted by Bloom."""
    chosen: list[QuestionInfo] = []
    fam = familiar if familiar is not None else set(graph.concepts)

    def order(qs: list[QuestionInfo]) -> list[QuestionInfo]:
        return sorted(qs, key=lambda q: (q.id in recent, q.bloom_index, q.id))

    pools = []
    for mid in mids:
        mc_concept = graph.misconceptions[mid].concept_id if mid in graph.misconceptions else None
        qs = [graph.questions[q] for q in graph.questions_by_misconception.get(mid, []) if q in graph.questions]
        pools.append(order([q for q in qs if q.concept_id in fam or q.concept_id == mc_concept]))
    while len(chosen) < n and any(pools):
        for pool in pools:
            while pool and pool[0] in chosen:
                pool.pop(0)
            if pool and len(chosen) < n:
                chosen.append(pool.pop(0))
    concepts = [graph.misconceptions[mid].concept_id for mid in mids if mid in graph.misconceptions] + weak_concepts
    for cid in concepts:
        for q in order([graph.questions[q] for q in graph.questions_by_concept.get(cid, [])]):
            if len(chosen) >= n:
                break
            if q not in chosen:
                chosen.append(q)
    return sorted(chosen, key=lambda q: (q.bloom_index, q.b))


def get_or_create(db: Session, student_id: str, graph: ContentGraph, trace_id: str) -> m.BossBattle:
    s = get_settings()
    active = db.scalars(
        select(m.BossBattle).where(m.BossBattle.student_id == student_id, m.BossBattle.status == "active")
        .order_by(m.BossBattle.created_at.desc())
    ).first()
    if active is not None:
        return active
    attempts = load_attempts(db, student_id)
    rows = load_rows(db, student_id, graph)
    results = recompute(rows, attempts, graph)
    mids = pick_misconceptions(db, student_id, graph)
    weak = [cid for cid in graph.topo_order if results[cid].state in ("gap", "fragile", "misconception")]
    recent = {a.question_id for a in attempts[-s.recent_window :]}
    familiar = {a.concept_id for a in attempts} | {cid for cid, r in results.items() if r.state != "locked"}
    qs = pick_questions(graph, mids, recent, weak[:3] or graph.topo_order[:3], s.boss_questions, familiar)
    if not qs:
        raise BossError("not enough questions for a boss battle yet")
    flavor = boss_flavor(graph, mids, trace_id, student_id)
    battle = m.BossBattle(
        student_id=student_id,
        name=flavor.name,
        taunt=flavor.taunt,
        question_ids=[q.id for q in qs],
        misconception_ids=mids,
        hp=s.boss_max_hp,
        max_hp=s.boss_max_hp,
        current_index=0,
        status="active",
    )
    db.add(battle)
    db.flush()
    return battle


def damage_per_hit(battle: m.BossBattle) -> int:
    n = len(battle.question_ids)
    hits_needed = max(1, n - 1) if n > 2 else n  # one mistake allowed
    return math.ceil(battle.max_hp / hits_needed)


def answer(
    db: Session, battle: m.BossBattle, student: m.Student, graph: ContentGraph, *, question_id: str, option_id: str,
    confidence: str, time_ms: int, trace_id: str,
):
    if battle.status != "active":
        raise BossError(f"battle is {battle.status}")
    if battle.current_index >= len(battle.question_ids) or battle.question_ids[battle.current_index] != question_id:
        raise BossError("that's not the current boss question")
    ctx = process_attempt(
        db, graph, student=student, question_id=question_id, option_id=option_id, answer_text=None,
        confidence=confidence, time_ms=time_ms, hints_used=0, reasoning_text=None, session_id=None,
        trace_id=trace_id, boss_battle_id=battle.id,
    )
    dmg = damage_per_hit(battle) if ctx.attempt.is_correct else 0
    battle.hp = max(0, battle.hp - dmg)
    battle.current_index += 1
    remaining = len(battle.question_ids) - battle.current_index
    extra_awards = gam.Awards()
    cleared: list[str] = []
    if battle.hp <= 0:
        battle.status = "won"
        battle.finished_at = utcnow()
        rows = ctx.rows
        before_unlocked = unlocked_set(rows, graph)
        active_now = {mid for r in rows.values() for mid in (r.active_misconception_ids or [])}
        cleared = [mid for mid in battle.misconception_ids if mid in active_now]
        clear_misconceptions(rows, set(cleared))
        results = recompute(rows, ctx.attempts, graph)
        extra_awards.extend(compute_awards(db, graph, student.id, rows, results, before_unlocked, cleared))
        extra_awards.extend(gam.boss_awards(battle.name))
        ctx.results = results
    elif remaining * damage_per_hit(battle) < battle.hp:
        battle.status = "lost"
        battle.finished_at = utcnow()
    new_badges = ctx.new_badges + gam.persist_awards(db, student.id, extra_awards)
    db.flush()
    return ctx, dmg, cleared, extra_awards, new_badges
