"""GET /students/{id}/map, GET /students/{id}/report, GET /concepts, GET /students/{id}."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db, graph_dep, require_student, trace_id
from app.core.analytics import root_report, student_map
from app.core.graph import ContentGraph
from app.core.student_state import student_summary
from app.schemas.api import RootReportResponse, StudentMapResponse, StudentSummary
from app.schemas.content import ConceptOut

router = APIRouter(tags=["students"])


@router.get("/students/{student_id}", response_model=StudentSummary)
def get_student(student_id: str, db: Session = Depends(get_db)) -> StudentSummary:
    return student_summary(db, require_student(db, student_id))


@router.get("/students/{student_id}/map", response_model=StudentMapResponse)
def get_map(
    student_id: str,
    db: Session = Depends(get_db),
    graph: ContentGraph = Depends(graph_dep),
    tid: str = Depends(trace_id),
) -> StudentMapResponse:
    require_student(db, student_id)
    out = student_map(db, student_id, graph, tid)
    db.commit()
    return out


@router.get("/students/{student_id}/report", response_model=RootReportResponse)
def get_report(
    student_id: str,
    db: Session = Depends(get_db),
    graph: ContentGraph = Depends(graph_dep),
    tid: str = Depends(trace_id),
) -> RootReportResponse:
    require_student(db, student_id)
    out = root_report(db, student_id, graph, tid)
    db.commit()
    return out


@router.get("/concepts", response_model=list[ConceptOut])
def list_concepts(graph: ContentGraph = Depends(graph_dep)) -> list[ConceptOut]:
    return [
        ConceptOut(id=c.id, name=c.name, description=c.description, prerequisites=c.prerequisites,
                   key_points=c.key_points, content_version=1, status="approved")
        for c in graph.concepts.values()
    ]
