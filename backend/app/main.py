"""Rootwise FastAPI app. `uv run uvicorn app.main:app --reload --port 8000`."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.ai.llm_client import llm_mode
from app.api import admin, attempts, boss, klass, levels, session, sim, students, teach, tutor
from app.config import get_settings
from app.core.graph import get_graph
from app.db.seed import ensure_seeded
from app.db.session import SessionLocal, create_all
from app.observability.logging import configure_logging, get_logger
from app.observability.metrics import TraceAndMetricsMiddleware
from app.observability.tracing import current_trace_id

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    s = get_settings()
    configure_logging(s.log_level)
    create_all()
    with SessionLocal() as db:
        seeded = ensure_seeded(db)
        g = get_graph(db)
    log.info("startup", seeded=seeded, concepts=len(g.concepts), questions=len(g.questions), llm_mode=llm_mode())
    yield


app = FastAPI(
    title="Rootwise API",
    version="0.1.0",
    description="Adaptive tutor that traces mistakes to the root prerequisite gap. AI suggests, code decides.",
    lifespan=lifespan,
)
app.add_middleware(TraceAndMetricsMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in get_settings().cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["x-trace-id"],
)

for r in (session, attempts, students, levels, tutor, boss, teach, klass, admin, sim):
    app.include_router(r.router)


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok", "llm_mode": llm_mode()}


@app.exception_handler(Exception)
async def unhandled(_request: Request, exc: Exception) -> JSONResponse:
    tid = current_trace_id()
    log.error("unhandled_error", error=f"{type(exc).__name__}: {exc}", trace_id=tid)
    return JSONResponse(status_code=500, content={"detail": "Something went wrong on our side.", "trace_id": tid})
