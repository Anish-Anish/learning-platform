"""trace_id propagation (§14.1), LLM cost scope and per-job token budgets.

A middleware assigns a trace_id per request (the OpenTelemetry trace id when OTel is on, so app traces,
llm_calls rows, logs and OpenObserve all correlate); it flows via contextvars into events, the learner
model, LLM calls (llm_calls.trace_id) and the response body/header.
"""

from __future__ import annotations

import re
import threading
import uuid
from contextvars import ContextVar

_SAFE_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_trace_id: ContextVar[str | None] = ContextVar("trace_id", default=None)
_student_id: ContextVar[str | None] = ContextVar("student_id", default=None)
_llm_scope: ContextVar[str] = ContextVar("llm_scope", default="learner")
_budget: ContextVar[TokenBudget | None] = ContextVar("token_budget", default=None)


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


def valid_trace_id(value: str | None) -> str | None:
    """Accept client-supplied trace ids only if they are short and safe (no log/header injection)."""
    return value if value and _SAFE_ID.match(value) else None


# ------------------------------------------------------------------ LLM cost attribution + budgets
def current_llm_scope() -> str:
    return _llm_scope.get()


def set_llm_scope(scope: str):
    return _llm_scope.set(scope)


class TokenBudget:
    """Shared across threads of one job (contextvars copy the reference, not the object)."""

    def __init__(self, limit: int) -> None:
        self.limit = limit
        self.used = 0
        self._lock = threading.Lock()

    @property
    def exhausted(self) -> bool:
        return self.used >= self.limit

    def consume(self, tokens: int) -> None:
        with self._lock:
            self.used += max(0, tokens)


def current_budget() -> TokenBudget | None:
    return _budget.get()


def set_budget(budget: TokenBudget | None):
    return _budget.set(budget)
