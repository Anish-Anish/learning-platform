"""Content contracts: concepts, misconceptions, questions. SHARED CONTRACT."""

from __future__ import annotations

from pydantic import BaseModel, Field

from .common import BloomLevel, ContentSource, ContentStatus, QuestionType


class SeedConcept(BaseModel):
    id: str
    name: str
    description: str
    prerequisites: list[str] = Field(default_factory=list)
    key_points: list[str]
    bloom_levels: list[BloomLevel] = Field(
        default_factory=lambda: ["remember", "understand", "apply", "analyze"]
    )


class SeedMisconception(BaseModel):
    id: str  # "<concept_id>.mN"
    concept_id: str
    description: str
    correct_belief: str
    # Static, human-written fallback content used when the LLM is unavailable.
    analogy: str = ""
    socratic: list[str] = Field(default_factory=list)
    replay_id: str | None = None


class SeedOption(BaseModel):
    id: str
    text: str
    is_correct: bool
    misconception_id: str | None = None


class SeedQuestion(BaseModel):
    id: str
    concept_id: str
    bloom_level: BloomLevel
    type: QuestionType = "mcq"
    stem: str
    explanation: str
    difficulty_b: float = 0.0
    options: list[SeedOption]
    hints: list[str] = Field(default_factory=list)
    status: ContentStatus = "approved"
    source: ContentSource = "seed"
    content_version: int = 1


class ConceptOut(BaseModel):
    id: str
    name: str
    description: str
    prerequisites: list[str]
    key_points: list[str]
    content_version: int
    status: ContentStatus


class MisconceptionOut(BaseModel):
    id: str
    concept_id: str
    description: str
    correct_belief: str
    replay_id: str | None = None


class OptionPublic(BaseModel):
    """An option as shown to students — never includes is_correct."""

    id: str
    text: str


class QuestionPublic(BaseModel):
    id: str
    concept_id: str
    concept_name: str
    bloom_level: BloomLevel
    type: QuestionType
    stem: str
    options: list[OptionPublic]
    has_hints: bool = False
