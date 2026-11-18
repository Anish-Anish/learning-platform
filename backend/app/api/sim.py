"""POST /sim/run — dev only, flag-gated (FLAG_SIM_ENDPOINT)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import trace_id
from app.config import get_settings
from app.schemas.api import SimRunRequest, SimRunResponse

router = APIRouter(tags=["sim"])


@router.post("/sim/run", response_model=SimRunResponse)
def sim_run(body: SimRunRequest, tid: str = Depends(trace_id)) -> SimRunResponse:
    if not get_settings().flag_sim_endpoint:
        raise HTTPException(404, "simulator endpoint disabled")
    from fastapi.testclient import TestClient

    from app.main import app
    from app.sim.run import reset_sim_data, run_simulation

    if body.reset:
        reset_sim_data()
    client = TestClient(app)
    stats = run_simulation(client, body.students, body.attempts_per_student, body.seed, body.remediation)
    det = stats.detection
    return SimRunResponse(
        trace_id=tid, students=stats.students, attempts=stats.attempts, diagnoses=stats.diagnoses,
        planted=det["planted"] or 0, detected=det["detected"] or 0, detection_accuracy=det["accuracy"],
        duration_s=stats.duration_s,
    )
