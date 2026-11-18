from app.core.adaptive import bloom_target
from app.core.graph import find_cycle, topo_sort
from app.core.states import AttemptLite, StateThresholds, classify

T = StateThresholds()
OK = AttemptLite(True, "sure")
GUESS = AttemptLite(True, "guess")
BAD = AttemptLite(False, "sure")


def test_locked_when_prereq_weak_and_no_attempts():
    r = classify(0.5, 0, [], [], {"a": 0.6}, T, {"a": "Arrays"})
    assert r.state == "locked"
    assert "Arrays" in r.reason


def test_attempts_unlock_even_if_prereq_weak():
    assert classify(0.4, 1, [BAD], [], {"a": 0.2}, T).state == "gap"


def test_misconception_outranks_mastery():
    assert classify(0.95, 5, [OK, OK, OK], ["x.m1"], {}, T).state == "misconception"


def test_active_misconception_shows_on_locked_concept():
    assert classify(0.5, 0, [], ["x.m1"], {"a": 0.1}, T).state == "misconception"


def test_mastered_rules():
    assert classify(0.85, 3, [OK, OK, BAD], [], {}, T).state == "mastered"
    # too few attempts
    assert classify(0.85, 2, [OK, OK], [], {}, T).state == "fragile"
    # last 3 lack two confident corrects
    assert classify(0.85, 3, [GUESS, GUESS, OK], [], {}, T).state == "fragile"


def test_fragile_gap_not_started():
    assert classify(0.6, 2, [OK, OK], [], {}, T).state == "fragile"
    assert classify(0.45, 2, [OK, GUESS], [], {}, T).state == "gap"
    assert classify(0.5, 0, [], [], {}, T).state == "not_started"
    assert classify(0.5, 0, [], [], {"a": 0.9}, T).state == "not_started"


def test_bloom_ladder():
    levels = [0, 1, 2, 3]
    assert bloom_target([], levels) == (0, False)
    assert bloom_target([(True, "sure", 0), (True, "sure", 0)], levels) == (1, True)
    # a wrong answer resets the streak
    assert bloom_target([(True, "sure", 0), (False, "sure", 0), (True, "sure", 0)], levels)[0] == 0
    # demonstrating a higher level jumps to it
    assert bloom_target([(True, "sure", 2)], levels)[0] == 2
    # guesses don't count
    assert bloom_target([(True, "guess", 0), (True, "guess", 0)], levels)[0] == 0
    # capped at the highest available level
    assert bloom_target([(True, "sure", 3)] * 4, levels)[0] == 3


def test_dag_helpers():
    assert find_cycle({"a": [], "b": ["a"], "c": ["b"]}) is None
    assert find_cycle({"a": ["c"], "b": ["a"], "c": ["b"]}) is not None
    order = topo_sort({"c": ["b"], "b": ["a"], "a": []})
    assert order.index("a") < order.index("b") < order.index("c")


def test_seed_graph(graph):
    assert len(graph.concepts) == 21
    assert graph.concepts["bst_delete"].depth > graph.concepts["linked_lists"].depth
    assert "recursion_base" in graph.ancestors("bst_ops")
    assert graph.prereq_path("bst_ops", "recursion_base") == ["bst_ops", "recursion_base"]
    assert "q_bst_ops_02" in graph.questions_by_misconception["recursion_base.m1"]
