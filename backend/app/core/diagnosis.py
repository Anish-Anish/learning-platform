"""Core side of diagnosis: enqueue, build agent context, VALIDATE + APPLY proposals (rule 1).

The agent (LLM or deterministic) only proposes. This module decides what actually changes:
activating a misconception on the root concept or scheduling a prerequisite probe.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.diagnosis_agent import AttemptFact, ConceptFact, DiagnosisContext, diagnose
from app.core.graph import ContentGraph, get_graph, subject_of_concept
from app.core.learner_model import mastery
from app.core.student_state import load_attempts, load_rows, recompute
from app.db import models as m
from app.db.models import utcnow
from app.observability.logging import get_logger
from app.schemas.ai import DiagnosisProposal
from app.schemas.api import DiagnosisOut, NextAction

log = get_logger(__name__)

MIN_CONFIDENCE = 0.35
MAX_PROBES_PER_CHAIN = 2


def enqueue(db: Session, attempt: m.Attempt, trace_id: str, origin_concept_id: str | None) -> m.Diagnosis:
    dx = m.Diagnosis(
        trace_id=trace_id,
        student_id=attempt.student_id,
        trigger_attempt_id=attempt.id,
        failed_concept_id=attempt.concept_id,
        origin_concept_id=origin_concept_id or attempt.concept_id,
        status="pending",
    )
    db.add(dx)
    db.flush()
    return dx


def _option_text(graph: ContentGraph, qid: str, oid: str | None) -> str | None:
    q = graph.questions.get(qid)
    if not q or not oid:
        return None
    o = next((o for o in q.options if o.id == oid), None)
    return o.text if o else None


def _chain_probes(db: Session, dx: m.Diagnosis) -> list[str]:
    """Concepts already probed in this diagnosis chain (same origin, recent)."""
    items = db.scalars(
        select(m.ScheduledItem)
        .where(m.ScheduledItem.student_id == dx.student_id, m.ScheduledItem.kind == "probe")
        .order_by(m.ScheduledItem.created_at.desc())
        .limit(6)
    ).all()
    out = []
    for it in items:
        src = db.get(m.Diagnosis, it.source_id) if it.source_id else None
        if src is None or src.origin_concept_id == dx.origin_concept_id:
            out.append(it.concept_id)
    return out


def build_context(db: Session, dx: m.Diagnosis, graph: ContentGraph) -> DiagnosisContext:
    attempts = load_attempts(db, dx.student_id)
    rows = load_rows(db, dx.student_id, graph)
    recompute(rows, attempts, graph)
    trig = next(a for a in attempts if a.id == dx.trigger_attempt_id)

    def fact(a: m.Attempt) -> AttemptFact:
        return AttemptFact(
            question_id=a.question_id,
            concept_id=a.concept_id,
            correct=a.is_correct,
            confidence=a.confidence,
            option_text=_option_text(graph, a.question_id, a.option_id),
            misconception_id=a.selected_misconception_id,
            seq=a.seq,
        )

    return DiagnosisContext(
        student_ref=dx.student_id,
        failed_concept_id=dx.failed_concept_id,
        origin_concept_id=dx.origin_concept_id or dx.failed_concept_id,
        trigger=fact(trig),
        history=[fact(a) for a in attempts[-40:] if a.boss_battle_id is None],
        concepts={
            cid: ConceptFact(
                concept_id=cid,
                mastery=mastery(r.theta),
                state=r.state,
                n_attempts=r.n_attempts,
                active_misconceptions=list(r.active_misconception_ids or []),
            )
            for cid, r in rows.items()
        },
        probed_concepts=_chain_probes(db, dx),
    )


def apply_proposal(db: Session, dx: m.Diagnosis, p: DiagnosisProposal, source: str, graph: ContentGraph) -> None:
    """Deterministic validation + application. Sets dx.status to applied / rejected."""
    dx.source = source
    failed = dx.failed_concept_id
    origin = dx.origin_concept_id or failed
    allowed_roots = {failed, origin, *graph.ancestors(failed), *graph.ancestors(origin)}

    def reject(reason: str) -> None:
        dx.status = "rejected"
        dx.rejection_reason = reason
        dx.root_concept_id = p.root_concept_id if p.root_concept_id in graph.concepts else None
        dx.evidence = p.evidence[:8]
        dx.confidence = p.confidence
        dx.student_message = p.student_message
        log.info("diagnosis_rejected", diagnosis_id=dx.id, reason=reason)

    if p.root_concept_id not in graph.concepts:
        return reject("unknown root concept")
    if p.root_concept_id not in allowed_roots:
        return reject("root is not the failed concept or one of its prerequisites")
    if p.confidence < MIN_CONFIDENCE:
        return reject(f"confidence {p.confidence:.2f} below {MIN_CONFIDENCE}")

    mis = p.misconception_id if p.misconception_id in graph.misconceptions else None
    path = [c for c in p.path if c in graph.concepts] or graph.prereq_path(origin, p.root_concept_id)
    probed = _chain_probes(db, dx)
    needs_probe = bool(p.needs_probe)
    probe = p.probe_concept_id or p.root_concept_id
    if needs_probe and (probe not in allowed_roots or probe in probed or len(probed) >= MAX_PROBES_PER_CHAIN):
        needs_probe = False  # code decides: stop probing, conclude with the evidence we have

    dx.root_concept_id = p.root_concept_id
    dx.misconception_id = mis
    dx.evidence = p.evidence[:8]
    dx.path = path
    dx.confidence = round(p.confidence, 3)
    dx.needs_probe = needs_probe
    dx.probe_concept_id = probe if needs_probe else None
    dx.student_message = p.student_message
    dx.status = "applied"
    dx.applied_at = utcnow()

    if needs_probe:
        db.add(
            m.ScheduledItem(
                student_id=dx.student_id,
                kind="probe",
                concept_id=probe,
                misconception_id=mis,
                reason=f"Checking whether {graph.name(probe)} is the root of this mistake.",
                source_id=dx.id,
            )
        )
    elif mis:
        rows = load_rows(db, dx.student_id, graph)
        r = rows[p.root_concept_id]
        active = list(r.active_misconception_ids or [])
        if mis not in active:
            active.append(mis)
            r.active_misconception_ids = active
            prog = dict(r.misconception_progress or {})
            prog[mis] = 0
            r.misconception_progress = prog
    db.flush()
    log.info("diagnosis_applied", diagnosis_id=dx.id, root=dx.root_concept_id, probe=dx.probe_concept_id, source=source)


def execute(db: Session, dx: m.Diagnosis, trace_id: str) -> m.Diagnosis:
    graph = get_graph(db, subject_of_concept(db, dx.failed_concept_id))
    try:
        ctx = build_context(db, dx, graph)
        proposal, source = diagnose(ctx, graph, trace_id)
    except Exception as exc:  # never fail the student flow
        log.warning("diagnosis_failed", error=str(exc))
        from app.ai.diagnosis_agent import deterministic_diagnosis

        ctx = build_context(db, dx, graph)
        proposal, source = deterministic_diagnosis(ctx, graph), "fallback"
    apply_proposal(db, dx, proposal, source, graph)
    return dx


def run_in_background(diagnosis_id: str, trace_id: str) -> None:
    from app.db.session import SessionLocal

    with SessionLocal() as db:
        dx = db.get(m.Diagnosis, diagnosis_id)
        if dx is None or dx.status != "pending":
            return
        execute(db, dx, trace_id)
        db.commit()


def resolve_probe_success(db: Session, item: m.ScheduledItem, attempt: m.Attempt, graph: ContentGraph) -> m.Diagnosis | None:
    """A probe was answered correctly: the prerequisite looks solid, so the root is the originally failed concept."""
    dx = db.get(m.Diagnosis, item.source_id) if item.source_id else None
    if dx is None:
        return None
    failed = dx.failed_concept_id
    dx.evidence = list(dx.evidence or []) + [
        f"Correct on probe {attempt.question_id} [{graph.name(item.concept_id)}], {attempt.confidence}: "
        "that prerequisite looks solid"
    ]
    dx.root_concept_id = failed
    dx.path = [failed]
    dx.needs_probe = False
    dx.probe_concept_id = None
    dx.confidence = 0.7
    dx.student_message = (
        f"Good news: {graph.name(item.concept_id)} looks solid. The gap is in {graph.name(failed)} itself, "
        "and a short lesson will fix it."
    )
    dx.applied_at = utcnow()
    db.flush()
    return dx


def next_action_for(dx: m.Diagnosis, graph: ContentGraph) -> NextAction:
    if dx.status == "pending":
        return NextAction(kind="next_question", message="Looking for the root cause...")
    if dx.status == "rejected" or not dx.root_concept_id:
        return NextAction(kind="next_question", message="Let's keep going.")
    if dx.needs_probe and dx.probe_concept_id:
        return NextAction(kind="probe", concept_id=dx.probe_concept_id, misconception_id=dx.misconception_id,
                          message=dx.student_message or f"Let's check {graph.name(dx.probe_concept_id)}.")
    return NextAction(kind="lesson", concept_id=dx.root_concept_id, misconception_id=dx.misconception_id,
                      message=dx.student_message or f"Let's fix the root: {graph.name(dx.root_concept_id)}.")


def to_out(dx: m.Diagnosis, graph: ContentGraph, trace_id: str) -> DiagnosisOut:
    mc = graph.misconceptions.get(dx.misconception_id or "")
    return DiagnosisOut(
        trace_id=trace_id,
        id=dx.id,
        status=dx.status,  # type: ignore[arg-type]
        student_id=dx.student_id,
        trigger_attempt_id=dx.trigger_attempt_id,
        failed_concept_id=dx.failed_concept_id,
        root_concept_id=dx.root_concept_id,
        root_concept_name=graph.name(dx.root_concept_id) if dx.root_concept_id else None,
        misconception_id=dx.misconception_id,
        misconception_text=mc.description if mc else None,
        correct_belief=mc.correct_belief if mc else None,
        evidence=list(dx.evidence or []),
        path=list(dx.path or []),
        confidence=dx.confidence,
        needs_probe=dx.needs_probe,
        probe_concept_id=dx.probe_concept_id,
        student_message=dx.student_message,
        source=dx.source,
        replay_id=mc.replay_id if mc else None,
    )
