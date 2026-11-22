"""Shared FastAPI dependencies and small helpers."""

from __future__ import annotations

import json
from collections.abc import Iterator

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.config import DEFAULT_SUBJECT_ID
from app.core.graph import ContentGraph, get_graph
from app.core.present import question_public  # noqa: F401  (re-exported for routes)
from app.db import models as m
from app.db.session import SessionLocal
from app.observability.tracing import current_trace_id, new_trace_id


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def trace_id(request: Request) -> str:
    return getattr(request.state, "trace_id", None) or current_trace_id() or new_trace_id()


def subject_dep(
    x_subject_id: str | None = Header(default=None, alias="X-Subject-Id"),
    db: Session = Depends(get_db),
) -> str:
    """The subject a request runs against (header set by the frontend's subject switcher)."""
    sid = (x_subject_id or "").strip() or DEFAULT_SUBJECT_ID
    if sid == DEFAULT_SUBJECT_ID:
        return sid
    subject = db.get(m.Subject, sid)
    if subject is None or subject.status != "published":
        raise HTTPException(404, f"subject {sid} is not published")
    return sid


def graph_dep(db: Session = Depends(get_db), subject_id: str = Depends(subject_dep)) -> ContentGraph:
    return get_graph(db, subject_id)


def enforce_rate_limit(key: str, per_minute: int, message: str = "Too many requests. Try again in a minute.") -> None:
    """Sliding-window guard for LLM-backed endpoints (cost + abuse). 429 with Retry-After."""
    from app.guardrails.budget import rate_limited
    from app.observability import otel
    from app.observability.logging import get_logger

    if rate_limited(key, per_minute):
        kind = key.split(":", 1)[0]
        otel.HTTP_REJECTED.add(1, {"reason": "rate_limited", "endpoint": kind})
        get_logger(__name__).warning("rate_limited", limiter=kind, per_minute=per_minute)
        raise HTTPException(429, message, headers={"Retry-After": "60"})


def client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def require_student(db: Session, student_id: str) -> m.Student:
    s = db.get(m.Student, student_id)
    if s is None:
        raise HTTPException(404, f"unknown student {student_id}; call POST /session/start first")
    return s


def sse(event: str, data) -> str:
    payload = data.model_dump(mode="json") if hasattr(data, "model_dump") else data
    return f"event: {event}\ndata: {json.dumps(payload, default=str)}\n\n"
