"""Generated-content cache keyed by hash(prompt_version + model + inputs) (§13.4)."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from app.db import models as m
from app.db.session import SessionLocal


def cache_key(prompt_name: str, prompt_version: str, model: str, inputs: dict[str, Any]) -> str:
    raw = json.dumps(
        {"p": prompt_name, "v": prompt_version, "m": model, "i": inputs}, sort_keys=True, default=str
    )
    return hashlib.sha256(raw.encode()).hexdigest()


def get(key: str) -> dict[str, Any] | None:
    try:
        with SessionLocal() as db:
            row = db.get(m.GeneratedCache, key)
            return dict(row.payload) if row else None
    except Exception:
        return None


def put(key: str, kind: str, payload: dict[str, Any]) -> None:
    from app.observability import writer

    writer.submit(lambda db: db.merge(m.GeneratedCache(key=key, kind=kind, payload=payload)))
