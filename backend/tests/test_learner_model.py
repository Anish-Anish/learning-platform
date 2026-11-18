import math

import pytest

from app.core.learner_model import (
    LearnerParams,
    calibration,
    classify_signal,
    confidence_weight,
    hint_multiplier,
    mastery,
    p_correct,
    sigmoid,
    update,
)

P = LearnerParams(k_student=0.4, k_question=0.05)


def test_sigmoid_and_p():
    assert sigmoid(0) == 0.5
    assert p_correct(0.0, 0.0) == 0.5
    assert p_correct(1.0, 0.0) == pytest.approx(1 / (1 + math.exp(-1)))
    assert sigmoid(-800) == pytest.approx(0.0)  # numerically stable
    assert mastery(0.0) == 0.5


def test_confidence_weights_match_spec():
    assert confidence_weight(True, "sure", P) == 1.0
    assert confidence_weight(True, "guess", P) == 0.5
    assert confidence_weight(False, "sure", P) == 1.2
    assert confidence_weight(False, "guess", P) == 0.8


def test_theta_update_formula():
    # theta += K_s * w * (y - p); p = 0.5 at theta=b=0
    u = update(0.0, 0.0, True, "sure", params=P)
    assert u.p == 0.5
    assert u.theta == pytest.approx(0.4 * 1.0 * 0.5)
    u = update(0.0, 0.0, False, "sure", params=P)
    assert u.theta == pytest.approx(-0.4 * 1.2 * 0.5)
    u = update(0.0, 0.0, True, "guess", params=P)
    assert u.theta == pytest.approx(0.4 * 0.5 * 0.5)


def test_question_difficulty_update_is_optional():
    assert update(0.0, 0.3, True, "sure", params=P).b == 0.3
    u = update(0.0, 0.0, True, "sure", params=P, update_b=True)
    assert u.b == pytest.approx(0.0 - 0.05 * 0.5)


def test_hints_scale_positive_updates_only():
    assert hint_multiplier(0) == 1.0
    assert hint_multiplier(1) == 0.75
    assert hint_multiplier(3) == 0.25
    assert hint_multiplier(10) == 0.25  # floor
    plain = update(0.0, 0.0, True, "sure", 0, P).delta
    hinted = update(0.0, 0.0, True, "sure", 2, P).delta
    assert hinted == pytest.approx(plain * 0.5)
    # negative update not softened by hints
    assert update(0.0, 0.0, False, "sure", 2, P).delta == update(0.0, 0.0, False, "sure", 0, P).delta


def test_anti_farming_blocks_only_positive_progress():
    assert update(0.0, 0.0, True, "sure", params=P, allow_progress=False).delta == 0.0
    assert update(0.0, 0.0, False, "sure", params=P, allow_progress=False).delta < 0


def test_confidence_matrix():
    assert classify_signal(True, "sure") == "mastered_signal"
    assert classify_signal(True, "guess") == "fragile_signal"
    assert classify_signal(False, "sure") == "misconception_signal"
    assert classify_signal(False, "guess") == "gap_signal"


def test_calibration_score():
    c = calibration([(True, "sure"), (False, "guess"), (False, "sure"), (True, "guess")])
    assert c.n == 4
    assert c.score == 0.5
    assert calibration([]).score is None


def test_repeated_correct_answers_converge_upward():
    theta = 0.0
    for _ in range(20):
        theta = update(theta, 0.0, True, "sure", params=P).theta
    assert mastery(theta) > 0.8
