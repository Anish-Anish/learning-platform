"""Learner model math (PROJECT_CONTEXT §9.1–9.2). Pure functions — no DB, no LLM.

theta = student ability on a concept, b = question difficulty.
p = 1 / (1 + exp(-(theta - b))) is the predicted chance of answering correctly.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass

from app.schemas.common import Confidence, ConfidenceSignal


@dataclass(frozen=True)
class LearnerParams:
    k_student: float = 1.0
    k_question: float = 0.05
    w_correct_sure: float = 1.0
    w_correct_guess: float = 0.5
    w_wrong_sure: float = 1.2
    w_wrong_guess: float = 0.8

    @classmethod
    def from_settings(cls) -> LearnerParams:
        from app.config import get_settings

        s = get_settings()
        return cls(
            k_student=s.k_student,
            k_question=s.k_question,
            w_correct_sure=s.w_correct_sure,
            w_correct_guess=s.w_correct_guess,
            w_wrong_sure=s.w_wrong_sure,
            w_wrong_guess=s.w_wrong_guess,
        )


def sigmoid(x: float) -> float:
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    z = math.exp(x)
    return z / (1.0 + z)


def p_correct(theta: float, b: float) -> float:
    """Predicted probability that a student with ability theta answers a question of difficulty b."""
    return sigmoid(theta - b)


def mastery(theta: float) -> float:
    """Mastery probability shown in the UI: m = sigmoid(theta)."""
    return sigmoid(theta)


def confidence_weight(correct: bool, confidence: Confidence, params: LearnerParams) -> float:
    if correct:
        return params.w_correct_sure if confidence == "sure" else params.w_correct_guess
    return params.w_wrong_sure if confidence == "sure" else params.w_wrong_guess


def hint_multiplier(hints_used: int) -> float:
    """Each hint reduces positive credit by 25%, floored at 0.25."""
    return max(0.25, 1.0 - 0.25 * max(0, hints_used))


@dataclass(frozen=True)
class ThetaUpdate:
    theta: float
    b: float
    p: float
    delta: float


def update(
    theta: float,
    b: float,
    correct: bool,
    confidence: Confidence,
    hints_used: int = 0,
    params: LearnerParams | None = None,
    allow_progress: bool = True,
    update_b: bool = False,
) -> ThetaUpdate:
    """Elo / 1-PL IRT update.

    theta += K_s * w * (y - p);  b -= K_q * (y - p)
    Hints scale positive updates; anti-farming (`allow_progress=False`) blocks positive updates only.
    """
    params = params or LearnerParams()
    y = 1.0 if correct else 0.0
    p = p_correct(theta, b)
    delta = params.k_student * confidence_weight(correct, confidence, params) * (y - p)
    if delta > 0:
        delta *= hint_multiplier(hints_used)
        if not allow_progress:
            delta = 0.0
    new_b = b - params.k_question * (y - p) if update_b else b
    return ThetaUpdate(theta=theta + delta, b=new_b, p=p, delta=delta)


def classify_signal(correct: bool, confidence: Confidence) -> ConfidenceSignal:
    """Confidence matrix (§9.2)."""
    if correct:
        return "mastered_signal" if confidence == "sure" else "fragile_signal"
    return "misconception_signal" if confidence == "sure" else "gap_signal"


@dataclass(frozen=True)
class CalibrationCounts:
    sure_correct: int = 0
    sure_wrong: int = 0
    guess_correct: int = 0
    guess_wrong: int = 0

    @property
    def n(self) -> int:
        return self.sure_correct + self.sure_wrong + self.guess_correct + self.guess_wrong

    @property
    def score(self) -> float | None:
        """Share of attempts where confidence matched correctness (sure&correct or guess&wrong)."""
        if self.n == 0:
            return None
        return (self.sure_correct + self.guess_wrong) / self.n


def calibration(attempts: Iterable[tuple[bool, str]]) -> CalibrationCounts:
    sc = sw = gc = gw = 0
    for correct, confidence in attempts:
        if confidence == "sure":
            if correct:
                sc += 1
            else:
                sw += 1
        else:
            if correct:
                gc += 1
            else:
                gw += 1
    return CalibrationCounts(sc, sw, gc, gw)
