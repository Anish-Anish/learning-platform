"""Adventure mode — the self-directed game layer (deterministic rules only).

* A **world** groups concepts (seed/worlds.json); each concept is a **level**.
* A **level run** is a short play-through: up to 4 questions of rising Bloom level, 3 hearts, combo counter,
  one 50/50 power-up. Every answer goes through the normal attempt pipeline (learner model, misconceptions,
  diagnosis, gamification), so playing levels is real learning evidence.
* **Stars** (0-3) and **daily quests** are pure functions of recorded play. They never award XP: XP stays
  mastery-only (PROJECT_CONTEXT §9.5). Stars are a separate, visible game score.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, time
from functools import lru_cache

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import SEED_DIR
from app.core.attempts import process_attempt
from app.core.gamification import BADGES
from app.core.graph import ContentGraph
from app.core.learner_model import mastery
from app.core.present import question_public
from app.core.student_state import load_attempts, load_rows, recompute, student_summary
from app.db import models as m
from app.db.models import utcnow
from app.schemas.api import (
    ClassGameResponse,
    CommonTrap,
    ConceptDetail,
    GameLevelStat,
    GameRunOut,
    GameStudentStat,
    LevelInfo,
    LevelRunOut,
    ProfileBadge,
    ProfileResponse,
    QuestOut,
    WorldInfo,
    WorldMapResponse,
)

MAX_HEARTS = 3
RUN_LENGTH = 4
FIFTY_PER_RUN = 1


class LevelError(ValueError):
    pass


class LevelLocked(LevelError):
    pass


@lru_cache
def worlds() -> list[dict]:
    return json.loads((SEED_DIR / "worlds.json").read_text())


def world_of(concept_id: str) -> dict | None:
    return next((w for w in worlds() if concept_id in w["concepts"]), None)


# ------------------------------------------------------------------ pure rules
def stars_for(total: int, correct: int, correct_sure: int, failed: bool, powerups_used: int) -> int:
    """1★ finish the level · 2★ at most one mistake · 3★ flawless AND every answer marked Sure.
    Using a power-up caps the run at 2★ (an honest trade-off)."""
    if failed or total == 0:
        return 0
    stars = 1
    if correct >= total - 1:
        stars = 2
    if correct == total and correct_sure == total:
        stars = 3
    if powerups_used:
        stars = min(stars, 2)
    return stars


def plan_questions(graph: ContentGraph, concept_id: str, recent_correct: set[str], n: int = RUN_LENGTH) -> list[str]:
    """Up to n questions of rising Bloom level, preferring ones not answered correctly recently
    (those would earn no mastery credit under anti-farming)."""
    qs = [graph.questions[q] for q in graph.questions_by_concept.get(concept_id, [])]
    order = lambda q: (q.bloom_index, q.b, q.id)  # noqa: E731
    fresh = sorted([q for q in qs if q.id not in recent_correct], key=order)
    stale = sorted([q for q in qs if q.id in recent_correct], key=order)
    pool = fresh if len(fresh) >= min(n, len(qs)) else fresh + stale
    if len(pool) > n:  # spread across the Bloom range
        idx = sorted({round(i * (len(pool) - 1) / (n - 1)) for i in range(n)})
        pool = [pool[i] for i in idx]
    return [q.id for q in sorted(pool[:n], key=order)]


def fifty_removals(run_id: str, option_ids_wrong: list[str]) -> list[str]:
    """Remove all but one wrong option, deterministically per run."""
    ranked = sorted(option_ids_wrong, key=lambda o: hashlib.sha1(f"{run_id}:{o}".encode()).hexdigest())
    return ranked[: max(0, len(ranked) - 1)]


# ------------------------------------------------------------------ helpers
def best_stars(db: Session, student_id: str) -> dict[str, int]:
    rows = db.execute(
        select(m.LevelRun.concept_id, func.max(m.LevelRun.stars))
        .where(m.LevelRun.student_id == student_id)
        .group_by(m.LevelRun.concept_id)
    ).all()
    return {cid: int(s or 0) for cid, s in rows}


def plays(db: Session, student_id: str) -> dict[str, int]:
    rows = db.execute(
        select(m.LevelRun.concept_id, func.count(m.LevelRun.id))
        .where(m.LevelRun.student_id == student_id, m.LevelRun.status.in_(["completed", "failed"]))
        .group_by(m.LevelRun.concept_id)
    ).all()
    return {cid: int(n) for cid, n in rows}


def run_out(run: m.LevelRun, graph: ContentGraph) -> LevelRunOut:
    q = None
    removed: list[str] = []
    if run.status == "active" and run.current_index < len(run.question_ids):
        qid = run.question_ids[run.current_index]
        q = question_public(graph.questions[qid], graph)
        removed = list((run.removed_options or {}).get(qid, []))
    return LevelRunOut(
        id=run.id, concept_id=run.concept_id, concept_name=graph.name(run.concept_id), status=run.status,
        hearts=run.hearts, max_hearts=run.max_hearts, index=run.current_index, total=len(run.question_ids),
        correct=run.correct, combo=run.combo, best_combo=run.best_combo, stars=run.stars,
        fifty_left=run.fifty_left, powerups_used=run.powerups_used, question=q, removed_option_ids=removed,
    )


# ------------------------------------------------------------------ world map
def world_map(db: Session, student_id: str, graph: ContentGraph, trace_id: str) -> WorldMapResponse:
    attempts = load_attempts(db, student_id)
    rows = load_rows(db, student_id, graph)
    results = recompute(rows, attempts, graph)
    best = best_stars(db, student_id)
    n_plays = plays(db, student_id)
    out_worlds: list[WorldInfo] = []
    seen: set[str] = set()
    for w in [*worlds(), {"id": "bonus", "name": "Bonus Isles", "emoji": "🏝️", "color": "rose",
                          "tagline": "Extra challenges.", "concepts": [c for c in graph.concepts]}]:
        levels = []
        for cid in w["concepts"]:
            if cid not in graph.concepts or cid in seen:
                continue
            seen.add(cid)
            res = results[cid]
            n_q = len(graph.questions_by_concept.get(cid, []))
            playable = res.state != "locked" and n_q > 0
            levels.append(LevelInfo(
                concept_id=cid, name=graph.name(cid), state=res.state, mastery=round(mastery(rows[cid].theta), 3),
                stars=best.get(cid, 0), playable=playable, locked_reason=None if playable else res.reason,
                has_myth=bool(rows[cid].active_misconception_ids), prerequisites=graph.concepts[cid].prerequisites,
                n_questions=n_q, plays=n_plays.get(cid, 0),
            ))
        if not levels:
            continue
        out_worlds.append(WorldInfo(
            id=w["id"], name=w["name"], tagline=w["tagline"], emoji=w["emoji"], color=w["color"], levels=levels,
            stars=sum(lv.stars for lv in levels), max_stars=3 * len(levels), unlocked=any(lv.playable for lv in levels),
        ))

    all_levels = [lv for w in out_worlds for lv in w.levels]
    rec, reason = None, "Every level has 3 stars. Legendary!"
    myth = next((lv for lv in all_levels if lv.has_myth and lv.playable), None)
    fresh = next((lv for lv in all_levels if lv.playable and lv.stars == 0), None)
    polish = sorted((lv for lv in all_levels if lv.playable and lv.stars < 3), key=lambda lv: (lv.stars, lv.mastery))
    if myth:
        rec, reason = myth.concept_id, f"A myth lurks in {myth.name}. Go bust it!"
    elif fresh:
        rec, reason = fresh.concept_id, f"Next adventure: {fresh.name}."
    elif polish:
        rec, reason = polish[0].concept_id, f"Go for 3 stars on {polish[0].name}."
    myths = {mid for r in rows.values() for mid in (r.active_misconception_ids or [])}
    return WorldMapResponse(
        trace_id=trace_id, student_id=student_id, worlds=out_worlds,
        stars_total=sum(lv.stars for lv in all_levels), stars_max=3 * len(all_levels),
        recommended_concept_id=rec, recommended_reason=reason, myths_active=len(myths),
    )


# ------------------------------------------------------------------ runs
def start_run(db: Session, student_id: str, graph: ContentGraph, concept_id: str, restart: bool = False) -> m.LevelRun:
    if concept_id not in graph.concepts or not graph.questions_by_concept.get(concept_id):
        raise LevelError("unknown level")
    attempts = load_attempts(db, student_id)
    rows = load_rows(db, student_id, graph)
    results = recompute(rows, attempts, graph)
    if results[concept_id].state == "locked":
        raise LevelLocked(results[concept_id].reason)
    active = db.scalars(
        select(m.LevelRun).where(m.LevelRun.student_id == student_id, m.LevelRun.concept_id == concept_id,
                                 m.LevelRun.status == "active").order_by(m.LevelRun.created_at.desc())
    ).first()
    if active is not None and not restart:
        return active
    if active is not None:
        active.status = "abandoned"
        active.finished_at = utcnow()
    recent_correct = {a.question_id for a in attempts[-10:] if a.is_correct}
    run = m.LevelRun(
        student_id=student_id, concept_id=concept_id, question_ids=plan_questions(graph, concept_id, recent_correct),
        attempt_ids=[], hearts=MAX_HEARTS, max_hearts=MAX_HEARTS, fifty_left=FIFTY_PER_RUN, removed_options={},
        status="active",
    )
    db.add(run)
    db.flush()
    return run


def use_fifty(db: Session, run: m.LevelRun, graph: ContentGraph) -> m.LevelRun:
    if run.status != "active":
        raise LevelError("this run is over")
    if run.fifty_left <= 0:
        raise LevelError("no 50/50 left in this run")
    qid = run.question_ids[run.current_index]
    if qid in (run.removed_options or {}):
        raise LevelError("50/50 already used on this question")
    wrong = [o.id for o in graph.questions[qid].options if not o.is_correct]
    run.removed_options = {**(run.removed_options or {}), qid: fifty_removals(run.id, wrong)}
    run.fifty_left -= 1
    run.powerups_used += 1
    db.flush()
    return run


def answer(
    db: Session, run: m.LevelRun, student: m.Student, graph: ContentGraph, *, option_id: str, confidence: str,
    hints_used: int, time_ms: int, session_id: str | None, trace_id: str, inline: bool,
):
    if run.status != "active":
        raise LevelError("this run is over")
    qid = run.question_ids[run.current_index]
    removed = (run.removed_options or {}).get(qid, [])
    if option_id in removed:
        raise LevelError("that option was removed by 50/50")
    # A 50/50 counts like a hint: -25% mastery credit and the usual hint XP cost.
    ctx = process_attempt(
        db, graph, student=student, question_id=qid, option_id=option_id, answer_text=None, confidence=confidence,
        time_ms=time_ms, hints_used=min(3, hints_used + (1 if removed else 0)), reasoning_text=None,
        session_id=session_id, trace_id=trace_id, run_diagnosis_inline=inline,
    )
    a = ctx.attempt
    run.attempt_ids = [*(run.attempt_ids or []), a.id]
    if a.is_correct:
        run.correct += 1
        run.combo += 1
        run.best_combo = max(run.best_combo, run.combo)
        if a.confidence == "sure":
            run.correct_sure += 1
    else:
        run.hearts -= 1
        run.combo = 0
    run.current_index += 1
    if run.hearts <= 0:
        run.status, run.stars, run.finished_at = "failed", 0, utcnow()
    elif run.current_index >= len(run.question_ids):
        run.status = "completed"
        run.stars = stars_for(len(run.question_ids), run.correct, run.correct_sure, False, run.powerups_used)
        run.finished_at = utcnow()
    db.flush()
    return ctx


# ------------------------------------------------------------------ study scroll
def concept_detail(graph: ContentGraph, concept_id: str) -> ConceptDetail:
    c = graph.concepts[concept_id]
    traps = [CommonTrap(description=mc.description, correct_belief=mc.correct_belief)
             for mc in graph.misconceptions.values() if mc.concept_id == concept_id]
    return ConceptDetail(id=c.id, name=c.name, description=c.description, prerequisites=c.prerequisites,
                         key_points=c.key_points, notes_md=c.notes_md, traps=traps)


# ------------------------------------------------------------------ quests + profile
def _today_start() -> datetime:
    return datetime.combine(utcnow().date(), time.min)


def quests(db: Session, student_id: str) -> list[QuestOut]:
    since = _today_start()
    atts = db.scalars(select(m.Attempt).where(m.Attempt.student_id == student_id, m.Attempt.created_at >= since)).all()
    stars_today = db.scalar(
        select(func.coalesce(func.sum(m.LevelRun.stars), 0)).where(
            m.LevelRun.student_id == student_id, m.LevelRun.finished_at >= since)
    ) or 0
    busted = db.scalar(
        select(func.count(m.XPEvent.id)).where(m.XPEvent.student_id == student_id, m.XPEvent.created_at >= since,
                                               m.XPEvent.kind == "misconception_cleared")
    ) or 0
    spec = [
        ("warmup", "Warm-up", "Answer 5 questions", "🔥", len(atts), 5),
        ("honest", "Honest hero", "Get 3 right while marked Sure", "🎯",
         sum(1 for a in atts if a.is_correct and a.confidence == "sure"), 3),
        ("stars", "Star collector", "Earn 3 stars in Adventure", "⭐", int(stars_today), 3),
        ("myth", "Myth hunter", "Bust a misconception", "👻", int(busted), 1),
    ]
    return [QuestOut(id=i, title=t, description=d, emoji=e, progress=min(p, n), target=n, done=p >= n)
            for i, t, d, e, p, n in spec]


def profile(db: Session, student: m.Student, graph: ContentGraph, trace_id: str) -> ProfileResponse:
    best = best_stars(db, student.id)
    playable_levels = [cid for cid in graph.concepts if graph.questions_by_concept.get(cid)]
    earned = {b.badge_id: b.earned_at for b in db.scalars(select(m.StudentBadge).where(m.StudentBadge.student_id == student.id))}
    runs = db.scalars(select(m.LevelRun).where(m.LevelRun.student_id == student.id)).all()
    return ProfileResponse(
        trace_id=trace_id,
        student=student_summary(db, student),
        stars_total=sum(best.values()),
        stars_max=3 * len(playable_levels),
        levels_completed=sum(1 for s in best.values() if s >= 1),
        levels_total=len(playable_levels),
        three_star_levels=sum(1 for s in best.values() if s == 3),
        bosses_defeated=db.scalar(select(func.count(m.BossBattle.id)).where(
            m.BossBattle.student_id == student.id, m.BossBattle.status == "won")) or 0,
        misconceptions_cleared=db.scalar(select(func.count(m.XPEvent.id)).where(
            m.XPEvent.student_id == student.id, m.XPEvent.kind == "misconception_cleared")) or 0,
        concepts_mastered=db.scalar(select(func.count()).select_from(m.MasteryState).where(
            m.MasteryState.student_id == student.id, m.MasteryState.ever_mastered.is_(True))) or 0,
        best_combo=max((r.best_combo for r in runs), default=0),
        runs_played=sum(1 for r in runs if r.status in ("completed", "failed")),
        attempts_total=db.scalar(select(func.count(m.Attempt.id)).where(m.Attempt.student_id == student.id)) or 0,
        badges=[ProfileBadge(badge_id=bid, name=name, description=desc, earned=bid in earned, earned_at=earned.get(bid))
                for bid, (name, desc) in BADGES.items()],
        quests=quests(db, student.id),
    )


# ------------------------------------------------------------------ teacher: class game results
def class_game(db: Session, graph: ContentGraph, trace_id: str, student_id: str | None = None) -> ClassGameResponse:
    students = {s.id: s for s in db.scalars(select(m.Student))}
    q = select(m.LevelRun).where(m.LevelRun.status.in_(["completed", "failed"]))
    if student_id:
        q = q.where(m.LevelRun.student_id == student_id)
    runs = db.scalars(q.order_by(m.LevelRun.finished_at.desc())).all()
    by_student: dict[str, list[m.LevelRun]] = defaultdict(list)
    by_level: dict[str, list[m.LevelRun]] = defaultdict(list)
    for r in runs:
        by_student[r.student_id].append(r)
        by_level[r.concept_id].append(r)
    bosses = dict(db.execute(select(m.BossBattle.student_id, func.count(m.BossBattle.id))
                             .where(m.BossBattle.status == "won").group_by(m.BossBattle.student_id)).all())

    stats = []
    for sid, rs in by_student.items():
        s = students.get(sid)
        if s is None:
            continue
        best: dict[str, int] = {}
        for r in rs:
            best[r.concept_id] = max(best.get(r.concept_id, 0), r.stars)
        stats.append(GameStudentStat(
            student_id=sid, display_name=s.display_name, is_simulated=s.is_simulated, stars=sum(best.values()),
            levels_completed=sum(1 for v in best.values() if v >= 1), runs=len(rs),
            wins=sum(1 for r in rs if r.status == "completed"), fails=sum(1 for r in rs if r.status == "failed"),
            best_combo=max((r.best_combo for r in rs), default=0), bosses_defeated=int(bosses.get(sid, 0)),
            quests_done_today=sum(1 for q in quests(db, sid) if q.done),
            last_played=max((r.finished_at for r in rs if r.finished_at), default=None),
        ))
    stats.sort(key=lambda x: (-x.stars, -x.wins, x.display_name))

    att_mis = {a.id: a.selected_misconception_id for a in db.scalars(
        select(m.Attempt).where(m.Attempt.selected_misconception_id.is_not(None)))}
    levels = []
    for w in worlds():
        for cid in w["concepts"]:
            if cid not in graph.concepts:
                continue
            rs = by_level.get(cid, [])
            done = [r for r in rs if r.status == "completed"]
            myths = Counter(att_mis[a] for r in rs for a in (r.attempt_ids or []) if a in att_mis)
            top = myths.most_common(1)[0][0] if myths else None
            levels.append(GameLevelStat(
                concept_id=cid, name=graph.name(cid), world=w["name"], plays=len(rs), completions=len(done),
                fails=len(rs) - len(done), completion_rate=round(len(done) / len(rs), 3) if rs else None,
                avg_stars=round(sum(r.stars for r in done) / len(done), 2) if done else None,
                avg_correct_pct=round(sum(r.correct / max(1, len(r.question_ids)) for r in rs) / len(rs), 3) if rs else None,
                top_myth=graph.misconceptions[top].description if top in graph.misconceptions else None,
            ))
    recent = [
        GameRunOut(
            id=r.id, student_id=r.student_id, display_name=students[r.student_id].display_name if r.student_id in students else r.student_id,
            concept_id=r.concept_id, concept_name=graph.name(r.concept_id), status=r.status, stars=r.stars, correct=r.correct,
            total=len(r.question_ids), hearts_left=max(0, r.hearts), best_combo=r.best_combo,
            powerups_used=r.powerups_used, finished_at=r.finished_at,
        )
        for r in runs[: 50 if student_id else 20]
    ]
    completed = [r for r in runs if r.status == "completed"]
    today = _today_start()
    return ClassGameResponse(
        trace_id=trace_id, students=stats, levels=levels, recent_runs=recent,
        totals={
            "runs": len(runs),
            "players": len(stats),
            "players_today": len({r.student_id for r in runs if r.finished_at and r.finished_at >= today}),
            "completion_rate": round(len(completed) / len(runs), 3) if runs else None,
            "avg_stars": round(sum(r.stars for r in completed) / len(completed), 2) if completed else None,
            "three_star_runs": sum(1 for r in completed if r.stars == 3),
        },
    )
