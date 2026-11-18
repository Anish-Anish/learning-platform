"""Cost/abuse guards (§13.1, §13.4): per-student daily token budget + per-minute rate limit."""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from datetime import timedelta

from sqlalchemy import func, select

from app.config import get_settings

_lock = threading.Lock()
_hits: dict[str, deque[float]] = defaultdict(deque)


def rate_limited(key: str, per_minute: int | None = None) -> bool:
    """Sliding-window limiter. Returns True when the call should be rejected."""
    limit = per_minute or get_settings().rate_limit_per_minute
    now = time.monotonic()
    with _lock:
        q = _hits[key]
        while q and now - q[0] > 60:
            q.popleft()
        if len(q) >= limit:
            return True
        q.append(now)
        return False


def tokens_used_today(student_id: str) -> int:
    from app.db.models import LLMCall, utcnow
    from app.db.session import SessionLocal

    since = utcnow() - timedelta(days=1)
    with SessionLocal() as db:
        return int(
            db.scalar(
                select(func.coalesce(func.sum(LLMCall.input_tokens + LLMCall.output_tokens), 0)).where(
                    LLMCall.student_id == student_id, LLMCall.created_at >= since
                )
            )
            or 0
        )


def over_budget(student_id: str | None) -> bool:
    if not student_id:
        return False
    try:
        return tokens_used_today(student_id) >= get_settings().student_daily_token_budget
    except Exception:
        return False


def reset() -> None:
    with _lock:
        _hits.clear()
