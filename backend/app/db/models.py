"""SQLAlchemy models (PROJECT_CONTEXT §7).

Additions beyond §7 (internal, additive): `sessions`, `scheduled_items` (probe / remediation queue
used by the adaptive engine), `request_metrics` (endpoint latency for /admin), plus a few nullable
columns (attempts.session_id / boss_battle_id / progress_awarded, mastery_state.misconception_progress).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


class Base(DeclarativeBase):
    pass


# ------------------------------------------------------------------ subjects (5A)
class Subject(Base):
    """A learnable subject. The original seed is the default subject; studio uploads create the rest."""

    __tablename__ = "subjects"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(Text, default="")
    owner_id: Mapped[str] = mapped_column(String, default="teacher")
    # draft -> processing -> review -> published  (failed on pipeline error)
    status: Mapped[str] = mapped_column(String, default="draft")
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    worlds: Mapped[list | None] = mapped_column(JSON, nullable=True)
    diagnostic_concepts: Mapped[list | None] = mapped_column(JSON, nullable=True)
    content_version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Enrollment(Base):
    __tablename__ = "enrollments"
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"), primary_key=True)
    subject_id: Mapped[str] = mapped_column(ForeignKey("subjects.id"), primary_key=True)
    assigned_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class StudioJob(Base):
    """One run of the ingestion pipeline for a subject (progress is polled by the studio UI)."""

    __tablename__ = "studio_jobs"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: new_id("job"))
    subject_id: Mapped[str] = mapped_column(ForeignKey("subjects.id"), index=True)
    trace_id: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="queued")  # queued / running / done / failed
    stage: Mapped[str] = mapped_column(String, default="queued")
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    message: Mapped[str] = mapped_column(Text, default="")
    stats: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Flashcard(Base):
    __tablename__ = "flashcards"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: new_id("fc"))
    subject_id: Mapped[str] = mapped_column(ForeignKey("subjects.id"), index=True)
    concept_id: Mapped[str] = mapped_column(ForeignKey("concepts.id"), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    front: Mapped[str] = mapped_column(Text)
    back: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String, default="draft")
    source: Mapped[str] = mapped_column(String, default="generated")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


# ------------------------------------------------------------------ content
class Concept(Base):
    __tablename__ = "concepts"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    subject_id: Mapped[str] = mapped_column(String, index=True, default="data_structures",
                                            server_default="data_structures")
    position: Mapped[int] = mapped_column(Integer, default=0, server_default="0")  # order in the source material
    name: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(Text)
    notes_md: Mapped[str] = mapped_column(Text, default="")
    key_points: Mapped[list] = mapped_column(JSON, default=list)
    bloom_levels: Mapped[list] = mapped_column(JSON, default=list)
    content_version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String, default="approved")


class Prerequisite(Base):
    __tablename__ = "prerequisites"
    concept_id: Mapped[str] = mapped_column(ForeignKey("concepts.id"), primary_key=True)
    prerequisite_id: Mapped[str] = mapped_column(ForeignKey("concepts.id"), primary_key=True)


class Misconception(Base):
    __tablename__ = "misconceptions"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    concept_id: Mapped[str] = mapped_column(ForeignKey("concepts.id"))
    description: Mapped[str] = mapped_column(Text)
    correct_belief: Mapped[str] = mapped_column(Text)
    analogy: Mapped[str] = mapped_column(Text, default="")
    socratic: Mapped[list] = mapped_column(JSON, default=list)
    replay_id: Mapped[str | None] = mapped_column(String, nullable=True)


class Question(Base):
    __tablename__ = "questions"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    concept_id: Mapped[str] = mapped_column(ForeignKey("concepts.id"), index=True)
    bloom_level: Mapped[str] = mapped_column(String)
    type: Mapped[str] = mapped_column(String, default="mcq")
    stem: Mapped[str] = mapped_column(Text)
    explanation: Mapped[str] = mapped_column(Text)
    difficulty_b: Mapped[float] = mapped_column(Float, default=0.0)
    hints: Mapped[list] = mapped_column(JSON, default=list)
    content_version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String, default="approved")
    verifier_report: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    source: Mapped[str] = mapped_column(String, default="seed")
    options: Mapped[list[Option]] = relationship(
        back_populates="question", cascade="all, delete-orphan", order_by="Option.position"
    )


class Option(Base):
    __tablename__ = "options"
    pk: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id: Mapped[str] = mapped_column(String)  # local id within the question ("a", "b", ...)
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    text: Mapped[str] = mapped_column(Text)
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False)
    misconception_id: Mapped[str | None] = mapped_column(ForeignKey("misconceptions.id"), nullable=True)
    question: Mapped[Question] = relationship(back_populates="options")


# ------------------------------------------------------------------ learners
class Student(Base):
    __tablename__ = "students"
    id: Mapped[str] = mapped_column(String, primary_key=True)  # pseudonymous
    display_name: Mapped[str] = mapped_column(String)  # never sent to an LLM
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=False)
    planted_misconceptions: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Session(Base):
    __tablename__ = "sessions"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: new_id("ses"))
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Attempt(Base):
    """The event log. Learner state can be rebuilt by replaying these (core/replay.py)."""

    __tablename__ = "attempts"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: new_id("att"))
    seq: Mapped[int] = mapped_column(Integer, default=0, index=True)  # per-student order
    trace_id: Mapped[str] = mapped_column(String, index=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"), index=True)
    session_id: Mapped[str | None] = mapped_column(String, nullable=True)
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"), index=True)
    concept_id: Mapped[str] = mapped_column(String, index=True)
    option_id: Mapped[str | None] = mapped_column(String, nullable=True)
    answer_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_correct: Mapped[bool] = mapped_column(Boolean)
    confidence: Mapped[str] = mapped_column(String)
    reasoning_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    time_ms: Mapped[int] = mapped_column(Integer, default=0)
    hints_used: Mapped[int] = mapped_column(Integer, default=0)
    selected_misconception_id: Mapped[str | None] = mapped_column(String, nullable=True)
    boss_battle_id: Mapped[str | None] = mapped_column(String, nullable=True)
    progress_awarded: Mapped[bool] = mapped_column(Boolean, default=True)
    theta_before: Mapped[float] = mapped_column(Float, default=0.0)
    theta_after: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class MasteryState(Base):
    __tablename__ = "mastery_state"
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"), primary_key=True)
    concept_id: Mapped[str] = mapped_column(ForeignKey("concepts.id"), primary_key=True)
    theta: Mapped[float] = mapped_column(Float, default=0.0)
    n_attempts: Mapped[int] = mapped_column(Integer, default=0)
    state: Mapped[str] = mapped_column(String, default="not_started")
    active_misconception_ids: Mapped[list] = mapped_column(JSON, default=list)
    misconception_progress: Mapped[dict] = mapped_column(JSON, default=dict)
    ever_mastered: Mapped[bool] = mapped_column(Boolean, default=False)
    ever_unlocked: Mapped[bool] = mapped_column(Boolean, default=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    review_strength: Mapped[float] = mapped_column(Float, default=3.0)


class Diagnosis(Base):
    __tablename__ = "diagnoses"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: new_id("dx"))
    trace_id: Mapped[str] = mapped_column(String, index=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"), index=True)
    trigger_attempt_id: Mapped[str] = mapped_column(String)
    failed_concept_id: Mapped[str] = mapped_column(String)
    origin_concept_id: Mapped[str | None] = mapped_column(String, nullable=True)  # start of a probe chain
    root_concept_id: Mapped[str | None] = mapped_column(String, nullable=True)
    misconception_id: Mapped[str | None] = mapped_column(String, nullable=True)
    evidence: Mapped[list] = mapped_column(JSON, default=list)
    path: Mapped[list] = mapped_column(JSON, default=list)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    needs_probe: Mapped[bool] = mapped_column(Boolean, default=False)
    probe_concept_id: Mapped[str | None] = mapped_column(String, nullable=True)
    student_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String, default="pending")
    source: Mapped[str | None] = mapped_column(String, nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ScheduledItem(Base):
    """Probe / remediation queue consumed by the adaptive engine (§9.4 steps 2-3)."""

    __tablename__ = "scheduled_items"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: new_id("sch"))
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"), index=True)
    kind: Mapped[str] = mapped_column(String)  # probe / remediation
    concept_id: Mapped[str] = mapped_column(String)
    misconception_id: Mapped[str | None] = mapped_column(String, nullable=True)
    min_bloom: Mapped[str | None] = mapped_column(String, nullable=True)
    question_id: Mapped[str | None] = mapped_column(String, nullable=True)
    reason: Mapped[str] = mapped_column(Text)
    source_id: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="pending")  # pending / done / skipped
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class XPEvent(Base):
    __tablename__ = "xp_events"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: new_id("xp"))
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"), index=True)
    kind: Mapped[str] = mapped_column(String)
    amount: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(Text)
    concept_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class StudentBadge(Base):
    __tablename__ = "badges"
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"), primary_key=True)
    badge_id: Mapped[str] = mapped_column(String, primary_key=True)
    earned_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class BossBattle(Base):
    __tablename__ = "boss_battles"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: new_id("boss"))
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"), index=True)
    name: Mapped[str] = mapped_column(String, default="Root Boss")
    taunt: Mapped[str] = mapped_column(Text, default="")
    question_ids: Mapped[list] = mapped_column(JSON, default=list)
    misconception_ids: Mapped[list] = mapped_column(JSON, default=list)
    hp: Mapped[int] = mapped_column(Integer, default=100)
    max_hp: Mapped[int] = mapped_column(Integer, default=100)
    current_index: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String, default="active")  # active / won / lost
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class LevelRun(Base):
    """Adventure mode: one play-through of a level (concept). Attempts inside it are normal attempts."""

    __tablename__ = "level_runs"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: new_id("run"))
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"), index=True)
    concept_id: Mapped[str] = mapped_column(String, index=True)
    question_ids: Mapped[list] = mapped_column(JSON, default=list)
    attempt_ids: Mapped[list] = mapped_column(JSON, default=list)
    current_index: Mapped[int] = mapped_column(Integer, default=0)
    hearts: Mapped[int] = mapped_column(Integer, default=3)
    max_hearts: Mapped[int] = mapped_column(Integer, default=3)
    correct: Mapped[int] = mapped_column(Integer, default=0)
    correct_sure: Mapped[int] = mapped_column(Integer, default=0)
    combo: Mapped[int] = mapped_column(Integer, default=0)
    best_combo: Mapped[int] = mapped_column(Integer, default=0)
    fifty_left: Mapped[int] = mapped_column(Integer, default=1)
    powerups_used: Mapped[int] = mapped_column(Integer, default=0)
    removed_options: Mapped[dict] = mapped_column(JSON, default=dict)  # question_id -> [option ids]
    status: Mapped[str] = mapped_column(String, default="active")  # active / completed / failed / abandoned
    stars: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class TeachSession(Base):
    __tablename__ = "teach_sessions"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: new_id("teach"))
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"), index=True)
    concept_id: Mapped[str] = mapped_column(String)
    transcript: Mapped[list] = mapped_column(JSON, default=list)
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    covered_points: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


# ------------------------------------------------------------------ AI / ops
class GeneratedCache(Base):
    __tablename__ = "generated_cache"
    key: Mapped[str] = mapped_column(String, primary_key=True)
    kind: Mapped[str] = mapped_column(String)
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class LLMCall(Base):
    __tablename__ = "llm_calls"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: new_id("llm"))
    trace_id: Mapped[str] = mapped_column(String, index=True)
    student_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    feature: Mapped[str] = mapped_column(String, index=True)
    prompt_name: Mapped[str] = mapped_column(String)
    prompt_version: Mapped[str] = mapped_column(String)
    model: Mapped[str] = mapped_column(String)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    schema_ok: Mapped[bool] = mapped_column(Boolean, default=True)
    retries: Mapped[int] = mapped_column(Integer, default=0)
    fallback_used: Mapped[bool] = mapped_column(Boolean, default=False)
    guardrail_flags: Mapped[list] = mapped_column(JSON, default=list)
    cache_hit: Mapped[bool] = mapped_column(Boolean, default=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    # learner = student-facing (counts toward cost per session) / studio = teacher content generation
    scope: Mapped[str] = mapped_column(String, default="learner", server_default="learner", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class RequestMetric(Base):
    __tablename__ = "request_metrics"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trace_id: Mapped[str] = mapped_column(String)
    method: Mapped[str] = mapped_column(String)
    route: Mapped[str] = mapped_column(String, index=True)
    status_code: Mapped[int] = mapped_column(Integer)
    latency_ms: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class AppLog(Base):
    """Structured application logs (INFO+), kept for the admin Logs page; pruned by age and row count."""

    __tablename__ = "app_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    level: Mapped[str] = mapped_column(String, index=True)
    event: Mapped[str] = mapped_column(String, index=True)
    logger: Mapped[str | None] = mapped_column(String, nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    student_id: Mapped[str | None] = mapped_column(String, nullable=True)
    data: Mapped[dict] = mapped_column(JSON, default=dict)


class Feedback(Base):
    __tablename__ = "feedback"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: new_id("fb"))
    student_id: Mapped[str] = mapped_column(String, index=True)
    target_kind: Mapped[str] = mapped_column(String)
    target_id: Mapped[str] = mapped_column(String)
    rating: Mapped[int] = mapped_column(Integer)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String, default="open")  # review queue (teacher queue in 5A)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


# ------------------------------------------------------------------ 5A source material
class SourceDocument(Base):
    __tablename__ = "source_documents"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: new_id("doc"))
    owner_id: Mapped[str] = mapped_column(String)
    subject_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    filename: Mapped[str] = mapped_column(String)
    storage_path: Mapped[str | None] = mapped_column(String, nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    page_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    parse_stats: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    parsed_text: Mapped[str] = mapped_column(Text, default="")
    # uploaded -> parsed | failed
    status: Mapped[str] = mapped_column(String, default="uploaded")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
