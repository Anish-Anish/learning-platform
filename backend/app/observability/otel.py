"""OpenTelemetry: traces, metrics and logs over OTLP/HTTP (OpenObserve by default, any OTLP backend works).

Off unless OTEL_ENABLED=true. When off, every helper here is a cheap no-op (the global OTel API returns
non-recording spans and instruments), so call sites never need to check.

- Traces: one server span per request (FastAPI instrumentation), one span per LLM call / agent turn with
  GenAI semantic-convention attributes (no prompt text: rule 5), spans around studio job stages.
- Metrics: LLM calls / tokens / cost / latency, guardrail flags, studio jobs, plus HTTP server metrics.
- Logs: every structlog event is bridged to an OTel log record correlated with the active span.
"""

from __future__ import annotations

import base64
import logging
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from opentelemetry import metrics, trace
from opentelemetry.trace import Status, StatusCode

from app.config import get_settings

_tracer = trace.get_tracer("rootwise")
_meter = metrics.get_meter("rootwise")

LLM_CALLS = _meter.create_counter("rootwise.llm.calls", description="LLM calls by feature and outcome")
LLM_TOKENS = _meter.create_counter("rootwise.llm.tokens", unit="{token}", description="LLM tokens")
LLM_COST = _meter.create_counter("rootwise.llm.cost", unit="USD", description="Estimated LLM cost")
LLM_DURATION = _meter.create_histogram("rootwise.llm.duration", unit="ms", description="LLM call latency")
GUARDRAIL_FLAGS = _meter.create_counter("rootwise.guardrail.flags", description="Guardrail flags raised")
STUDIO_JOBS = _meter.create_counter("rootwise.studio.jobs", description="Studio generation jobs by outcome")
HTTP_REJECTED = _meter.create_counter("rootwise.http.rejected", description="Requests rejected by guardrails")

_BRIDGE = logging.getLogger("rootwise.otel")
_BRIDGE.propagate = False
_RESERVED = set(logging.LogRecord("", 0, "", 0, "", None, None).__dict__) | {"message", "asctime"}


class _ExportStats:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.data: dict[str, dict[str, Any]] = {}

    def record(self, signal: str, ok: bool, n: int, error: str | None = None) -> None:
        with self.lock:
            d = self.data.setdefault(signal, {"exported": 0, "failed": 0, "last_success_at": None, "last_error": None})
            if ok:
                d["exported"] += n
                d["last_success_at"] = time.time()
            else:
                d["failed"] += n
                d["last_error"] = error

    def snapshot(self) -> dict[str, dict[str, Any]]:
        with self.lock:
            return {k: dict(v) for k, v in self.data.items()}


STATS = _ExportStats()
_state: dict[str, Any] = {"enabled": False, "providers": []}


def _headers() -> dict[str, str]:
    s = get_settings()
    out: dict[str, str] = {}
    for part in s.otel_headers.split(","):
        if "=" in part:
            k, v = part.split("=", 1)
            out[k.strip()] = v.strip()
    if s.openobserve_user and s.openobserve_password:
        token = base64.b64encode(f"{s.openobserve_user}:{s.openobserve_password}".encode()).decode()
        out.setdefault("Authorization", f"Basic {token}")
    return out


def _counting(exporter: Any, signal: str) -> Any:
    """Wrap a span/log exporter so the admin page can show real export health."""
    original = exporter.export

    def export(batch):  # type: ignore[no-untyped-def]
        try:
            result = original(batch)
        except Exception as exc:  # pragma: no cover - network errors
            STATS.record(signal, False, len(batch), f"{type(exc).__name__}: {exc}"[:200])
            raise
        ok = getattr(result, "name", str(result)) == "SUCCESS"
        STATS.record(signal, ok, len(batch), None if ok else "exporter returned FAILURE (check endpoint/auth)")
        return result

    exporter.export = export
    return exporter


def setup(app: Any = None) -> bool:
    """Install providers + FastAPI instrumentation. Must run before the app serves its first request."""
    s = get_settings()
    if not s.otel_enabled or _state["enabled"]:
        return _state["enabled"]
    from opentelemetry._logs import set_logger_provider
    from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
    from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
    from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased

    base = s.otel_exporter_endpoint.rstrip("/")
    headers = _headers()
    resource = Resource.create({"service.name": s.otel_service_name, "service.version": "0.1.0",
                                "deployment.environment": s.otel_environment})

    tp = TracerProvider(resource=resource, sampler=ParentBased(TraceIdRatioBased(s.otel_sample_ratio)))
    tp.add_span_processor(BatchSpanProcessor(_counting(
        OTLPSpanExporter(endpoint=f"{base}/v1/traces", headers=headers, timeout=10), "traces")))
    trace.set_tracer_provider(tp)

    mp = MeterProvider(resource=resource, metric_readers=[PeriodicExportingMetricReader(
        OTLPMetricExporter(endpoint=f"{base}/v1/metrics", headers=headers, timeout=10),
        export_interval_millis=s.otel_metric_interval_s * 1000)])
    metrics.set_meter_provider(mp)

    lp = LoggerProvider(resource=resource)
    lp.add_log_record_processor(BatchLogRecordProcessor(_counting(
        OTLPLogExporter(endpoint=f"{base}/v1/logs", headers=headers, timeout=10), "logs")))
    set_logger_provider(lp)
    _BRIDGE.handlers = [LoggingHandler(level=logging.DEBUG, logger_provider=lp)]
    _BRIDGE.setLevel(logging.DEBUG)

    if app is not None:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(app, tracer_provider=tp, meter_provider=mp,
                                           excluded_urls="health,docs,openapi.json,redoc,favicon.ico")
    _state.update(enabled=True, providers=[tp, mp, lp])
    return True


