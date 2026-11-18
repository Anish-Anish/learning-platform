"""Request-latency middleware + percentile helpers for /admin (§14.2)."""

from __future__ import annotations

import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.observability.logging import get_logger
from app.observability.tracing import new_trace_id, reset_trace_id, set_student_id, set_trace_id

log = get_logger(__name__)

_SKIP = ("/docs", "/openapi.json", "/redoc", "/favicon.ico", "/health")


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    vs = sorted(values)
    k = (len(vs) - 1) * pct / 100.0
    lo, hi = int(k), min(int(k) + 1, len(vs) - 1)
    return round(vs[lo] + (vs[hi] - vs[lo]) * (k - lo), 2)


class TraceAndMetricsMiddleware(BaseHTTPMiddleware):
    """Assign trace_id, time the request, persist a request_metrics row."""

    async def dispatch(self, request: Request, call_next):
        tid = request.headers.get("x-trace-id") or new_trace_id()
        token = set_trace_id(tid)
        set_student_id(request.query_params.get("student_id"))
        request.state.trace_id = tid
        start = time.perf_counter()
        status = 500
        try:
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
            return response
        finally:
            elapsed = (time.perf_counter() - start) * 1000
            path = request.url.path
            if not path.startswith(_SKIP) and request.method != "OPTIONS":
                route = request.scope.get("route")
                route_path = getattr(route, "path", path)
                _record(tid, request.method, route_path, status, elapsed)
            reset_trace_id(token)


def _record(tid: str, method: str, route: str, status: int, latency_ms: float) -> None:
    from app.db.models import RequestMetric
    from app.observability import writer

    row = RequestMetric(trace_id=tid, method=method, route=route, status_code=status, latency_ms=latency_ms)
    writer.submit(lambda db: db.add(row))
