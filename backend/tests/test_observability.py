"""Observability: admin metrics/logs/traces/telemetry, trace-id hygiene, OTel spans and OTLP export."""

from __future__ import annotations

import base64
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from types import SimpleNamespace

import pytest

from app.ai import llm_client
from app.db import models as m
from app.observability import otel, writer
from app.observability.logging import get_logger
from app.observability.tracing import set_llm_scope
from app.schemas.ai import AnalogyOut


def _fake_client(output):
    class Completions:
        def parse(self, **_kw):
            msg = SimpleNamespace(parsed=output, content=None, tool_calls=None)
            return SimpleNamespace(choices=[SimpleNamespace(message=msg)],
                                   usage=SimpleNamespace(prompt_tokens=1000, completion_tokens=500))

    return SimpleNamespace(chat=SimpleNamespace(completions=Completions()))


def _llm(feature: str, trace: str):
    return llm_client.call(feature=feature, prompt_name="analogy", inputs={"x": trace}, output_schema=AnalogyOut,
                           trace_id=trace, fallback=lambda: AnalogyOut(analogy="FB"), use_cache=False)


def test_metrics_window_and_cost_split(client):
    llm_client.set_client(_fake_client(AnalogyOut(analogy="live")))
    try:
        _llm("analogy", "tr_obs_learner")
        token = set_llm_scope("studio")
        try:
            _llm("studio_notes", "tr_obs_studio")
        finally:
            from app.observability.tracing import _llm_scope

            _llm_scope.reset(token)
    finally:
        llm_client.set_client(None)
    writer.flush()
    mt = client.get("/admin/metrics", params={"window": "1h"}).json()
    assert mt["window"] == "1h" and mt["window_start"]
    assert mt["cost"]["studio_usd"] > 0 and mt["cost"]["learner_usd"] > 0
    assert mt["cost"]["total_usd"] == pytest.approx(mt["cost"]["learner_usd"] + mt["cost"]["studio_usd"], abs=1e-5)
    assert mt["studio"]["studio_llm_calls"] >= 1
    assert isinstance(mt["timeseries"], list) and mt["timeseries"]
    assert {"rate_limited", "uploads_rejected", "injection_attempts", "blocked_calls"} <= set(mt["safety"])
    traces = client.get("/admin/traces", params={"scope": "studio", "limit": 5}).json()
    assert traces["total"] >= 1 and all(c["scope"] == "studio" for c in traces["calls"])
    one = client.get("/admin/traces", params={"trace_id": "tr_obs_learner"}).json()
    assert [c["feature"] for c in one["calls"]] == ["analogy"]
    assert client.get("/admin/metrics", params={"window": "5y"}).status_code == 422


def test_logs_are_stored_searchable_and_filtered(client):
    log = get_logger("tests.obs")
    log.info("obs_probe_event", detail="needle-1234")
    log.warning("obs_probe_warning", detail="haystack")
    log.debug("obs_probe_debug")  # below INFO: not stored
    writer.flush()
    found = client.get("/admin/logs", params={"q": "needle-1234"}).json()
    assert found["total"] >= 1
    row = found["logs"][0]
    assert row["event"] == "obs_probe_event" and row["logger"] == "tests.obs" and row["data"]["detail"] == "needle-1234"
    warn = client.get("/admin/logs", params={"level": "warning", "event": "obs_probe_warning"}).json()
    assert warn["total"] >= 1 and all(r["level"] in ("warning", "error", "critical") for r in warn["logs"])
    assert client.get("/admin/logs", params={"event": "obs_probe_debug"}).json()["total"] == 0
    assert client.get("/admin/logs", params={"q": "100%_"}).status_code == 200  # LIKE wildcards are escaped


def test_trace_id_header_is_sanitised(client):
    ok = client.get("/health", headers={"x-trace-id": "tr_client_123"})
    assert ok.headers["x-trace-id"] == "tr_client_123"
    bad = client.get("/concepts", headers={"x-trace-id": "evil\x0bid; drop table"})
    assert bad.headers["x-trace-id"].startswith("tr_") and "evil" not in bad.headers["x-trace-id"]
    assert bad.headers["x-frame-options"] == "DENY"


def test_telemetry_status_reports_disabled_otel(client):
    t = client.get("/admin/telemetry").json()
    assert t["otel_enabled"] is False and t["endpoint"] is None
    assert t["stored"]["llm_calls"] >= 0 and t["retention"]["log_days"] > 0


def test_llm_span_has_genai_attributes_and_no_prompt_text():
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("test")
    original = otel._tracer
    otel._tracer = tracer
    try:
        llm_client.set_client(_fake_client(AnalogyOut(analogy="live")))
        with tracer.start_as_current_span("request") as parent:
            _llm("analogy", "tr_span_test")
        parent_id = parent.get_span_context().span_id
    finally:
        llm_client.set_client(None)
        otel._tracer = original
    span = next(s for s in exporter.get_finished_spans() if s.name == "llm analogy")
    a = span.attributes
    assert a["gen_ai.usage.input_tokens"] == 1000 and a["gen_ai.usage.output_tokens"] == 500
    assert a["rootwise.feature"] == "analogy" and a["rootwise.trace_id"] == "tr_span_test"
    assert span.parent.span_id == parent_id and span.end_time >= span.start_time
    assert not any("tr_span_test" in str(v) for k, v in a.items() if k != "rootwise.trace_id")  # no prompt inputs
    assert trace.get_current_span() is not None


class _Capture(BaseHTTPRequestHandler):
    seen: list[tuple[str, str | None]] = []

    def do_POST(self):  # noqa: N802
        self.rfile.read(int(self.headers.get("content-length", 0)))
        _Capture.seen.append((self.path, self.headers.get("authorization")))
        self.send_response(200)
        self.send_header("content-type", "application/x-protobuf")
        self.end_headers()

    def log_message(self, *_a):
        pass


def test_otlp_export_reaches_openobserve_style_endpoint(monkeypatch):
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor

    from app.config import get_settings

    server = HTTPServer(("127.0.0.1", 0), _Capture)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        s = get_settings()
        monkeypatch.setattr(s, "openobserve_user", "root@example.com")
        monkeypatch.setattr(s, "openobserve_password", "secret")
        base = f"http://127.0.0.1:{server.server_port}/api/default"
        exporter = otel._counting(OTLPSpanExporter(endpoint=f"{base}/v1/traces", headers=otel._headers()), "traces_test")
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        with provider.get_tracer("t").start_as_current_span("hello"):
            pass
        provider.shutdown()
    finally:
        server.shutdown()
    path, auth = _Capture.seen[-1]
    assert path == "/api/default/v1/traces"
    assert auth == "Basic " + base64.b64encode(b"root@example.com:secret").decode()
    assert otel.STATS.snapshot()["traces_test"]["exported"] == 1


def test_app_log_table_is_bounded(db, monkeypatch):
    from app.config import get_settings
    from app.observability import logstore

    monkeypatch.setattr(get_settings(), "log_max_rows", 5)
    monkeypatch.setattr(logstore, "_flushes", 0)
    for i in range(12):
        logstore.capture({"event": f"bulk_{i}", "level": "info"})
    writer.flush()
    from sqlalchemy import func, select

    db.expire_all()
    assert (db.scalar(select(func.count(m.AppLog.id))) or 0) <= 5
