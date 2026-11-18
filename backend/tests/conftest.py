from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

# Force offline mode + an isolated DB before any app import reads settings.
os.environ["OPENAI_API_KEY"] = ""
os.environ["LESSON_STREAM_DELAY_MS"] = "0"
_TMP = Path(tempfile.mkdtemp(prefix="rootwise-test-"))
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP / 'test.db'}"

from app.config import get_settings  # noqa: E402

get_settings.cache_clear()

from app.db import session as db_session  # noqa: E402

db_session.configure(os.environ["DATABASE_URL"])
db_session.create_all()

from app.core import graph as graph_mod  # noqa: E402
from app.db.seed import seed  # noqa: E402

with db_session.SessionLocal() as _db:
    seed(_db)


@pytest.fixture(scope="session")
def graph():
    with db_session.SessionLocal() as db:
        return graph_mod.get_graph(db)


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture()
def db():
    with db_session.SessionLocal() as s:
        yield s


_counter = {"n": 0}


@pytest.fixture()
def student_id() -> str:
    _counter["n"] += 1
    return f"test_{os.getpid()}_{_counter['n']}"


def answer(graph, qid: str, *, correct: bool = True, misconception: str | None = None) -> str:
    q = graph.questions[qid]
    if misconception:
        return next(o.id for o in q.options if o.misconception_id == misconception)
    if correct:
        return q.correct_option.id
    return next(o.id for o in q.options if not o.is_correct)
