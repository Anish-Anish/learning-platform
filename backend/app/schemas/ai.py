"""Structured-output contracts for LLM features. SHARED CONTRACT (core consumes DiagnosisProposal).

Note: the diagnosis schema used for the actual LLM call is built dynamically in
`ai/diagnosis_agent.py` so concept/misconception IDs are constrained to an enum of real IDs (§13.2).
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class DiagnosisProposal(BaseModel):
    root_concept_id: str
    misconception_id: str | None
    evidence: list[str]
    path: list[str]
    confidence: float = Field(ge=0, le=1)
    needs_probe: bool
    probe_concept_id: str | None = None
    student_message: str


class LessonContent(BaseModel):
    lesson_md: str = Field(description="<=200 words, grounded only in the concept notes")
    worked_example: str
    analogy: str
    socratic_questions: list[str] = Field(description="1-2 questions that play out the wrong belief")
    citations: list[str] = Field(description="Short quotes of the note paragraphs used")


class LessonBody(BaseModel):
    lesson_md: str
    worked_example: str
    citations: list[str]


class AnalogyOut(BaseModel):
    analogy: str


class SocraticOut(BaseModel):
    questions: list[str]


class GeneratedOption(BaseModel):
    text: str
    is_correct: bool
    misconception_id: str | None = Field(description="Required for wrong options")


class GeneratedQuestion(BaseModel):
    stem: str
    explanation: str
    bloom_level: str
    difficulty_b: float
    options: list[GeneratedOption]


class GeneratedQuestionSet(BaseModel):
    questions: list[GeneratedQuestion]


class VerifierReport(BaseModel):
    passed: bool = Field(alias="pass")
    issues: list[str]
    bloom_detected: str

    model_config = {"populate_by_name": True}


class BossFlavor(BaseModel):
    name: str
    taunt: str


class TeachBotReply(BaseModel):
    reply: str
    on_topic: bool


class TeachScore(BaseModel):
    score: int = Field(ge=0, le=100)
    covered_points: list[str]
    missing_points: list[str]
    misconceptions_detected: list[str]
    feedback: str


class HintContent(BaseModel):
    hint: str
