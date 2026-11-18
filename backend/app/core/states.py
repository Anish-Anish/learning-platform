"""Concept state classification (PROJECT_CONTEXT §9.3). Pure functions.

Priority order: locked > misconception > mastered > fragile > gap > not_started.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from app.schemas.common import ConceptState


@dataclass(frozen=True)
class AttemptLite:
    """Minimal view of an attempt used for state rules."""

    correct: bool
    confidence: str  # sure / guess


@dataclass(frozen=True)
class StateThresholds:
    unlock: float = 0.7
    mastered: float = 0.8
    fragile: float = 0.5

    @classmethod
    def from_settings(cls) -> StateThresholds:
        from app.config import get_settings

        s = get_settings()
        return cls(unlock=s.unlock_threshold, mastered=s.mastered_threshold, fragile=s.fragile_threshold)


@dataclass
class StateResult:
    state: ConceptState
    reason: str
    blocking_prereqs: list[str] = field(default_factory=list)


def is_unlocked(prereq_mastery: dict[str, float], thresholds: StateThresholds) -> bool:
    return all(m >= thresholds.unlock for m in prereq_mastery.values())


def classify(
    m: float,
    n_attempts: int,
    recent: Sequence[AttemptLite],
    active_misconceptions: Sequence[str],
    prereq_mastery: dict[str, float],
    thresholds: StateThresholds | None = None,
    names: dict[str, str] | None = None,
) -> StateResult:
    """Return the concept's state plus a human-readable reason.

    `recent` is this concept's attempts, oldest first. `prereq_mastery` maps prerequisite id -> m.
    """
    t = thresholds or StateThresholds()
    names = names or {}

    blocking = [pid for pid, pm in prereq_mastery.items() if pm < t.unlock]
    # An active misconception is evidence about the concept, so it counts like an attempt for locking.
    if blocking and n_attempts == 0 and not active_misconceptions:
        blocked = ", ".join(names.get(b, b) for b in blocking)
        return StateResult("locked", f"Unlocks when these reach {t.unlock:.0%} mastery: {blocked}.", blocking)

    if active_misconceptions:
        return StateResult(
            "misconception",
            f"A confident wrong answer revealed {len(active_misconceptions)} active misconception(s).",
        )

    if n_attempts == 0:
        return StateResult("not_started", "Unlocked and ready to start.")

    last3 = list(recent)[-3:]
    strong_in_last3 = sum(1 for a in last3 if a.correct and a.confidence == "sure")
    if m >= t.mastered and n_attempts >= 3 and strong_in_last3 >= 2:
        return StateResult("mastered", f"Mastery {m:.0%} with {strong_in_last3} confident correct of the last 3.")

    last_correct = next((a for a in reversed(recent) if a.correct), None)
    if t.fragile <= m < t.mastered:
        return StateResult("fragile", f"Mastery {m:.0%}: partly there, needs more confident practice.")
    if last_correct is not None and last_correct.confidence == "guess" and m >= t.fragile:
        return StateResult("fragile", "Last correct answer was a guess, so it isn't solid yet.")
    if m >= t.mastered:
        # High estimate but not enough confirming evidence yet (n < 3 or too few confident answers).
        return StateResult("fragile", f"Mastery {m:.0%} but needs more confident correct answers to confirm.")

    return StateResult("gap", f"Mastery {m:.0%} after {n_attempts} attempt(s): a knowledge gap.")
