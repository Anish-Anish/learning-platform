"""GET /admin/metrics, GET /admin/traces, POST /feedback (§14)."""

from __future__ import annotations

import json
from collections import defaultdict

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.llm_client import llm_mode
from app.api.deps import get_db, graph_dep, trace_id
from app.config import EVAL_RESULTS_DIR
from app.core.graph import ContentGraph
from app.core.learner_model import calibration, mastery, p_correct
from app.core.quality import detection_stats, verifier_pass_rate
from app.db import models as m
from app.observability import writer
from app.observability.metrics import percentile
from app.schemas.api import (
    AdminMetricsResponse,
    FeatureCost,
    FeedbackRequest,
    FeedbackResponse,
    LatencyStat,
    LLMCallOut,
    QuestionHealth,
    TracesResponse,
)

router = APIRouter(tags=["admin"])


def latest_eval() -> dict | None:
    files = sorted(EVAL_RESULTS_DIR.glob("*.json"))
    if not files:
        return None
    try:
        return json.loads(files[-1].read_text())
    except Exception:
        return None


@router.get("/admin/metrics", response_model=AdminMetricsResponse)
def admin_metrics(db: Session = Depends(get_db), graph: ContentGraph = Depends(graph_dep),
                  tid: str = Depends(trace_id)) -> AdminMetricsResponse:
    writer.flush()  # include telemetry still queued for the background writer
    # ---------------- system: endpoint latency
    reqs = db.execute(select(m.RequestMetric.route, m.RequestMetric.latency_ms, m.RequestMetric.status_code)).all()
    by_route: dict[str, list[tuple[float, int]]] = defaultdict(list)
    for route, lat, code in reqs:
        by_route[route].append((lat, code))
    endpoints = sorted(
        (
            LatencyStat(
                name=r, count=len(v), p50_ms=percentile([x for x, _ in v], 50), p95_ms=percentile([x for x, _ in v], 95),
                error_rate=round(sum(1 for _, c in v if c >= 500) / len(v), 4),
            )
            for r, v in by_route.items()
        ),
        key=lambda s: -s.count,
    )
    all_lat = [lat for lat, _ in (x for v in by_route.values() for x in v)]

    # ---------------- LLM features
    calls = db.scalars(select(m.LLMCall)).all()
    by_feat: dict[str, list[m.LLMCall]] = defaultdict(list)
    for c in calls:
        by_feat[c.feature].append(c)
    features = []
    for f, cs in sorted(by_feat.items()):
        lats = [c.latency_ms for c in cs]
        features.append(FeatureCost(
            feature=f, calls=len(cs), input_tokens=sum(c.input_tokens for c in cs),
            output_tokens=sum(c.output_tokens for c in cs), cost_usd=round(sum(c.cost_usd for c in cs), 5),
            p50_ms=percentile(lats, 50), p95_ms=percentile(lats, 95),
            fallback_rate=round(sum(c.fallback_used for c in cs) / len(cs), 3),
            cache_hit_rate=round(sum(c.cache_hit for c in cs) / len(cs), 3),
        ))
    n_calls = len(calls) or 1
    flags_count: dict[str, int] = defaultdict(int)
    for c in calls:
        for fl in c.guardrail_flags or []:
            flags_count[fl] += 1

    # ---------------- cost
    sessions = db.scalar(select(func.count(m.Session.id))) or 0
    students_n = db.scalar(select(func.count(m.Student.id))) or 0
    total_cost = sum(c.cost_usd for c in calls)
    total_tokens = sum(c.input_tokens + c.output_tokens for c in calls)

    # ---------------- learning outcomes
    attempts = db.scalars(select(m.Attempt)).all()
    sess_gain: dict[str, float] = defaultdict(float)
    for a in attempts:
        if a.session_id:
            sess_gain[a.session_id] += mastery(a.theta_after) - mastery(a.theta_before)
    sess_counts: dict[str, int] = defaultdict(int)
    for a in attempts:
        if a.session_id:
            sess_counts[a.session_id] += 1
    cal = calibration((a.is_correct, a.confidence) for a in attempts)
    cleared = db.scalar(select(func.count(m.XPEvent.id)).where(m.XPEvent.kind == "misconception_cleared")) or 0
    mastered_rows = db.scalars(select(m.MasteryState).where(m.MasteryState.ever_mastered.is_(True))).all()
    off_topic = 0
    for t in db.scalars(select(m.TeachSession)).all():
        off_topic += sum(1 for turn in t.transcript or [] if turn.get("role") == "bot" and turn.get("on_topic") is False)
    student_flags: dict[str, int] = defaultdict(int)
    for t in db.scalars(select(m.TeachSession)).all():
        for turn in t.transcript or []:
            for fl in turn.get("flags", []) if turn.get("role") == "student" else []:
                student_flags[fl] += 1

    # ---------------- AI quality
    det = detection_stats(db)
    ver = verifier_pass_rate(db)
    ev = latest_eval() or {}
    dx_rows = db.scalars(select(m.Diagnosis)).all()

    # ---------------- question health
    by_q: dict[str, list[m.Attempt]] = defaultdict(list)
    for a in attempts:
        by_q[a.question_id].append(a)
    reports = defaultdict(int)
    for fb in db.scalars(select(m.Feedback).where(m.Feedback.target_kind == "question")):
        reports[fb.target_id] += 1
    health = []
    for qid, atts in by_q.items():
        q = graph.questions.get(qid)
        if q is None or len(atts) < 5:
            continue
        obs = sum(a.is_correct for a in atts) / len(atts)
        pred = sum(p_correct(a.theta_before, q.b) for a in atts) / len(atts)
        picked = {a.option_id for a in atts}
        never = [o.id for o in q.options if not o.is_correct and o.id not in picked] if len(atts) >= 8 else []
        flag = "too_easy" if obs - pred > 0.25 else "too_hard" if pred - obs > 0.25 else "ok"
        health.append(QuestionHealth(question_id=qid, concept_id=q.concept_id, attempts=len(atts),
                                     observed_success=round(obs, 3), predicted_success=round(pred, 3), flag=flag,
                                     never_picked_options=never, reports=reports.get(qid, 0)))
    health.sort(key=lambda h: (h.flag == "ok", -abs(h.observed_success - h.predicted_success)))

    return AdminMetricsResponse(
        trace_id=tid,
        llm_mode=llm_mode(),
        system={
            "requests": len(all_lat),
            "p50_ms": percentile(all_lat, 50),
            "p95_ms": percentile(all_lat, 95),
            "error_rate": round(sum(1 for v in by_route.values() for _, c in v if c >= 500) / max(1, len(all_lat)), 4),
            "llm_calls": len(calls),
            "cache_hit_rate": round(sum(c.cache_hit for c in calls) / n_calls, 3),
            "schema_failure_rate": round(sum(not c.schema_ok for c in calls) / n_calls, 3),
            "retry_rate": round(sum(c.retries > 0 for c in calls) / n_calls, 3),
            "fallback_rate": round(sum(c.fallback_used for c in calls) / n_calls, 3),
        },
        endpoints=endpoints[:20],
        features=features,
        cost={
            "total_usd": round(total_cost, 5),
            "total_tokens": total_tokens,
            "sessions": sessions,
            "students": students_n,
            "usd_per_session": round(total_cost / sessions, 6) if sessions else None,
            "usd_per_student": round(total_cost / students_n, 6) if students_n else None,
            "tokens_per_session": round(total_tokens / sessions, 1) if sessions else None,
        },
        ai_quality={
            "root_gap_detection": det["accuracy"],
            "root_gap_detected": det["detected"],
            "root_gap_planted": det["planted"],
            "root_gap_detection_exercised": det["accuracy_exercised"],
            "root_concept_accuracy": det["root_concept_accuracy"],
            "verifier_pass_rate": ver["pass_rate"],
            "verifier_checked": ver["checked"],
            "grounding_failures": flags_count.get("grounding_failure", 0),
            "answer_leakage_blocked": flags_count.get("answer_leakage", 0),
            "teach_score_agreement": (ev.get("teach_scorer") or {}).get("agreement_within_15"),
            "diagnoses_total": len(dx_rows),
            "diagnoses_rejected": sum(1 for d in dx_rows if d.status == "rejected"),
            "diagnoses_llm": sum(1 for d in dx_rows if d.source == "llm"),
            "last_eval_at": ev.get("timestamp"),
        },
        safety={
            "moderation_flags": flags_count.get("moderation_flagged", 0) + student_flags.get("moderation_flagged", 0),
            "injection_attempts_blocked": flags_count.get("injection_attempt", 0) + student_flags.get("injection_attempt", 0),
            "off_topic_redirects": off_topic,
            "pii_scrubbed": sum(v for k, v in {**flags_count, **student_flags}.items() if k.startswith("pii_")),
            "budget_exceeded": flags_count.get("budget_exceeded", 0),
        },
        learning={
            "attempts": len(attempts),
            "mastery_gain_per_session": round(sum(sess_gain.values()) / len(sess_gain), 4) if sess_gain else None,
            "misconceptions_cleared": cleared,
            "concepts_mastered": len(mastered_rows),
            "avg_attempts_to_mastery": round(sum(r.n_attempts for r in mastered_rows) / len(mastered_rows), 2)
            if mastered_rows else None,
            "calibration": round(cal.score, 3) if cal.score is not None else None,
            "drop_off_rate": round(sum(1 for n in sess_counts.values() if n < 5) / len(sess_counts), 3)
            if sess_counts else None,
            "eval_mastery_gain_vs_control": (ev.get("mastery") or {}).get("gain_vs_control"),
        },
        question_health=health[:25],
    )


