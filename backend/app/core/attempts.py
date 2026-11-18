"""Attempt processing (PROJECT_CONTEXT §4.3). One attempt = one `attempt_recorded` event.

Handlers (in order): learner model -> misconceptions -> states -> gamification -> scheduling -> diagnosis.
Everything here is deterministic. The diagnosis itself is proposed by the agent and applied by core/diagnosis.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core import diagnosis as dxmod
from app.core import gamification as gam
from app.core.events import Event, bus
from app.core.graph import ContentGraph, QuestionInfo
from app.core.learner_model import LearnerParams, classify_signal, mastery
from app.core.learner_model import update as theta_update
from app.core.states import StateResult
from app.core.student_state import (
    calibration_for,
    concept_state_out,
    load_attempts,
    load_rows,
    recompute,
    streak_days,
    unlocked_set,
)
from app.db import models as m
from app.db.models import utcnow
from app.schemas.api import AttemptResponse, BadgeOut, DiagnosisRef, NextAction


class AttemptError(ValueError):
    pass


@dataclass
class AttemptContext:
    db: Session
    graph: ContentGraph
    student: m.Student
    question: QuestionInfo
    attempt: m.Attempt
    rows: dict[str, m.MasteryState]
    attempts: list[m.Attempt]  # includes this attempt (last)
    allow_progress: bool
    boss_battle_id: str | None = None
    # snapshots
    before_unlocked: set[str] = field(default_factory=set)
    # outputs
    results: dict[str, StateResult] = field(default_factory=dict)
    cleared: list[str] = field(default_factory=list)
    awards: gam.Awards = field(default_factory=gam.Awards)
    new_badges: list[BadgeOut] = field(default_factory=list)
    diagnosis: m.Diagnosis | None = None
    probe_resolution: m.Diagnosis | None = None
    completed_item: m.ScheduledItem | None = None
    run_diagnosis_inline: bool = True


# ---------------------------------------------------------------- handlers
def handle_learner_model(ev: Event, ctx: AttemptContext) -> None:
    s = get_settings()
    a, q = ctx.attempt, ctx.question
    r = ctx.rows[q.concept_id]
    upd = theta_update(
        r.theta,
        q.b,
        a.is_correct,
        a.confidence,  # type: ignore[arg-type]
        a.hints_used,
        LearnerParams.from_settings(),
        allow_progress=ctx.allow_progress,
        update_b=s.update_question_difficulty and not ctx.student.is_simulated,
    )
    a.theta_before, a.theta_after = r.theta, upd.theta
    r.theta = upd.theta
    r.n_attempts += 1
    r.last_seen_at = utcnow()
    if upd.b != q.b:
        q.b = upd.b
        row = ctx.db.get(m.Question, q.id)
        if row is not None:
            row.difficulty_b = upd.b


def apply_misconception_rules(
    rows: dict, concept_id: str, targets: set[str], correct: bool, confidence: str, selected_mid: str | None,
    allow_progress: bool, clear_needed: int,
) -> set[str]:
    """Pure rule over row-like objects (MasteryState or replay rows). Returns misconceptions cleared.

    misconception_signal activates the option's misconception on the question's concept; 2 correct+sure
    answers on questions targeting it clear it everywhere (§9.3).
    """
    signal = classify_signal(correct, confidence)  # type: ignore[arg-type]
    if signal == "misconception_signal" and selected_mid:
        r = rows[concept_id]
        active = list(r.active_misconception_ids or [])
        if selected_mid not in active:
            active.append(selected_mid)
        r.active_misconception_ids = active
        for row in rows.values():  # reset progress wherever it is active
            if selected_mid in (row.active_misconception_ids or []):
                prog = dict(row.misconception_progress or {})
                prog[selected_mid] = 0
                row.misconception_progress = prog
        return set()
    cleared: set[str] = set()
    if correct and confidence == "sure" and allow_progress:
        for row in rows.values():
            hit = [x for x in (row.active_misconception_ids or []) if x in targets]
            if not hit:
                continue
            prog = dict(row.misconception_progress or {})
            for x in hit:
                prog[x] = int(prog.get(x, 0)) + 1
                if prog[x] >= clear_needed:
                    cleared.add(x)
            row.misconception_progress = prog
        if cleared:
            clear_misconceptions(rows, cleared)
    return cleared


def handle_misconceptions(ev: Event, ctx: AttemptContext) -> None:
    a, q = ctx.attempt, ctx.question
    cleared = apply_misconception_rules(
        ctx.rows, q.concept_id, q.targets, a.is_correct, a.confidence, a.selected_misconception_id,
        ctx.allow_progress, get_settings().misconception_clear_needed,
    )
    ctx.cleared.extend(sorted(cleared))


def clear_misconceptions(rows: dict, mids: set[str]) -> None:
    for row in rows.values():
        active = [x for x in (row.active_misconception_ids or []) if x not in mids]
        if len(active) != len(row.active_misconception_ids or []):
            row.active_misconception_ids = active
            prog = {k: v for k, v in (row.misconception_progress or {}).items() if k not in mids}
            row.misconception_progress = prog


def handle_states(ev: Event, ctx: AttemptContext) -> None:
    ctx.results = recompute(ctx.rows, ctx.attempts, ctx.graph)


def compute_awards(
    db: Session,
    graph: ContentGraph,
    student_id: str,
    rows: dict[str, m.MasteryState],
    results: dict[str, StateResult],
    before_unlocked: set[str],
    cleared: list[str],
) -> gam.Awards:
    """Mastery / misconception / unlock / root-finder awards shared by attempts and boss wins."""
    awards = gam.Awards()
    newly_mastered = []
    for cid, res in results.items():
        r = rows[cid]
        if res.state == "mastered" and not r.ever_mastered:
            r.ever_mastered = True
            newly_mastered.append((cid, graph.name(cid)))
    awards.extend(gam.mastery_awards(newly_mastered))

    had_cleared = db.scalar(
        select(m.XPEvent.id).where(m.XPEvent.student_id == student_id, m.XPEvent.kind == "misconception_cleared").limit(1)
    ) is not None
    cleared_desc = [(mid, graph.misconceptions[mid].description if mid in graph.misconceptions else mid) for mid in cleared]
    awards.extend(gam.misconception_awards(cleared_desc, had_cleared))

    now_unlocked = unlocked_set(rows, graph)
    newly = []
    for cid in sorted(now_unlocked - before_unlocked, key=lambda c: graph.concepts[c].depth):
        r = rows[cid]
        if not r.ever_unlocked:
            r.ever_unlocked = True
            newly.append((cid, graph.name(cid)))
    prereq_names = {cid: [graph.name(p) for p in graph.concepts[cid].prerequisites] for cid, _ in newly}
    awards.extend(gam.unlock_awards(newly, prereq_names))

    # Root Finder: a diagnosed root gets fixed (its misconception cleared, or the root concept mastered).
    applied = db.scalars(
        select(m.Diagnosis).where(
            m.Diagnosis.student_id == student_id, m.Diagnosis.status == "applied", m.Diagnosis.needs_probe.is_(False)
        )
    ).all()
    mastered_now = {cid for cid, _ in newly_mastered}
    if any(d.misconception_id in cleared or d.root_concept_id in mastered_now for d in applied):
        awards.badges.append("root_finder")
    return awards


def handle_gamification(ev: Event, ctx: AttemptContext) -> None:
    db, graph, sid = ctx.db, ctx.graph, ctx.student.id
    awards = compute_awards(db, graph, sid, ctx.rows, ctx.results, ctx.before_unlocked, ctx.cleared)
    awards.extend(gam.hint_awards(ctx.attempt.hints_used))
    dates = [a.created_at.date() for a in ctx.attempts if a.created_at]
    today = ctx.attempt.created_at.date()
    awards.extend(gam.streak_awards(dates, today, streak_days(dates, today)))
    cal = calibration_for(ctx.attempts)
    awards.extend(gam.calibration_awards(cal.n, cal.score))
    ctx.awards = awards
    ctx.new_badges = gam.persist_awards(db, sid, awards)


def handle_scheduling(ev: Event, ctx: AttemptContext) -> None:
    if ctx.boss_battle_id:
        return
    items = ctx.db.scalars(
        select(m.ScheduledItem).where(
            m.ScheduledItem.student_id == ctx.student.id,
            m.ScheduledItem.status == "pending",
            m.ScheduledItem.question_id == ctx.question.id,
        )
    ).all()
    for it in items:
        it.status = "done"
        ctx.completed_item = it
        if it.kind == "probe" and ctx.attempt.is_correct:
            ctx.probe_resolution = dxmod.resolve_probe_success(ctx.db, it, ctx.attempt, ctx.graph)


def handle_diagnosis_trigger(ev: Event, ctx: AttemptContext) -> None:
    """Trigger: wrong answer or misconception_signal (§10.4). Not during boss battles."""
    if ctx.boss_battle_id or ctx.attempt.is_correct:
        return
    origin = None
    it = ctx.completed_item
    if it is not None and it.kind == "probe" and it.source_id:
        src = ctx.db.get(m.Diagnosis, it.source_id)
        origin = src.origin_concept_id if src else None
    dx = dxmod.enqueue(ctx.db, ctx.attempt, ev.trace_id, origin)
    ctx.diagnosis = dx
    if ctx.run_diagnosis_inline:
        dxmod.execute(ctx.db, dx, ev.trace_id)


bus.subscribe("attempt_recorded", handle_learner_model, order=10)
bus.subscribe("attempt_recorded", handle_misconceptions, order=20)
bus.subscribe("attempt_recorded", handle_states, order=30)
bus.subscribe("attempt_recorded", handle_gamification, order=40)
bus.subscribe("attempt_recorded", handle_scheduling, order=50)
bus.subscribe("attempt_recorded", handle_diagnosis_trigger, order=60)


# ---------------------------------------------------------------- orchestrator
def grade(q: QuestionInfo, option_id: str | None, answer_text: str | None) -> tuple[bool, str | None]:
    """Return (is_correct, selected_misconception_id)."""
    if q.type == "mcq":
        opt = next((o for o in q.options if o.id == option_id), None)
        if opt is None:
            raise AttemptError(f"option {option_id!r} not in question {q.id}")
        return opt.is_correct, (opt.misconception_id if not opt.is_correct else None)
    correct = q.correct_option
    norm = (answer_text or "").strip().lower()
    return bool(correct and norm == correct.text.strip().lower()), None


def farming_allowed(recent: list, question_id: str) -> bool:
    """True if `question_id` may award progress given the recent attempts (objects with question_id/is_correct)."""
    return not any(a.question_id == question_id and a.is_correct for a in recent)


def process_attempt(
    db: Session,
    graph: ContentGraph,
    *,
    student: m.Student,
    question_id: str,
    option_id: str | None,
    answer_text: str | None,
    confidence: str,
    time_ms: int,
    hints_used: int,
    reasoning_text: str | None,
    session_id: str | None,
    trace_id: str,
    boss_battle_id: str | None = None,
    run_diagnosis_inline: bool = True,
) -> AttemptContext:
    s = get_settings()
    q = graph.questions.get(question_id)
    if q is None:
        raise AttemptError(f"unknown question {question_id}")
    is_correct, sel_mis = grade(q, option_id, answer_text)

    attempts = load_attempts(db, student.id)
    rows = load_rows(db, student.id, graph)
    # Anti-farming (§9.5): no progress for re-answering a question answered *correctly* in the last 10 attempts.
    # Re-trying a question you got wrong is retrieval practice (used by boss battles), so it may count.
    allow_progress = farming_allowed(attempts[-s.recent_window :], question_id)
    before_unlocked = unlocked_set(rows, graph)

    a = m.Attempt(
        trace_id=trace_id,
        seq=(attempts[-1].seq + 1) if attempts else 1,
        student_id=student.id,
        session_id=session_id,
        question_id=question_id,
        concept_id=q.concept_id,
        option_id=option_id,
        answer_text=answer_text,
        is_correct=is_correct,
        confidence=confidence,
        reasoning_text=reasoning_text,
        time_ms=time_ms,
        hints_used=hints_used,
        selected_misconception_id=sel_mis,
        boss_battle_id=boss_battle_id,
        progress_awarded=allow_progress,
        created_at=utcnow(),
    )
    db.add(a)
    db.flush()
    ctx = AttemptContext(
        db=db, graph=graph, student=student, question=q, attempt=a, rows=rows, attempts=[*attempts, a],
        allow_progress=allow_progress, boss_battle_id=boss_battle_id, before_unlocked=before_unlocked,
        run_diagnosis_inline=run_diagnosis_inline,
    )
    bus.publish(Event("attempt_recorded", trace_id, student.id, {"attempt_id": a.id}), ctx)
    db.flush()
    return ctx


def next_action(ctx: AttemptContext) -> NextAction:
    g = ctx.graph
    if ctx.diagnosis is not None:
        return dxmod.next_action_for(ctx.diagnosis, g)
    if ctx.probe_resolution is not None:
        return dxmod.next_action_for(ctx.probe_resolution, g)
    if ctx.cleared:
        return NextAction(kind="boss", message="Misconception cleared! Face the Root Boss to lock it in for good.")
    return NextAction(kind="next_question", message="Nice, keep going." if ctx.attempt.is_correct else "Let's keep going.")


def to_response(ctx: AttemptContext, trace_id: str) -> AttemptResponse:
    a, q, g = ctx.attempt, ctx.question, ctx.graph
    correct = q.correct_option
    dx = ctx.diagnosis or ctx.probe_resolution
    return AttemptResponse(
        trace_id=trace_id,
        attempt_id=a.id,
        is_correct=a.is_correct,
        correct_option_id=correct.id if correct else None,
        explanation=q.explanation,
        signal=classify_signal(a.is_correct, a.confidence),  # type: ignore[arg-type]
        selected_misconception_id=a.selected_misconception_id,
        progress_awarded=a.progress_awarded,
        concept_state=concept_state_out(q.concept_id, ctx.rows, ctx.results, g),
        xp_events=[x for x in ctx.awards.xp],
        unlocks=ctx.awards.unlocks,
        badges=ctx.new_badges,
        cleared_misconception_ids=ctx.cleared,
        diagnosis=DiagnosisRef(status=dx.status, id=dx.id) if dx else DiagnosisRef(),  # type: ignore[arg-type]
        next_action=next_action(ctx),
    )


def mastery_snapshot(rows: dict[str, m.MasteryState]) -> dict[str, float]:
    return {cid: mastery(r.theta) for cid, r in rows.items()}