def shutdown() -> None:
    for p in _state.get("providers", []):
        try:
            p.shutdown()
        except Exception:  # pragma: no cover
            pass


def enabled() -> bool:
    return bool(_state["enabled"])


def status() -> dict[str, Any]:
    s = get_settings()
    return {
        "enabled": enabled(),
        "service_name": s.otel_service_name,
        "environment": s.otel_environment,
        "endpoint": s.otel_exporter_endpoint if enabled() else None,
        "auth_configured": bool(s.openobserve_user and s.openobserve_password) or "Authorization" in s.otel_headers,
        "sample_ratio": s.otel_sample_ratio,
        "openobserve_ui_url": s.openobserve_ui_url,
        "openobserve_org": s.openobserve_org,
        "exports": STATS.snapshot(),
    }


# ------------------------------------------------------------------ helpers used across the app
def current_trace_hex() -> str | None:
    ctx = trace.get_current_span().get_span_context()
    return format(ctx.trace_id, "032x") if ctx.is_valid else None


def set_attributes(**attrs: Any) -> None:
    span = trace.get_current_span()
    if span.is_recording():
        span.set_attributes({k: v for k, v in attrs.items() if v is not None})


@contextmanager
def span(name: str, **attrs: Any) -> Iterator[Any]:
    with _tracer.start_as_current_span(name, attributes={k: v for k, v in attrs.items() if v is not None}) as sp:
        yield sp


def llm_span(*, feature: str, prompt_name: str, prompt_version: str, model: str, scope: str, tin: int, tout: int,
             latency_ms: int, cost_usd: float, schema_ok: bool, retries: int, fallback_used: bool, cache_hit: bool,
             flags: list[str], trace_id: str, error: str | None) -> None:
    """Back-dated span for a finished LLM call (child of the current request/job span) + metrics."""
    end = time.time_ns()
    attrs: dict[str, Any] = {
        "gen_ai.system": "openai", "gen_ai.operation.name": "chat", "gen_ai.request.model": model,
        "gen_ai.usage.input_tokens": tin, "gen_ai.usage.output_tokens": tout,
        "rootwise.feature": feature, "rootwise.prompt.name": prompt_name, "rootwise.prompt.version": prompt_version,
        "rootwise.scope": scope, "rootwise.cost_usd": cost_usd, "rootwise.schema_ok": schema_ok,
        "rootwise.retries": retries, "rootwise.fallback_used": fallback_used, "rootwise.cache_hit": cache_hit,
        "rootwise.guardrail_flags": flags, "rootwise.trace_id": trace_id,
    }
    sp = _tracer.start_span(f"llm {feature}", kind=trace.SpanKind.CLIENT, start_time=end - latency_ms * 1_000_000,
                            attributes=attrs)
    if error:
        sp.set_status(Status(StatusCode.ERROR, error[:200]))
    sp.end(end_time=end)

    labels = {"feature": feature, "scope": scope}
    LLM_CALLS.add(1, {**labels, "outcome": "cache" if cache_hit else "fallback" if fallback_used else "ok"})
    if tin:
        LLM_TOKENS.add(tin, {**labels, "direction": "input"})
    if tout:
        LLM_TOKENS.add(tout, {**labels, "direction": "output"})
    if cost_usd:
        LLM_COST.add(cost_usd, labels)
    LLM_DURATION.record(latency_ms, labels)
    for f in flags:
        GUARDRAIL_FLAGS.add(1, {"flag": f, "feature": feature})


def emit_log(level: str, event: str, fields: dict[str, Any]) -> None:
    """structlog -> OTel log record (correlated with the current span)."""
    if not enabled():
        return
    extra: dict[str, Any] = {}
    for k, v in fields.items():
        key = f"x_{k}" if k in _RESERVED else k
        extra[key] = v if isinstance(v, (str, int, float, bool)) else str(v)[:1000]
    levelno = logging.getLevelName(str(level).upper())
    _BRIDGE.log(levelno if isinstance(levelno, int) else logging.INFO, event, extra=extra)