@router.get("/admin/traces", response_model=TracesResponse)
def admin_traces(limit: int = Query(default=50, ge=1, le=500), feature: str | None = None,
                 db: Session = Depends(get_db), tid: str = Depends(trace_id)) -> TracesResponse:
    q = select(m.LLMCall).order_by(m.LLMCall.created_at.desc()).limit(limit)
    if feature:
        q = q.where(m.LLMCall.feature == feature)
    rows = db.scalars(q).all()
    return TracesResponse(
        trace_id=tid,
        calls=[
            LLMCallOut(id=r.id, trace_id=r.trace_id, feature=r.feature, prompt_name=r.prompt_name,
                       prompt_version=r.prompt_version, model=r.model, input_tokens=r.input_tokens,
                       output_tokens=r.output_tokens, latency_ms=r.latency_ms, cost_usd=r.cost_usd,
                       schema_ok=r.schema_ok, retries=r.retries, fallback_used=r.fallback_used,
                       guardrail_flags=list(r.guardrail_flags or []), cache_hit=r.cache_hit, created_at=r.created_at)
            for r in rows
        ],
    )


@router.post("/feedback", response_model=FeedbackResponse)
def post_feedback(body: FeedbackRequest, db: Session = Depends(get_db), tid: str = Depends(trace_id)) -> FeedbackResponse:
    from app.guardrails.pii import scrub

    comment = scrub(body.comment)[0] if body.comment else None
    fb = m.Feedback(student_id=body.student_id, target_kind=body.target_kind, target_id=body.target_id,
                    rating=body.rating, comment=comment, status="open" if body.rating <= 0 else "closed")
    db.add(fb)
    db.commit()
    return FeedbackResponse(trace_id=tid, id=fb.id, queued_for_review=fb.status == "open")
