"""Teacher studio (5A): upload material -> generated subject -> review -> publish -> assign to students.

Plus GET /students/{id}/subjects for the student subject switcher. Additive to PROJECT_CONTEXT §11.
"""

from __future__ import annotations

import shutil

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import client_key, enforce_rate_limit, get_db, trace_id
from app.config import UPLOADS_DIR, get_settings
from app.core import studio
from app.schemas.studio import (
    ConceptPatch,
    EnrollmentList,
    EnrollmentUpdate,
    FlashcardCreate,
    FlashcardIn,
    OkResponse,
    QuestionPatch,
    StudentSubjects,
    StudioConceptContent,
    StudioGraph,
    SubjectDetail,
    SubjectList,
)


def job_rate_limit(request: Request) -> None:
    """Generation jobs are the most expensive calls in the app: cap them per client."""
    enforce_rate_limit(f"studio_job:{client_key(request)}", get_settings().studio_jobs_per_minute,
                       "Too many generation requests. Wait a minute and try again.")


def studio_enabled() -> None:
    if not get_settings().flag_studio:
        raise HTTPException(404, "teacher studio is disabled")


router = APIRouter(tags=["studio"])
studio_router = APIRouter(prefix="/studio", tags=["studio"], dependencies=[Depends(studio_enabled)])


def _store_all(db: Session, subject, files: list[UploadFile]) -> None:
    if not files:
        raise studio.StudioError("attach at least one file")
    for f in files:
        studio.store_upload(db, subject, f.filename or "upload", f.file)


@studio_router.get("/subjects", response_model=SubjectList)
def list_subjects(db: Session = Depends(get_db), tid: str = Depends(trace_id)) -> SubjectList:
    return SubjectList(trace_id=tid, subjects=studio.list_subjects(db))


@studio_router.post("/subjects", response_model=SubjectDetail, status_code=201, dependencies=[Depends(job_rate_limit)])
def create_subject(
    name: str = Form(..., min_length=1, max_length=120),
    description: str = Form(default="", max_length=1000),
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    tid: str = Depends(trace_id),
) -> SubjectDetail:
    subject = studio.create_subject(db, name, description)
    try:
        _store_all(db, subject, files)
    except Exception:
        shutil.rmtree(UPLOADS_DIR / subject.id, ignore_errors=True)
        raise
    db.commit()
    studio.start_job(db, subject)
    return studio.subject_detail(db, subject.id, tid)


@studio_router.get("/subjects/{subject_id}", response_model=SubjectDetail)
def get_subject(subject_id: str, db: Session = Depends(get_db), tid: str = Depends(trace_id)) -> SubjectDetail:
    return studio.subject_detail(db, subject_id, tid)


@studio_router.delete("/subjects/{subject_id}", response_model=OkResponse)
def delete_subject(subject_id: str, db: Session = Depends(get_db), tid: str = Depends(trace_id)) -> OkResponse:
    studio.delete_subject(db, subject_id)
    return OkResponse(trace_id=tid)


@studio_router.post("/subjects/{subject_id}/documents", response_model=SubjectDetail,
                     dependencies=[Depends(job_rate_limit)])
def add_documents(
    subject_id: str,
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    tid: str = Depends(trace_id),
) -> SubjectDetail:
    subject = studio.get_subject(db, subject_id)
    if subject.status in ("processing", "published") or subject.is_default:
        raise studio.StudioConflict("material can only be added to a draft subject")
    _store_all(db, subject, files)
    db.commit()
    studio.start_job(db, subject)
    return studio.subject_detail(db, subject_id, tid)


@studio_router.post("/subjects/{subject_id}/regenerate", response_model=SubjectDetail,
                     dependencies=[Depends(job_rate_limit)])
def regenerate(subject_id: str, db: Session = Depends(get_db), tid: str = Depends(trace_id)) -> SubjectDetail:
    studio.start_job(db, studio.get_subject(db, subject_id))
    return studio.subject_detail(db, subject_id, tid)


@studio_router.post("/subjects/{subject_id}/publish", response_model=SubjectDetail)
def publish(subject_id: str, db: Session = Depends(get_db), tid: str = Depends(trace_id)) -> SubjectDetail:
    studio.publish(db, subject_id)
    return studio.subject_detail(db, subject_id, tid)


