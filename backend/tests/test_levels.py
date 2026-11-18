"""Adventure mode: pure rules + API flows."""

from app.core.levels import fifty_removals, plan_questions, stars_for
from tests.conftest import answer


# ------------------------------------------------------------- pure rules
def test_stars_rules():
    assert stars_for(4, 4, 4, failed=False, powerups_used=0) == 3
    assert stars_for(4, 4, 3, failed=False, powerups_used=0) == 2  # flawless but one guess
    assert stars_for(4, 3, 3, failed=False, powerups_used=0) == 2  # one mistake
    assert stars_for(4, 2, 2, failed=False, powerups_used=0) == 1
    assert stars_for(4, 4, 4, failed=False, powerups_used=1) == 2  # power-ups cap at 2
    assert stars_for(4, 1, 1, failed=True, powerups_used=0) == 0


def test_plan_rises_in_bloom_and_avoids_recent_correct(graph):
    plan = plan_questions(graph, "recursion_base", set())
    assert len(plan) == 4
    blooms = [graph.questions[q].bloom_index for q in plan]
    assert blooms == sorted(blooms) and blooms[0] == 0 and blooms[-1] == 3  # spans remember..analyze
    plan2 = plan_questions(graph, "recursion_base", {"q_recursion_base_01"})
    assert "q_recursion_base_01" not in plan2


def test_fifty_leaves_exactly_one_wrong_option():
    assert len(fifty_removals("run_x", ["b", "c"])) == 1
    assert len(fifty_removals("run_x", ["b", "c", "d"])) == 2
    assert fifty_removals("run_x", ["b", "c", "d"]) == fifty_removals("run_x", ["b", "c", "d"])  # deterministic


# ------------------------------------------------------------- API
def _start_student(client, sid):
    assert client.post("/session/start", json={"student_id": sid}).status_code == 200


def _play(client, graph, run, *, wrong=0, conf="sure"):
    """Answer the run: the first `wrong` questions wrong, the rest right."""
    i = 0
    while run["status"] == "active":
        qid = run["question"]["id"]
        opt = answer(graph, qid, correct=i >= wrong)
        r = client.post(f"/levels/runs/{run['id']}/answer", json={"option_id": opt, "confidence": conf})
        assert r.status_code == 200, r.text
        body = r.json()
        run = body["run"]
        i += 1
    return run, body


def test_world_map_shape(client, student_id):
    _start_student(client, student_id)
    w = client.get(f"/students/{student_id}/world").json()
    assert len(w["worlds"]) == 7
    assert sum(len(x["levels"]) for x in w["worlds"]) == 21
    assert w["stars_max"] == 63 and w["stars_total"] == 0
    levels = {lv["concept_id"]: lv for x in w["worlds"] for lv in x["levels"]}
    assert levels["memory_basics"]["playable"] and not levels["bst_delete"]["playable"]
    assert levels["bst_delete"]["locked_reason"]
    assert w["recommended_concept_id"] in ("memory_basics", "recursion_base")


def test_locked_level_cannot_start(client, student_id):
    _start_student(client, student_id)
    r = client.post("/levels/bst_delete/start", json={"student_id": student_id})
    assert r.status_code == 409 and "locked" in r.json()["detail"].lower()


def test_flawless_run_earns_three_stars(client, graph, student_id):
    _start_student(client, student_id)
    start = client.post("/levels/recursion_base/start", json={"student_id": student_id}).json()
    run = start["run"]
    assert run["hearts"] == 3 and run["total"] == 4 and run["question"]
    assert all(set(o) == {"id", "text"} for o in run["question"]["options"])  # no answer leakage
    run, last = _play(client, graph, run)
    assert run["status"] == "completed" and run["stars"] == 3 and run["best_combo"] == 4
    assert last["new_best"] and last["best_stars"] == 3
    # stars never become XP
    assert not any(x["kind"] == "stars" for x in last["attempt"]["xp_events"])
    w = client.get(f"/students/{student_id}/world").json()
    lv = next(lv for x in w["worlds"] for lv in x["levels"] if lv["concept_id"] == "recursion_base")
    assert lv["stars"] == 3 and lv["plays"] == 1


def test_three_wrong_answers_is_game_over_and_triggers_diagnosis(client, graph, student_id):
    _start_student(client, student_id)
    run = client.post("/levels/memory_basics/start", json={"student_id": student_id}).json()["run"]
    run, last = _play(client, graph, run, wrong=3)
    assert run["status"] == "failed" and run["hearts"] == 0 and run["stars"] == 0
    assert last["attempt"]["diagnosis"]["id"]  # wrong answers still feed the root-cause tutor


def test_fifty_power_up_caps_stars(client, graph, student_id):
    _start_student(client, student_id)
    run = client.post("/levels/recursion_base/start", json={"student_id": student_id}).json()["run"]
    r = client.post(f"/levels/runs/{run['id']}/fifty").json()["run"]
    removed = r["removed_option_ids"]
    q = graph.questions[r["question"]["id"]]
    assert removed and q.correct_option.id not in removed
    assert len(q.options) - len(removed) == 2
    assert client.post(f"/levels/runs/{run['id']}/fifty").status_code == 409  # one per run
    bad = client.post(f"/levels/runs/{run['id']}/answer", json={"option_id": removed[0], "confidence": "sure"})
    assert bad.status_code == 409
    run, _ = _play(client, graph, r)
    assert run["status"] == "completed" and run["stars"] == 2


def test_resume_and_restart(client, student_id):
    _start_student(client, student_id)
    a = client.post("/levels/memory_basics/start", json={"student_id": student_id}).json()["run"]
    b = client.post("/levels/memory_basics/start", json={"student_id": student_id}).json()["run"]
    assert a["id"] == b["id"]  # resumes the active run
    c = client.post("/levels/memory_basics/start", json={"student_id": student_id, "restart": True}).json()["run"]
    assert c["id"] != a["id"]


def test_study_scroll_profile_quests_and_teacher_view(client, graph, student_id):
    _start_student(client, student_id)
    detail = client.get("/concepts/bst_property").json()
    assert detail["notes_md"] and detail["key_points"] and detail["traps"]
    run = client.post("/levels/recursion_base/start", json={"student_id": student_id}).json()["run"]
    _play(client, graph, run)
    prof = client.get(f"/students/{student_id}/profile").json()
    assert prof["stars_total"] == 3 and prof["levels_completed"] == 1 and prof["runs_played"] == 1
    assert len(prof["badges"]) >= 6 and {q["id"] for q in prof["quests"]} == {"warmup", "honest", "stars", "myth"}
    stars_q = next(q for q in prof["quests"] if q["id"] == "stars")
    assert stars_q["done"]
    game = client.get("/class/game").json()
    me = next(s for s in game["students"] if s["student_id"] == student_id)
    assert me["stars"] == 3 and me["wins"] == 1
    lvl = next(lv for lv in game["levels"] if lv["concept_id"] == "recursion_base")
    assert lvl["plays"] >= 1 and lvl["completion_rate"] is not None
    assert any(r["student_id"] == student_id for r in game["recent_runs"])
