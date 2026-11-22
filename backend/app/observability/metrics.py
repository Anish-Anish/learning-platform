"""Request-latency middleware + percentile helpers for /admin (§14.2)."""

from __future__ import annotations

import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.config import get_settings
from app.observability import otel
from app.observability.logging import get_logger
from app.observability.tracing import (
    new_trace_id,
    reset_trace_id,
    set_student_id,
    set_trace_id,
    valid_trace_id,
)

log = get_logger(__name__)

_SKIP = ("/docs", "/openapi.json", "/redoc", "/favicon.ico", "/health")


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    vs = sorted(values)
    k = (len(vs) - 1) * pct / 100.0
    lo, hi = int(k), min(int(k) + 1, len(vs) - 1)
    return round(vs[lo] + (vs[hi] - vs[lo]) * (k - lo), 2)


SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
}
SLOW_MS = 1500


def _too_large(request: Request) -> bool:
    """Reject oversized uploads from Content-Length before Starlette spools the body to disk."""
    if request.method != "POST" or not request.url.path.startswith("/studio/"):
        return False
    s = get_settings()
    limit = s.studio_max_files * s.studio_max_upload_mb * 1024 * 1024 + 1024 * 1024
    try:
        return int(request.headers.get("content-length", "0")) > limit
    except ValueError:
        return True


class TraceAndMetricsMiddleware(BaseHTTPMiddleware):
    """Assign trace_id, apply request guardrails, time the request, persist a request_metrics row."""

    async def dispatch(self, request: Request, call_next):
        otel_hex = otel.current_trace_hex()
        tid = valid_trace_id(request.headers.get("x-trace-id")) or (f"tr_{otel_hex}" if otel_hex else new_trace_id())
        token = set_trace_id(tid)
        student = valid_trace_id(request.query_params.get("student_id"))
        set_student_id(student)
        request.state.trace_id = tid
        otel.set_attributes(**{"rootwise.trace_id": tid, "rootwise.student_id": student,
                               "rootwise.subject_id": valid_trace_id(request.headers.get("x-subject-id"))})
        start = time.perf_counter()
        status = 500
        try:
            if _too_large(request):
                otel.HTTP_REJECTED.add(1, {"reason": "payload_too_large"})
                log.warning("upload_rejected_too_large", path=request.url.path,
                            content_length=request.headers.get("content-length"))
                response = JSONResponse(status_code=413, content={"detail": "Upload is too large.", "trace_id": tid})
                status = 413
                response.headers["x-trace-id"] = tid
                return response
            try:
                response = await call_next(request)
            except Exception as exc:
                # Handle here (inside CORSMiddleware) so browsers see a JSON 500 with CORS headers,
                # not an opaque CORS failure.
                log.error("unhandled_error", error=f"{type(exc).__name__}: {exc}"[:500], path=request.url.path)
                response = JSONResponse(
                    status_code=500, content={"detail": "Something went wrong on our side.", "trace_id": tid}
                )
            status = response.status_code
            response.headers["x-trace-id"] = tid
            for k, v in SECURITY_HEADERS.items():
                response.headers.setdefault(k, v)
            return response
        finally:
            elapsed = (time.perf_counter() - start) * 1000
            path = request.url.path
            if not path.startswith(_SKIP) and request.method != "OPTIONS":
                route = request.scope.get("route")
                route_path = getattr(route, "path", path)
                _record(tid, request.method, route_path, status, elapsed)
                if status >= 500:
                    log.error("http_request", method=request.method, route=route_path, status=status, ms=round(elapsed))
                elif status >= 400 or elapsed > SLOW_MS:
                    log.warning("http_request", method=request.method, route=route_path, status=status,
                                ms=round(elapsed), slow=elapsed > SLOW_MS)
            reset_trace_id(token)


def _record(tid: str, method: str, route: str, status: int, latency_ms: float) -> None:
    from app.db.models import RequestMetric
    from app.observability import writer

    row = RequestMetric(trace_id=tid, method=method, route=route, status_code=status, latency_ms=latency_ms)
    writer.submit(lambda db: db.add(row))
