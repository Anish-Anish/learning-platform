"""Shared FastAPI dependencies and small helpers."""

from __future__ import annotations

import json
from collections.abc import Iterator

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

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


def graph_dep(db: Session = Depends(get_db)) -> ContentGraph:
    return get_graph(db)


def require_student(db: Session, student_id: str) -> m.Student:
    s = db.get(m.Student, student_id)
    if s is None:
        raise HTTPException(404, f"unknown student {student_id}; call POST /session/start first")
    return s


def sse(event: str, data) -> str:
    payload = data.model_dump(mode="json") if hasattr(data, "model_dump") else data
    return f"event: {event}\ndata: {json.dumps(payload, default=str)}\n\n"
