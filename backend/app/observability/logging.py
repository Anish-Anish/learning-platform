"""structlog JSON logging with trace_id / student_id bound from context (§14.1)."""

from __future__ import annotations

import logging
import sys

import structlog

from app.observability.tracing import current_student_id, current_trace_id

_configured = False


def _add_context(_logger, _method, event_dict):
    tid = current_trace_id()
    if tid and "trace_id" not in event_dict:
        event_dict["trace_id"] = tid
    sid = current_student_id()
    if sid and "student_id" not in event_dict:
        event_dict["student_id"] = sid
    return event_dict


def _sinks(_logger, _method, event_dict):
    """Fan out to the admin log store and (when enabled) OpenTelemetry logs. Never raises."""
    try:
        from app.observability import logstore, otel

        logstore.capture(event_dict)
        otel.emit_log(str(event_dict.get("level", "info")), str(event_dict.get("event", "")),
                      {k: v for k, v in event_dict.items() if k not in ("event", "level", "timestamp")})
    except Exception:  # pragma: no cover - logging must never break the app
        pass
    return event_dict


def configure_logging(level: str = "INFO") -> None:
    global _configured
    if _configured:
        return
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=getattr(logging, level.upper(), 20))
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            _add_context,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            _sinks,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, level.upper(), 20)),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    _configured = True


def get_logger(name: str | None = None):
    if not _configured:
        configure_logging()
    # PrintLoggerFactory ignores positional names, so bind it explicitly for the Logs page.
    return structlog.get_logger().bind(logger=name) if name else structlog.get_logger()
