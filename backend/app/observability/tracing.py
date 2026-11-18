"""trace_id propagation (§14.1) + optional export to Langfuse / Phoenix.

A middleware assigns a trace_id per request; it flows via contextvars into events, the learner model,
LLM calls (llm_calls.trace_id) and the response body/header.
"""

from __future__ import annotations

import uuid
from contextvars import ContextVar
from typing import Any

_trace_id: ContextVar[str | None] = ContextVar("trace_id", default=None)
_student_id: ContextVar[str | None] = ContextVar("student_id", default=None)


def new_trace_id() -> str:
    return f"tr_{uuid.uuid4().hex[:16]}"


def current_trace_id() -> str | None:
    return _trace_id.get()


def ensure_trace_id() -> str:
    tid = _trace_id.get()
    if tid is None:
        tid = new_trace_id()
        _trace_id.set(tid)
    return tid


def set_trace_id(tid: str | None):
    return _trace_id.set(tid)


def reset_trace_id(token) -> None:
    _trace_id.reset(token)


def current_student_id() -> str | None:
    return _student_id.get()


def set_student_id(sid: str | None) -> None:
    _student_id.set(sid)


def export_span(kind: str, payload: dict[str, Any]) -> None:
    """Best-effort export to an external tracer when TRACING_EXPORT is set. Never raises."""
    from app.config import get_settings

    target = get_settings().tracing_export.lower()
    if not target:
        return
    try:
        if target == "langfuse":
            from langfuse import Langfuse  # type: ignore[import-not-found]

            Langfuse().trace(name=kind, id=payload.get("trace_id"), metadata=payload)
        elif target == "phoenix":
            from opentelemetry import trace  # type: ignore[import-not-found]

            with trace.get_tracer("rootwise").start_as_current_span(kind) as span:
                for k, v in payload.items():
                    if isinstance(v, (str, int, float, bool)):
                        span.set_attribute(k, v)
    except Exception:  # pragma: no cover - optional dependency
        pass