@studio_router.post("/subjects/{subject_id}/unpublish", response_model=SubjectDetail)
def unpublish(subject_id: str, db: Session = Depends(get_db), tid: str = Depends(trace_id)) -> SubjectDetail:
    studio.unpublish(db, subject_id)
    return studio.subject_detail(db, subject_id, tid)


@studio_router.get("/subjects/{subject_id}/graph", response_model=StudioGraph)
def subject_graph(subject_id: str, db: Session = Depends(get_db), tid: str = Depends(trace_id)) -> StudioGraph:
    return studio.studio_graph(db, subject_id, tid)


@studio_router.get("/subjects/{subject_id}/students", response_model=EnrollmentList)
def get_enrollment(subject_id: str, db: Session = Depends(get_db), tid: str = Depends(trace_id)) -> EnrollmentList:
    return studio.enrollment_list(db, subject_id, tid)


@studio_router.put("/subjects/{subject_id}/students", response_model=EnrollmentList)
def put_enrollment(subject_id: str, body: EnrollmentUpdate, db: Session = Depends(get_db),
                   tid: str = Depends(trace_id)) -> EnrollmentList:
    studio.set_enrollment(db, subject_id, body.student_ids)
    return studio.enrollment_list(db, subject_id, tid)


@studio_router.get("/concepts/{concept_id}", response_model=StudioConceptContent)
def get_concept(concept_id: str, db: Session = Depends(get_db), tid: str = Depends(trace_id)) -> StudioConceptContent:
    return studio.concept_content(db, concept_id, tid)


@studio_router.patch("/concepts/{concept_id}", response_model=StudioConceptContent)
def patch_concept(concept_id: str, body: ConceptPatch, db: Session = Depends(get_db),
                  tid: str = Depends(trace_id)) -> StudioConceptContent:
    studio.update_concept(db, concept_id, body)
    db.commit()
    return studio.concept_content(db, concept_id, tid)


@studio_router.delete("/concepts/{concept_id}", response_model=OkResponse)
def delete_concept(concept_id: str, db: Session = Depends(get_db), tid: str = Depends(trace_id)) -> OkResponse:
    studio.delete_concept(db, concept_id)
    db.commit()
    return OkResponse(trace_id=tid)


@studio_router.patch("/questions/{question_id}", response_model=OkResponse)
def patch_question(question_id: str, body: QuestionPatch, db: Session = Depends(get_db),
                   tid: str = Depends(trace_id)) -> OkResponse:
    studio.update_question(db, question_id, body)
    db.commit()
    return OkResponse(trace_id=tid)


@studio_router.delete("/questions/{question_id}", response_model=OkResponse)
def delete_question(question_id: str, db: Session = Depends(get_db), tid: str = Depends(trace_id)) -> OkResponse:
    studio.delete_question(db, question_id)
    db.commit()
    return OkResponse(trace_id=tid)


@studio_router.post("/flashcards", response_model=OkResponse, status_code=201)
def create_flashcard(body: FlashcardCreate, db: Session = Depends(get_db), tid: str = Depends(trace_id)) -> OkResponse:
    studio.create_flashcard(db, body.concept_id, FlashcardIn(front=body.front, back=body.back))
    db.commit()
    return OkResponse(trace_id=tid)


@studio_router.patch("/flashcards/{card_id}", response_model=OkResponse)
def patch_flashcard(card_id: str, body: FlashcardIn, db: Session = Depends(get_db),
                    tid: str = Depends(trace_id)) -> OkResponse:
    studio.update_flashcard(db, card_id, body)
    db.commit()
    return OkResponse(trace_id=tid)


@studio_router.delete("/flashcards/{card_id}", response_model=OkResponse)
def delete_flashcard(card_id: str, db: Session = Depends(get_db), tid: str = Depends(trace_id)) -> OkResponse:
    studio.delete_flashcard(db, card_id)
    db.commit()
    return OkResponse(trace_id=tid)


@router.get("/students/{student_id}/subjects", response_model=StudentSubjects, tags=["students"])
def student_subjects(student_id: str, db: Session = Depends(get_db), tid: str = Depends(trace_id)) -> StudentSubjects:
    return studio.student_subjects(db, student_id, tid)


router.include_router(studio_router)
