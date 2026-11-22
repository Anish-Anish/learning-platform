"""Admin observability API (§14): metrics, LLM traces, logs, telemetry status; plus POST /feedback.

Every metric is computed from stored events inside the requested window (`?window=1h|24h|7d|30d|all`).
A few are inherently all-time and labelled so: simulator ground truth, mastery state, question health.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import String, cast, func, select
from sqlalchemy.orm import Session

from app.ai.llm_client import llm_mode
from app.api.deps import get_db, graph_dep, trace_id
from app.config import EVAL_RESULTS_DIR, get_settings
from app.core.graph import ContentGraph
from app.core.learner_model import calibration, mastery, p_correct
from app.core.quality import detection_stats, verifier_pass_rate
from app.db import models as m
from app.observability import otel, writer
from app.observability.metrics import percentile
from app.schemas.api import (
    AdminMetricsResponse,
    ExportHealth,
    FeatureCost,
    FeedbackRequest,
    FeedbackResponse,
    LatencyStat,
    LLMCallOut,
    LogEntryOut,
    LogsResponse,
    MetricsWindow,
    QuestionHealth,
    TelemetryStatus,
    TimeBucket,
    TracesResponse,
)

router = APIRouter(tags=["admin"])

WINDOWS: dict[str, timedelta | None] = {
    "1h": timedelta(hours=1), "24h": timedelta(days=1), "7d": timedelta(days=7), "30d": timedelta(days=30), "all": None,
}
BUCKETS: dict[str, timedelta] = {
    "1h": timedelta(minutes=5), "24h": timedelta(hours=1), "7d": timedelta(hours=6), "30d": timedelta(days=1),
}
LEVELS = ["debug", "info", "warning", "error", "critical"]
GUARD_DROP_KEYS = ("output_injection", "card_dropped_output_injection", "card_dropped_grounding_failure",
                   "notes_grounding_fallback")


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _start(window: str) -> datetime | None:
    delta = WINDOWS[window]
    return _now() - delta if delta else None


def _since(col, start: datetime | None):
    return col >= start if start is not None else col.is_not(None)


def latest_eval() -> dict | None:
    files = sorted(EVAL_RESULTS_DIR.glob("*.json"))
    if not files:
        return None
    try:
        return json.loads(files[-1].read_text(encoding="utf-8"))
    except Exception:
        return None


def _rate(n: float, d: float, digits: int = 4) -> float | None:
    return round(n / d, digits) if d else None


def _timeseries(window: str, start: datetime | None, reqs, calls) -> list[TimeBucket]:
    times = [r[3] for r in reqs] + [c.created_at for c in calls]
    if not times:
        return []
    begin = start or min(times)
    step = BUCKETS.get(window) or max(timedelta(hours=1), (_now() - begin) / 30)
    n = min(60, int((_now() - begin) / step) + 1)
    buckets = [{"lat": [], "err": 0, "calls": 0, "cost": 0.0} for _ in range(n)]

    def idx(t: datetime) -> int:
        return min(n - 1, max(0, int((t - begin) / step)))

    for _route, lat, code, created in reqs:
        b = buckets[idx(created)]
        b["lat"].append(lat)
        b["err"] += code >= 500
    for c in calls:
        b = buckets[idx(c.created_at)]
        b["calls"] += 1
        b["cost"] += c.cost_usd
    return [TimeBucket(start=begin + i * step, requests=len(b["lat"]), errors=b["err"],
                       p95_ms=percentile(b["lat"], 95) if b["lat"] else None,
                       llm_calls=b["calls"], cost_usd=round(b["cost"], 6)) for i, b in enumerate(buckets)]


@router.get("/admin/metrics", response_model=AdminMetricsResponse)
def admin_metrics(window: MetricsWindow = Query(default="all"), db: Session = Depends(get_db),
                  graph: ContentGraph = Depends(graph_dep), tid: str = Depends(trace_id)) -> AdminMetricsResponse:
    writer.flush()  # include telemetry still queued for the background writer
    start = _start(window)

    # ---------------- HTTP
    reqs = db.execute(select(m.RequestMetric.route, m.RequestMetric.latency_ms, m.RequestMetric.status_code,
                             m.RequestMetric.created_at).where(_since(m.RequestMetric.created_at, start))).all()
    by_route: dict[str, list[tuple[float, int]]] = defaultdict(list)
    for route, lat, code, _ in reqs:
        by_route[route].append((lat, code))
    endpoints = sorted(
        (LatencyStat(name=r, count=len(v), p50_ms=percentile([x for x, _ in v], 50),
                     p95_ms=percentile([x for x, _ in v], 95),
                     error_rate=round(sum(1 for _, c in v if c >= 500) / len(v), 4))
         for r, v in by_route.items()),
        key=lambda s: -s.count,
    )
    lats = [r[1] for r in reqs]
    codes = Counter(r[2] for r in reqs)
    n_req = len(reqs)
    span_min = ((_now() - (start or min((r[3] for r in reqs), default=_now()))).total_seconds() / 60) or 1

    # ---------------- LLM
    calls = db.scalars(select(m.LLMCall).where(_since(m.LLMCall.created_at, start))).all()
    by_feat: dict[str, list[m.LLMCall]] = defaultdict(list)
    for c in calls:
        by_feat[c.feature].append(c)
    features = [
        FeatureCost(feature=f, calls=len(cs), input_tokens=sum(c.input_tokens for c in cs),
                    output_tokens=sum(c.output_tokens for c in cs), cost_usd=round(sum(c.cost_usd for c in cs), 5),
                    p50_ms=percentile([c.latency_ms for c in cs if not c.cache_hit], 50),
                    p95_ms=percentile([c.latency_ms for c in cs if not c.cache_hit], 95),
                    fallback_rate=round(sum(c.fallback_used for c in cs) / len(cs), 3),
                    cache_hit_rate=round(sum(c.cache_hit for c in cs) / len(cs), 3))
        for f, cs in sorted(by_feat.items(), key=lambda kv: -len(kv[1]))
    ]
    flags = Counter(fl for c in calls for fl in (c.guardrail_flags or []))
    live = [c for c in calls if "offline" not in (c.guardrail_flags or [])]
    learner = [c for c in calls if c.scope != "studio"]
    studio_calls = [c for c in calls if c.scope == "studio"]

    # ---------------- learners
    sessions = db.scalar(select(func.count(m.Session.id)).where(_since(m.Session.started_at, start))) or 0
    attempts = db.scalars(select(m.Attempt).where(_since(m.Attempt.created_at, start))).all()
    active_students = len({a.student_id for a in attempts})
    learner_cost = sum(c.cost_usd for c in learner)
    learner_tokens = sum(c.input_tokens + c.output_tokens for c in learner)
    sess_gain: dict[str, float] = defaultdict(float)
    sess_counts: Counter = Counter()
    for a in attempts:
        if a.session_id:
            sess_gain[a.session_id] += mastery(a.theta_after) - mastery(a.theta_before)
            sess_counts[a.session_id] += 1
    cal = calibration((a.is_correct, a.confidence) for a in attempts)
    cleared = db.scalar(select(func.count(m.XPEvent.id)).where(
        m.XPEvent.kind == "misconception_cleared", _since(m.XPEvent.created_at, start))) or 0
    mastered_rows = db.scalars(select(m.MasteryState).where(m.MasteryState.ever_mastered.is_(True))).all()
    teach = db.scalars(select(m.TeachSession).where(_since(m.TeachSession.created_at, start))).all()
    off_topic = sum(1 for t in teach for turn in t.transcript or []
                    if turn.get("role") == "bot" and turn.get("on_topic") is False)
    student_flags = Counter(fl for t in teach for turn in t.transcript or [] if turn.get("role") == "student"
                            for fl in turn.get("flags", []))

    # ---------------- studio
    jobs = db.scalars(select(m.StudioJob).where(_since(m.StudioJob.created_at, start))).all()
    finished = [j for j in jobs if j.status in ("done", "failed")]
    durations = [(j.finished_at - j.created_at).total_seconds() for j in finished if j.finished_at]
    job_stats = [j.stats or {} for j in jobs if j.status == "done"]
    guard = Counter()
    for st in job_stats:
        guard.update({k: int(v) for k, v in (st.get("guardrails") or {}).items() if isinstance(v, (int, float))})
    docs = db.scalars(select(m.SourceDocument).where(_since(m.SourceDocument.created_at, start))).all()
    subjects = Counter(s for s in db.scalars(select(m.Subject.status)))

    # ---------------- AI quality
    det = detection_stats(db)
    ver = verifier_pass_rate(db)
    ev = latest_eval() or {}
    dx_rows = db.scalars(select(m.Diagnosis).where(_since(m.Diagnosis.created_at, start))).all()

    # ---------------- question health (all-time: needs volume)
    by_q: dict[str, list[m.Attempt]] = defaultdict(list)
    for a in db.scalars(select(m.Attempt).where(m.Attempt.question_id.in_(list(graph.questions)))):
        by_q[a.question_id].append(a)
    reports = Counter(fb.target_id for fb in db.scalars(select(m.Feedback).where(m.Feedback.target_kind == "question")))
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
        trace_id=tid, window=window, window_start=start, generated_at=_now(), llm_mode=llm_mode(),
        system={
            "requests": n_req,
            "requests_per_min": round(n_req / span_min, 2) if n_req else 0,
            "p50_ms": percentile(lats, 50),
            "p95_ms": percentile(lats, 95),
            "p99_ms": percentile(lats, 99),
            "error_rate": _rate(sum(v for k, v in codes.items() if k >= 500), n_req),
            "client_error_rate": _rate(sum(v for k, v in codes.items() if 400 <= k < 500), n_req),
            "llm_calls": len(calls),
            "llm_calls_live": len(live),
            "cache_hit_rate": _rate(sum(c.cache_hit for c in calls), len(calls), 3),
            "schema_failure_rate": _rate(sum(not c.schema_ok for c in live), len(live), 3),
            "retry_rate": _rate(sum(c.retries > 0 for c in live), len(live), 3),
            "fallback_rate": _rate(sum(c.fallback_used for c in calls), len(calls), 3),
            "live_fallback_rate": _rate(sum(c.fallback_used for c in live), len(live), 3),
            "llm_p95_ms": percentile([c.latency_ms for c in live if not c.cache_hit], 95),
        },
        endpoints=endpoints[:25],
        features=features,
        cost={
            "total_usd": round(sum(c.cost_usd for c in calls), 5),
            "learner_usd": round(learner_cost, 5),
            "studio_usd": round(sum(c.cost_usd for c in studio_calls), 5),
            "total_tokens": sum(c.input_tokens + c.output_tokens for c in calls),
            "sessions": sessions,
            "active_students": active_students,
            "students_total": db.scalar(select(func.count(m.Student.id))) or 0,
            "usd_per_session": round(learner_cost / sessions, 6) if sessions else None,
            "usd_per_active_student": round(learner_cost / active_students, 6) if active_students else None,
            "tokens_per_session": round(learner_tokens / sessions, 1) if sessions else None,
        },
        ai_quality={
            "root_gap_detection": det["accuracy"],
            "root_gap_detected": det["detected"],
            "root_gap_planted": det["planted"],
            "root_gap_detection_exercised": det["accuracy_exercised"],
            "root_concept_accuracy": det["root_concept_accuracy"],
            "verifier_pass_rate": ver["pass_rate"],
            "verifier_checked": ver["checked"],
            "verifier_first_pass_rate": _rate(guard["questions_passed_first_try"], guard["questions_drafted"], 3),
            "grounding_failures": flags.get("grounding_failure", 0),
            "answer_leakage_blocked": flags.get("answer_leakage", 0),
            "teach_score_agreement": (ev.get("teach_scorer") or {}).get("agreement_within_15"),
            "diagnoses_total": len(dx_rows),
            "diagnoses_rejected": sum(1 for d in dx_rows if d.status == "rejected"),
            "diagnoses_llm": sum(1 for d in dx_rows if d.source == "llm"),
            "last_eval_at": ev.get("timestamp"),
        },
        safety={
            "injection_attempts": flags.get("injection_attempt", 0) + student_flags.get("injection_attempt", 0),
            "blocked_calls": flags.get("moderation_flagged", 0),
            "moderation_flags": flags.get("moderation_flagged", 0) + student_flags.get("moderation_flagged", 0),
            "off_topic_redirects": off_topic,
            "pii_scrubbed": sum(v for k, v in (flags + student_flags).items() if "pii_" in k),
            "budget_exceeded": flags.get("budget_exceeded", 0),
            "job_budget_exceeded": flags.get("job_budget_exceeded", 0),
            "rate_limited": codes.get(429, 0),
            "uploads_rejected": codes.get(413, 0),
            "document_injection_suspects": flags.get("document_injection_suspect", 0),
            "output_guardrail_drops": sum(guard.get(k, 0) for k in GUARD_DROP_KEYS),
            "studio_moderation_flags": guard.get("moderation_flagged", 0),
        },
        learning={
            "attempts": len(attempts),
            "active_students": active_students,
            "accuracy": _rate(sum(a.is_correct for a in attempts), len(attempts), 3),
            "mastery_gain_per_session": round(sum(sess_gain.values()) / len(sess_gain), 4) if sess_gain else None,
            "misconceptions_cleared": cleared,
            "concepts_mastered": len(mastered_rows),
            "avg_attempts_to_mastery": round(sum(r.n_attempts for r in mastered_rows) / len(mastered_rows), 2)
            if mastered_rows else None,
            "calibration": round(cal.score, 3) if cal.score is not None else None,
            "drop_off_rate": _rate(sum(1 for n in sess_counts.values() if n < 5), len(sess_counts), 3),
            "eval_mastery_gain_vs_control": (ev.get("mastery") or {}).get("gain_vs_control"),
        },
        studio={
            "subjects_total": sum(subjects.values()),
            "subjects_published": subjects.get("published", 0),
            "subjects_in_review": subjects.get("review", 0),
            "jobs": len(jobs),
            "jobs_running": sum(1 for j in jobs if j.status in ("queued", "running")),
            "jobs_failed": sum(1 for j in jobs if j.status == "failed"),
            "job_success_rate": _rate(sum(1 for j in finished if j.status == "done"), len(finished), 3),
            "avg_job_seconds": round(sum(durations) / len(durations), 1) if durations else None,
            "p95_job_seconds": percentile(durations, 95) if durations else None,
            "documents": len(docs),
            "documents_failed": sum(1 for d in docs if d.status == "failed"),
            "pages_parsed": sum(d.page_count for d in docs if d.status == "parsed"),
            "figures_described": sum(int(st.get("figures_described", 0)) for st in job_stats),
            "pages_ocr": sum(int(st.get("pages_ocr", 0)) for st in job_stats),
            "concepts_generated": sum(int(st.get("concepts", 0)) for st in job_stats),
            "questions_generated": sum(int(st.get("questions", 0)) for st in job_stats),
            "flashcards_generated": sum(int(st.get("flashcards", 0)) for st in job_stats),
            "studio_llm_calls": len(studio_calls),
            "studio_tokens": sum(c.input_tokens + c.output_tokens for c in studio_calls),
            "studio_usd": round(sum(c.cost_usd for c in studio_calls), 5),
        },
        timeseries=_timeseries(window, start, reqs, calls),
        question_health=health[:25],
    )


@router.get("/admin/traces", response_model=TracesResponse)
def admin_traces(limit: int = Query(default=50, ge=1, le=500), feature: str | None = None,
                 scope: str | None = Query(default=None, pattern="^(learner|studio)$"),
                 trace: str | None = Query(default=None, max_length=64, alias="trace_id"),
                 flagged: bool = False, window: MetricsWindow = Query(default="all"),
                 db: Session = Depends(get_db), tid: str = Depends(trace_id)) -> TracesResponse:
    writer.flush()
    conds = [_since(m.LLMCall.created_at, _start(window))]
    if feature:
        conds.append(m.LLMCall.feature == feature)
    if scope:
        conds.append(m.LLMCall.scope == scope)
    if trace:
        conds.append(m.LLMCall.trace_id == trace)
    if flagged:
        conds.append((m.LLMCall.fallback_used.is_(True)) | (m.LLMCall.schema_ok.is_(False))
                     | (cast(m.LLMCall.guardrail_flags, String).not_in(["[]", '["offline"]'])))
    total = db.scalar(select(func.count(m.LLMCall.id)).where(*conds)) or 0
    rows = db.scalars(select(m.LLMCall).where(*conds).order_by(m.LLMCall.created_at.desc()).limit(limit)).all()
    return TracesResponse(
        trace_id=tid, total=total,
        calls=[
            LLMCallOut(id=r.id, trace_id=r.trace_id, feature=r.feature, prompt_name=r.prompt_name,
                       prompt_version=r.prompt_version, model=r.model, input_tokens=r.input_tokens,
                       output_tokens=r.output_tokens, latency_ms=r.latency_ms, cost_usd=r.cost_usd,
                       schema_ok=r.schema_ok, retries=r.retries, fallback_used=r.fallback_used,
                       guardrail_flags=list(r.guardrail_flags or []), cache_hit=r.cache_hit, created_at=r.created_at,
                       scope=r.scope or "learner", student_id=r.student_id, error=r.error)
            for r in rows
        ],
    )


def _like(text: str) -> str:
    return "%" + text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


@router.get("/admin/logs", response_model=LogsResponse)
def admin_logs(level: str = Query(default="info", pattern="^(debug|info|warning|error|critical)$"),
               q: str | None = Query(default=None, max_length=200), event: str | None = Query(default=None, max_length=200),
               trace: str | None = Query(default=None, max_length=64, alias="trace_id"),
               window: MetricsWindow = Query(default="24h"), limit: int = Query(default=100, ge=1, le=500),
               before_id: int | None = None, db: Session = Depends(get_db),
               tid: str = Depends(trace_id)) -> LogsResponse:
    writer.flush()
    base = [_since(m.AppLog.created_at, _start(window))]
    levels = dict(db.execute(select(m.AppLog.level, func.count(m.AppLog.id)).where(*base)
                             .group_by(m.AppLog.level)).all())
    conds = [*base, m.AppLog.level.in_(LEVELS[LEVELS.index(level):])]
    if event:
        conds.append(m.AppLog.event == event)
    if trace:
        conds.append(m.AppLog.trace_id == trace)
    if q:
        pat = _like(q)
        conds.append(m.AppLog.event.ilike(pat, escape="\\") | cast(m.AppLog.data, String).ilike(pat, escape="\\"))
    total = db.scalar(select(func.count(m.AppLog.id)).where(*conds)) or 0
    page = [*conds, m.AppLog.id < before_id] if before_id else conds
    rows = db.scalars(select(m.AppLog).where(*page).order_by(m.AppLog.id.desc()).limit(limit)).all()
    return LogsResponse(
        trace_id=tid, total=total, levels={k: int(v) for k, v in levels.items()},
        next_before_id=rows[-1].id if len(rows) == limit else None,
        logs=[LogEntryOut(id=r.id, created_at=r.created_at, level=r.level, event=r.event, logger=r.logger,
                          trace_id=r.trace_id, student_id=r.student_id, data=r.data or {}) for r in rows],
    )


@router.get("/admin/telemetry", response_model=TelemetryStatus)
def admin_telemetry(db: Session = Depends(get_db), tid: str = Depends(trace_id)) -> TelemetryStatus:
    st = otel.status()
    s = get_settings()

    def ts(v: float | None) -> datetime | None:
        return datetime.fromtimestamp(v, UTC).replace(tzinfo=None) if v else None

    return TelemetryStatus(
        trace_id=tid, otel_enabled=st["enabled"], service_name=st["service_name"], environment=st["environment"],
        endpoint=st["endpoint"], auth_configured=st["auth_configured"], sample_ratio=st["sample_ratio"],
        openobserve_ui_url=st["openobserve_ui_url"], openobserve_org=st["openobserve_org"],
        exports={k: ExportHealth(exported=v["exported"], failed=v["failed"], last_success_at=ts(v["last_success_at"]),
                                 last_error=v["last_error"]) for k, v in st["exports"].items()},
        stored={
            "app_logs": db.scalar(select(func.count(m.AppLog.id))) or 0,
            "request_metrics": db.scalar(select(func.count(m.RequestMetric.id))) or 0,
            "llm_calls": db.scalar(select(func.count(m.LLMCall.id))) or 0,
        },
        retention={"log_days": s.log_retention_days, "log_max_rows": s.log_max_rows,
                   "request_metrics_days": s.request_metrics_retention_days},
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
