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
    return structlog.get_logger(name)
