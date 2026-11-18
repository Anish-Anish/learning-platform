"""GET /class/heatmap, GET /class/alerts (teacher dashboard)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db, graph_dep, trace_id
from app.core import analytics
from app.core.graph import ContentGraph
from app.schemas.api import AlertsResponse, HeatmapResponse

router = APIRouter(tags=["class"])


@router.get("/class/heatmap", response_model=HeatmapResponse)
def class_heatmap(db: Session = Depends(get_db), graph: ContentGraph = Depends(graph_dep),
                  tid: str = Depends(trace_id)) -> HeatmapResponse:
    return analytics.heatmap(db, graph, tid)


@router.get("/class/alerts", response_model=AlertsResponse)
def class_alerts(db: Session = Depends(get_db), graph: ContentGraph = Depends(graph_dep),
                 tid: str = Depends(trace_id)) -> AlertsResponse:
    alerts, clusters, size = analytics.alerts(db, graph)
    return AlertsResponse(trace_id=tid, alerts=alerts, clusters=clusters, class_size=size)
