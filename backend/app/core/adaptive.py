"""Adaptive engine — next question selection (PROJECT_CONTEXT §9.4).

Order: diagnostic (first 5) -> scheduled probes -> scheduled remediation checks -> default
(misconception > gap > fragile > not_started, p closest to 0.7, Bloom ladder). Every pick has a reason.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.graph import ContentGraph, QuestionInfo
from app.core.learner_model import mastery, p_correct
from app.core.student_state import load_attempts, load_rows, recompute
from app.db import models as m
from app.schemas.common import BLOOM_ORDER

TIER = {"misconception": 0, "gap": 1, "fragile": 2, "not_started": 3}


@dataclass
class Pick:
    question_id: str | None
    concept_id: str | None
    reason: str
    phase: str
    scheduled_item_id: str | None = None


def bloom_target(concept_attempts: list[tuple[bool, str, int]], available_levels: list[int]) -> tuple[int, bool]:
    """Bloom ladder (§9.4.5): start at the lowest available level; 2 consecutive correct+sure -> next level.

    A confident correct answer *above* the current level counts as demonstrated (jump to that level).
    `concept_attempts` = (correct, confidence, bloom_index) oldest first.
    Returns (target bloom index, just_promoted).
    """
    if not available_levels:
        return 1, False
    levels = sorted(set(available_levels))
    idx = 0
    streak = 0
    promoted = False
    for correct, conf, bloom in concept_attempts:
        promoted = False
        if correct and conf == "sure":
            if bloom > levels[idx]:
                idx = max(i for i, lv in enumerate(levels) if lv <= bloom)
                streak = 1
            else:
                streak += 1
            if streak >= 2 and idx < len(levels) - 1:
                idx += 1
                streak = 0
                promoted = True
        elif not correct:
            streak = 0
    return levels[idx], promoted


def score_question(q: QuestionInfo, theta: float, target_bloom: int, target_p: float) -> float:
    p = p_correct(theta, q.b)
    return abs(p - target_p) + 0.15 * abs(q.bloom_index - target_bloom)


def _choose(
    candidates: list[QuestionInfo],
    theta: float,
    target_bloom: int,
    target_p: float,
    prefer_misconception: str | None = None,
    min_bloom: int | None = None,
) -> QuestionInfo | None:
    if not candidates:
        return None
    pool = candidates
    if min_bloom is not None:
        higher = [q for q in pool if q.bloom_index >= min_bloom]
        pool = higher or pool
    if prefer_misconception:
        targeted = [q for q in pool if prefer_misconception in q.targets]
        pool = targeted or pool
    return min(pool, key=lambda q: (score_question(q, theta, target_bloom, target_p), q.id))


def select_next(db: Session, student_id: str, graph: ContentGraph) -> Pick:
    s = get_settings()
    attempts = load_attempts(db, student_id)
    rows = load_rows(db, student_id, graph)
    results = recompute(rows, attempts, graph)
    regular = [a for a in attempts if a.boss_battle_id is None and a.concept_id in graph.concepts]
    recent_qids = {a.question_id for a in attempts[-s.recent_window :]}
    attempted_concepts = {a.concept_id for a in attempts}

    def available(cid: str, allow_recent: bool = False) -> list[QuestionInfo]:
        qs = [graph.questions[q] for q in graph.questions_by_concept.get(cid, [])]
        if allow_recent:
            return qs
        return [q for q in qs if q.id not in recent_qids]

    def concept_attempt_tuples(cid: str) -> list[tuple[bool, str, int]]:
        out = []
        for a in attempts:
            if a.concept_id == cid:
                q = graph.questions.get(a.question_id)
                out.append((a.is_correct, a.confidence, q.bloom_index if q else 1))
        return out

    # 1. Diagnostic phase -----------------------------------------------------------------
    diag = list(graph.diagnostic_concepts)
    n_diag = min(len(regular), len(diag))
    if len(regular) < len(diag):
        for cid in diag:
            if cid in attempted_concepts:
                continue
            qs = available(cid)
            mid = [q for q in qs if q.bloom_level in ("understand", "apply")] or qs
            if not mid:
                continue
            q = min(mid, key=lambda q: (abs(q.b), q.id))
            k = n_diag + 1
            return Pick(
                q.id,
                cid,
                f"Diagnostic {k}/{len(diag)}: sampling {graph.name(cid)} to map where you're starting. "
                "Answer honestly, and use 'Guessing' if you're not sure.",
                "diagnostic",
            )

    # 2-3. Scheduled probes, then remediation checks ------------------------------------------
    items = list(
        db.scalars(
            select(m.ScheduledItem)
            .where(m.ScheduledItem.student_id == student_id, m.ScheduledItem.status == "pending")
            .order_by(m.ScheduledItem.created_at)
        )
    )
    items.sort(key=lambda it: (0 if it.kind == "probe" else 1, it.created_at))
    for it in items:
        cid = it.concept_id
        if cid not in graph.concepts:
            it.status = "skipped"
            continue
        if it.question_id and it.question_id in graph.questions and it.question_id not in recent_qids:
            q = graph.questions[it.question_id]
        else:
            # Never repeat a question from the last 10 for a probe/check; skip if nothing fresh is left.
            qs = available(cid)
            levels = [graph.questions[qid].bloom_index for qid in graph.questions_by_concept.get(cid, [])]
            target, _ = bloom_target(concept_attempt_tuples(cid), levels)
            min_bloom = BLOOM_ORDER.index(it.min_bloom) if it.min_bloom in BLOOM_ORDER else None
            q = _choose(qs, rows[cid].theta, target, s.target_p, it.misconception_id, min_bloom)
        if q is None:
            it.status = "skipped"
            continue
        it.question_id = q.id
        db.flush()
        phase = "probe" if it.kind == "probe" else "remediation"
        return Pick(q.id, cid, it.reason, phase, it.id)

    # 4-5. Default: weakest unlocked, not-mastered concept; p closest to target; Bloom ladder -----------
    candidates: list[tuple[int, float, str]] = []
    for cid in graph.topo_order:
        st = results[cid].state
        if st in TIER:
            candidates.append((TIER[st], mastery(rows[cid].theta), cid))
    candidates.sort(key=lambda t: (t[0], t[1] if t[0] < 3 else 0, graph.concepts[t[2]].depth))

    # Momentum (blocked practice): stay on the last concept while it is in the best tier, up to 4 in a row.
    momentum = False
    if candidates and regular:
        last_c = regular[-1].concept_id
        run = 0
        for a in reversed(regular):
            if a.concept_id != last_c:
                break
            run += 1
        best_tier = candidates[0][0]
        for i, (tier, _mv, cid) in enumerate(candidates):
            if cid == last_c and tier == best_tier and run < 4 and available(cid):
                candidates.insert(0, candidates.pop(i))
                momentum = True
                break

    for tier, mval, cid in candidates:
        qs = available(cid)
        if not qs:
            continue
        levels = [graph.questions[qid].bloom_index for qid in graph.questions_by_concept.get(cid, [])]
        target, promoted = bloom_target(concept_attempt_tuples(cid), levels)
        active = rows[cid].active_misconception_ids or []
        q = _choose(qs, rows[cid].theta, target, s.target_p, active[0] if active else None)
        if q is None:
            continue
        p = p_correct(rows[cid].theta, q.b)
        name = graph.name(cid)
        bloom = q.bloom_level
        if tier == 0:
            mdesc = graph.misconceptions[active[0]].description if active and active[0] in graph.misconceptions else ""
            reason = (
                f"{name} has an active misconception ('{mdesc}'). This {bloom} question targets it. "
                f"Two confident correct answers clear it."
            )
        elif tier == 1:
            reason = (
                f"{name} is a gap (mastery {mval:.0%}). This {bloom} question has about {p:.0%} predicted success, "
                "the learning sweet spot."
            )
        elif tier == 2:
            reason = (
                f"{name} is fragile (mastery {mval:.0%}). A {bloom} question at about {p:.0%} predicted success "
                "will firm it up."
            )
        else:
            reason = f"{name} is unlocked and new to you. Starting at the {bloom} level (about {p:.0%} predicted success)."
        if promoted:
            reason += f" You answered 2 in a row confidently, so we moved up to '{bloom}'."
        elif momentum and cid == regular[-1].concept_id:
            reason += " Staying on this concept a little longer to lock it in."
        return Pick(q.id, cid, reason, "practice")

    # Nothing left: review the weakest mastered concept, avoiding recent questions.
    mastered = sorted(
        (cid for cid in graph.topo_order if results[cid].state == "mastered"), key=lambda c: rows[c].theta
    )
    for cid in mastered:
        qs = available(cid)
        if qs:
            q = max(qs, key=lambda q: (q.bloom_index, q.id))
            return Pick(q.id, cid, f"Everything unlocked is mastered. Reviewing {graph.name(cid)} at a harder level.", "practice")
    return Pick(None, None, "You've mastered everything available. Try a Root Boss or teach the bot!", "complete")
