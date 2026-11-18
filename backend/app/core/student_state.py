"""Loading / recomputing a student's per-concept state from the DB."""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.graph import ContentGraph
from app.core.learner_model import calibration, mastery
from app.core.states import AttemptLite, StateResult, StateThresholds, classify
from app.db import models as m
from app.schemas.api import ConceptStateOut, StudentSummary

XP_PER_LEVEL = 250


def pseudonym_display_name(student_id: str) -> str:
    return "Demo Student" if student_id.startswith("demo") else f"Student {student_id[-4:]}"


def insert_ignore(db: Session, model: type, values: list[dict]) -> None:
    """INSERT ... ON CONFLICT DO NOTHING — safe when two requests create the same rows concurrently
    (e.g. React StrictMode firing POST /session/start twice)."""
    if not values:
        return
    dialect = db.get_bind().dialect.name
    if dialect == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    else:
        from sqlalchemy.dialects.sqlite import insert
    db.execute(insert(model).values(values).on_conflict_do_nothing())


def get_or_create_student(
    db: Session, student_id: str, display_name: str | None = None, is_simulated: bool = False
) -> m.Student:
    s = db.get(m.Student, student_id)
    if s is None:
        insert_ignore(db, m.Student, [{
            "id": student_id,
            "display_name": display_name or pseudonym_display_name(student_id),
            "is_simulated": is_simulated,
            "created_at": m.utcnow(),
        }])
        s = db.get(m.Student, student_id)
        assert s is not None
    return s


def load_rows(db: Session, student_id: str, graph: ContentGraph) -> dict[str, m.MasteryState]:
    q = select(m.MasteryState).where(m.MasteryState.student_id == student_id)
    rows = {r.concept_id: r for r in db.scalars(q)}
    missing = [
        {
            "student_id": student_id,
            "concept_id": cid,
            "theta": 0.0,
            "n_attempts": 0,
            "state": "not_started" if not c.prerequisites else "locked",
            "active_misconception_ids": [],
            "misconception_progress": {},
            "ever_mastered": False,
            "ever_unlocked": not c.prerequisites,
            "review_strength": 3.0,
        }
        for cid, c in graph.concepts.items()
        if cid not in rows
    ]
    if missing:
        insert_ignore(db, m.MasteryState, missing)
        rows = {r.concept_id: r for r in db.scalars(q)}
    return rows


def load_attempts(db: Session, student_id: str) -> list[m.Attempt]:
    return list(
        db.scalars(select(m.Attempt).where(m.Attempt.student_id == student_id).order_by(m.Attempt.seq)).all()
    )


def attempts_by_concept(attempts: list[m.Attempt]) -> dict[str, list[AttemptLite]]:
    out: dict[str, list[AttemptLite]] = {}
    for a in attempts:
        out.setdefault(a.concept_id, []).append(AttemptLite(a.is_correct, a.confidence))
    return out


def prereq_mastery(cid: str, rows: dict[str, m.MasteryState], graph: ContentGraph) -> dict[str, float]:
    return {p: mastery(rows[p].theta) for p in graph.concepts[cid].prerequisites}


def recompute(
    rows: dict[str, m.MasteryState], attempts: list[m.Attempt], graph: ContentGraph
) -> dict[str, StateResult]:
    t = StateThresholds.from_settings()
    by_c = attempts_by_concept(attempts)
    names = graph.names()
    results: dict[str, StateResult] = {}
    for cid in graph.topo_order:
        r = rows[cid]
        res = classify(
            m=mastery(r.theta),
            n_attempts=r.n_attempts,
            recent=by_c.get(cid, []),
            active_misconceptions=r.active_misconception_ids or [],
            prereq_mastery=prereq_mastery(cid, rows, graph),
            thresholds=t,
            names=names,
        )
        r.state = res.state
        results[cid] = res
    return results


def unlocked_set(rows: dict[str, m.MasteryState], graph: ContentGraph) -> set[str]:
    """Concepts (with prerequisites) whose prerequisites all reached the unlock threshold."""
    t = StateThresholds.from_settings()
    return {
        cid
        for cid, c in graph.concepts.items()
        if c.prerequisites and all(mastery(rows[p].theta) >= t.unlock for p in c.prerequisites)
    }


def concept_state_out(
    cid: str, rows: dict[str, m.MasteryState], results: dict[str, StateResult], graph: ContentGraph
) -> ConceptStateOut:
    r = rows[cid]
    return ConceptStateOut(
        concept_id=cid,
        concept_name=graph.name(cid),
        state=results[cid].state,
        mastery=round(mastery(r.theta), 4),
        n_attempts=r.n_attempts,
        active_misconception_ids=list(r.active_misconception_ids or []),
        reason=results[cid].reason,
    )


def xp_total(db: Session, student_id: str) -> int:
    return int(db.scalar(select(func.coalesce(func.sum(m.XPEvent.amount), 0)).where(m.XPEvent.student_id == student_id)))


def streak_days(attempt_dates: list[date], today: date | None = None) -> int:
    """Consecutive days with at least one attempt, ending today (or yesterday)."""
    if not attempt_dates:
        return 0
    days = set(attempt_dates)
    today = today or max(days)
    cur = today if today in days else today - timedelta(days=1)
    n = 0
    while cur in days:
        n += 1
        cur -= timedelta(days=1)
    return n


def student_summary(db: Session, student: m.Student) -> StudentSummary:
    xp = xp_total(db, student.id)
    dates = [
        d.date()
        for d in db.scalars(select(m.Attempt.created_at).where(m.Attempt.student_id == student.id)).all()
        if d is not None
    ]
    return StudentSummary(
        id=student.id,
        display_name=student.display_name,
        xp_total=xp,
        level=1 + max(0, xp) // XP_PER_LEVEL,
        streak_days=streak_days(dates),
        is_simulated=student.is_simulated,
    )


def calibration_for(attempts: list[m.Attempt]):
    return calibration((a.is_correct, a.confidence) for a in attempts)
