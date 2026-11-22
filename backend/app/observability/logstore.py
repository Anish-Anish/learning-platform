"""Persist structlog events (INFO+) to `app_logs` for the admin Logs page.

Events are buffered and written in batches by the telemetry writer thread (never on the request path).
Old rows are pruned by age and by count so the table stays bounded.
"""

from __future__ import annotations

import threading
from datetime import UTC, datetime, timedelta
from typing import Any

_LEVELS = {"debug": 10, "info": 20, "warning": 30, "warn": 30, "error": 40, "critical": 50, "exception": 40}
_SKIP_EVENTS = {"telemetry_write_failed"}  # never log about failing to store logs (no feedback loop)
_CORE_KEYS = {"event", "level", "timestamp", "trace_id", "student_id", "logger"}
PRUNE_EVERY = 200

_lock = threading.Lock()
_buffer: list[dict[str, Any]] = []
_flushes = 0
_enabled = True


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def set_enabled(value: bool) -> None:
    global _enabled
    _enabled = value


def _jsonable(v: Any) -> Any:
    if isinstance(v, (str, int, float, bool)) or v is None:
        return v
    if isinstance(v, (list, tuple)):
        return [_jsonable(x) for x in v][:50]
    if isinstance(v, dict):
        return {str(k): _jsonable(x) for k, x in list(v.items())[:50]}
    return str(v)[:500]


def capture(event_dict: dict[str, Any]) -> None:
    level = str(event_dict.get("level", "info")).lower()
    event = str(event_dict.get("event", ""))
    if not _enabled or _LEVELS.get(level, 20) < 20 or event in _SKIP_EVENTS:
        return
    row = {
        "created_at": _now(),
        "level": "warning" if level == "warn" else level,
        "event": event[:200],
        "logger": event_dict.get("logger"),
        "trace_id": event_dict.get("trace_id"),
        "student_id": event_dict.get("student_id"),
        "data": {k: _jsonable(v) for k, v in event_dict.items() if k not in _CORE_KEYS},
    }
    with _lock:
        first = not _buffer
        _buffer.append(row)
    if first:
        from app.observability import writer

        writer.submit(_flush)


def _flush(db) -> None:
    global _flushes
    from sqlalchemy import delete, func, insert, select

    from app.config import get_settings
    from app.db.models import AppLog, RequestMetric

    with _lock:
        rows = list(_buffer)
        _buffer.clear()
    if rows:
        db.execute(insert(AppLog), rows)
    _flushes += 1
    if _flushes % PRUNE_EVERY == 1:
        s = get_settings()
        now = _now()
        db.execute(delete(AppLog).where(AppLog.created_at < now - timedelta(days=s.log_retention_days)))
        n = db.scalar(select(func.count(AppLog.id))) or 0
        if n > s.log_max_rows:
            cutoff = db.scalar(select(AppLog.id).order_by(AppLog.id.desc()).offset(s.log_max_rows).limit(1))
            if cutoff is not None:
                db.execute(delete(AppLog).where(AppLog.id <= cutoff))
        db.execute(delete(RequestMetric).where(
            RequestMetric.created_at < now - timedelta(days=s.request_metrics_retention_days)))
