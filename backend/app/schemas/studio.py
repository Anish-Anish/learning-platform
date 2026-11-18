"""Teacher studio (5A) + subject contracts. SHARED CONTRACT, additive to PROJECT_CONTEXT §11."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from .api import Traced
from .common import BloomLevel

SubjectStatus = Literal["draft", "processing", "review", "published", "failed"]
JobStatus = Literal["queued", "running", "done", "failed"]


class StudioJobOut(BaseModel):
    id: str
    status: JobStatus
    stage: str
    progress: float
    message: str
    error: str | None = None
    stats: dict
    created_at: datetime
    finished_at: datetime | None = None


class SourceDocumentOut(BaseModel):
    id: str
    filename: str
    size_bytes: int
    page_count: int
    status: str
    error: str | None = None
    parse_stats: dict | None = None


class SubjectSummary(BaseModel):
    id: str
    name: str
    description: str
    status: SubjectStatus
    is_default: bool
    n_concepts: int
    n_questions: int
    n_flashcards: int
    n_documents: int
    n_students: int
    created_at: datetime
    published_at: datetime | None = None
    job: StudioJobOut | None = None


class StudioWorld(BaseModel):
    id: str
    name: str
    tagline: str
    emoji: str
    color: str
    concepts: list[str]


class SubjectDetail(Traced):
    subject: SubjectSummary
    documents: list[SourceDocumentOut]
    worlds: list[StudioWorld]
    diagnostic_concepts: list[str]
    warnings: list[str]
    publish_blockers: list[str]
    editable: bool


class SubjectList(Traced):
    subjects: list[SubjectSummary]


class StudioConcept(BaseModel):
    id: str
    name: str
    description: str
    prerequisites: list[str]
    depth: int
    notes_md: str
    key_points: list[str]
    n_questions: int
    n_flashcards: int
    n_misconceptions: int
    world_id: str | None = None


class StudioGraph(Traced):
    subject_id: str
    concepts: list[StudioConcept]


class StudioOption(BaseModel):
    id: str
    text: str
    is_correct: bool
    misconception_id: str | None = None
    misconception: str | None = None


class StudioQuestion(BaseModel):
    id: str
    concept_id: str
    bloom_level: BloomLevel
    stem: str
    explanation: str
    difficulty_b: float
    options: list[StudioOption]
    verifier_passed: bool | None = None
    verifier_issues: list[str]
    status: str


class StudioFlashcard(BaseModel):
    id: str
    concept_id: str
    front: str
    back: str
    status: str
    source: str


class StudioMisconception(BaseModel):
    id: str
    description: str
    correct_belief: str


class StudioConceptContent(Traced):
    concept: StudioConcept
    misconceptions: list[StudioMisconception]
    questions: list[StudioQuestion]
    flashcards: list[StudioFlashcard]


class ConceptPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    notes_md: str | None = Field(default=None, max_length=20_000)
    key_points: list[str] | None = None
    prerequisites: list[str] | None = None


class OptionPatch(BaseModel):
    id: str
    text: str = Field(min_length=1, max_length=240)


class QuestionPatch(BaseModel):
    stem: str | None = Field(default=None, min_length=10, max_length=900)
    explanation: str | None = Field(default=None, min_length=1, max_length=2000)
    options: list[OptionPatch] | None = None


class FlashcardIn(BaseModel):
    front: str = Field(min_length=1, max_length=300)
    back: str = Field(min_length=1, max_length=600)


class FlashcardCreate(FlashcardIn):
    concept_id: str


class EnrollmentStudent(BaseModel):
    id: str
    display_name: str
    is_simulated: bool
    enrolled: bool


class EnrollmentList(Traced):
    subject_id: str
    students: list[EnrollmentStudent]


class EnrollmentUpdate(BaseModel):
    student_ids: list[str] = Field(max_length=500)


class StudentSubject(BaseModel):
    id: str
    name: str
    description: str
    is_default: bool
    n_concepts: int


class StudentSubjects(Traced):
    student_id: str
    subjects: list[StudentSubject]


class OkResponse(Traced):
    ok: bool = True
