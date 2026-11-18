"""Background DB writer for telemetry (llm_calls, cache, request metrics).

SQLite allows one writer at a time. LLM calls often happen *inside* a request transaction that already
holds the write lock (e.g. the inline diagnosis), so writing the trace row synchronously from another
session would deadlock until the busy timeout. Telemetry is queued here and written by one daemon thread
as soon as the lock is free. `flush()` blocks until everything queued so far is written (tests/evals).
"""

from __future__ import annotations

import queue
import threading
from collections.abc import Callable

from sqlalchemy.orm import Session

_q: queue.Queue[Callable[[Session], None] | None] = queue.Queue()
_thread: threading.Thread | None = None
_lock = threading.Lock()


def _run() -> None:
    from app.db.session import SessionLocal
    from app.observability.logging import get_logger

    log = get_logger(__name__)
    while True:
        job = _q.get()
        try:
            if job is None:
                return
            with SessionLocal() as db:
                job(db)
                db.commit()
        except Exception as exc:  # pragma: no cover - telemetry must never crash the app
            log.warning("telemetry_write_failed", error=str(exc)[:300])
        finally:
            _q.task_done()


def submit(job: Callable[[Session], None]) -> None:
    global _thread
    if _thread is None or not _thread.is_alive():
        with _lock:
            if _thread is None or not _thread.is_alive():
                _thread = threading.Thread(target=_run, name="telemetry-writer", daemon=True)
                _thread.start()
    _q.put(job)


def flush() -> None:
    """Wait until every queued write has been committed."""
    if _thread is not None and _thread.is_alive():
        _q.join()
