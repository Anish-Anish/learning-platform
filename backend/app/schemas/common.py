"""Shared enums / literal types. SHARED CONTRACT — change only with team agreement."""

from __future__ import annotations

from typing import Literal

BloomLevel = Literal["remember", "understand", "apply", "analyze"]
BLOOM_ORDER: tuple[BloomLevel, ...] = ("remember", "understand", "apply", "analyze")

QuestionType = Literal["mcq", "short"]
ContentStatus = Literal["draft", "approved"]
ContentSource = Literal["seed", "generated", "teacher"]

Confidence = Literal["sure", "guess"]
ConfidenceSignal = Literal["mastered_signal", "fragile_signal", "misconception_signal", "gap_signal"]

# Concept states, in priority order (PROJECT_CONTEXT §9.3).
ConceptState = Literal["locked", "misconception", "mastered", "fragile", "gap", "not_started"]

# §7 lists proposed/applied/rejected. `pending` = agent still running (row created at enqueue time
# so the client can poll GET /diagnoses/{id}).
DiagnosisStatus = Literal["pending", "proposed", "applied", "rejected"]

Phase = Literal["diagnostic", "probe", "remediation", "practice", "boss", "complete"]

NextActionKind = Literal["next_question", "lesson", "probe", "boss", "complete"]

XPKind = Literal[
    "concept_mastered",
    "misconception_cleared",
    "boss_defeated",
    "teach_score",
    "daily_streak",
    "unlock",
    "hint",
]

BadgeId = Literal["myth_buster", "root_finder", "well_calibrated", "teachers_pet", "streak_3", "streak_7"]

AlertKind = Literal["confident_wrong", "class_misconception", "no_progress", "low_calibration"]
Severity = Literal["info", "warning", "critical"]

FeedbackTarget = Literal["lesson", "question"]
