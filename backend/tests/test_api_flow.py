"""Contract + integration tests through the real API (offline mode)."""

import json

from sqlalchemy import select

from app.core.replay import rebuild
from app.core.student_state import load_rows
from app.db import models as m
from tests.conftest import answer


def _start(client, sid):
    r = client.post("/session/start", json={"student_id": sid})
    assert r.status_code == 200
    body = r.json()
    assert body["trace_id"] and body["session_id"]
    return body


def _attempt(client, sid, qid, option, conf="sure", **kw):
    r = client.post("/attempts", json={"student_id": sid, "question_id": qid, "option_id": option,
                                       "confidence": conf, "time_ms": 1000, **kw})
    assert r.status_code == 200, r.text
    return r.json()


def _sse(text):
    events = []
    for block in text.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.split("\n") if ": " in line)
        events.append((lines.get("event"), json.loads(lines.get("data", "null"))))
    return events


def test_public_question_hides_answer(client, student_id):
    body = _start(client, student_id)
    q = body["next"]["question"]
    assert body["next"]["phase"] == "diagnostic"
    assert all(set(o) == {"id", "text"} for o in q["options"])
    assert body["next"]["reason"]


def test_diagnostic_spans_five_concepts(client, graph, student_id):
    nxt = _start(client, student_id)["next"]
    seen = []
    for _ in range(5):
        q = nxt["question"]
        seen.append(q["concept_id"])
        _attempt(client, student_id, q["id"], answer(graph, q["id"]))
        nxt = client.get("/next-question", params={"student_id": student_id}).json()
    assert len(set(seen)) == 5
    assert nxt["phase"] != "diagnostic"


def test_root_cause_loop_end_to_end(client, graph, student_id):
    """Demo path: confident-wrong BST answer -> probe prerequisite -> root found -> lesson -> checks -> cleared."""
    _start(client, student_id)
    a = _attempt(client, student_id, "q_bst_ops_02", answer(graph, "q_bst_ops_02", misconception="recursion_base.m1"))
    assert a["signal"] == "misconception_signal"
    assert a["concept_state"]["state"] == "misconception"
    assert a["next_action"]["kind"] == "probe" and a["next_action"]["concept_id"] == "recursion_base"
    dx = client.get(f"/diagnoses/{a['diagnosis']['id']}").json()
    assert dx["needs_probe"] and dx["path"] == ["bst_ops", "recursion_base"]

    # Skip the diagnostic: the probe is scheduled ahead of default practice, but diagnostic comes first;
    # answer the probe question directly.
    nxt = client.get("/next-question", params={"student_id": student_id}).json()
    assert nxt["phase"] in ("diagnostic", "probe")
    probe_q = next(q for q in graph.questions_by_misconception["recursion_base.m1"] if q.startswith("q_recursion_base"))
    a2 = _attempt(client, student_id, probe_q, answer(graph, probe_q, misconception="recursion_base.m1"))
    assert a2["next_action"]["kind"] == "lesson"
    dx2 = client.get(f"/diagnoses/{a2['diagnosis']['id']}").json()
    assert dx2["status"] == "applied" and dx2["root_concept_id"] == "recursion_base"
    assert dx2["misconception_id"] == "recursion_base.m1" and not dx2["needs_probe"]

    r = client.get("/lesson/recursion_base", params={"student_id": student_id, "misconception_id": "recursion_base.m1"})
    events = _sse(r.text)
    names = [e for e, _ in events]
    assert names[0] == "meta" and "delta" in names and names[-2:] == ["lesson", "done"]
    lesson = dict(events)["lesson"]
    checks = lesson["mastery_check_question_ids"]
    assert len(checks) == 2 and lesson["analogy"] and lesson["socratic_questions"]
    # mastery checks: one Bloom level above the slip
    probe_bloom = graph.questions[probe_q].bloom_index
    assert all(graph.questions[c].bloom_index >= min(probe_bloom + 1, 3) for c in checks)

    cleared = []
    for qid in checks:
        res = _attempt(client, student_id, qid, answer(graph, qid))
        cleared += res["cleared_misconception_ids"]
        badges = [b["badge_id"] for b in res["badges"]]
    assert "recursion_base.m1" in cleared
    assert "myth_buster" in badges
    assert res["next_action"]["kind"] == "boss"

    report = client.get(f"/students/{student_id}/report").json()
    assert report["root_gaps"][0]["concept_id"] in ("recursion_base", "bst_ops")
    assert report["xp_total"] >= 150


def test_probe_answered_correctly_points_root_back(client, graph, student_id):
    _start(client, student_id)
    a = _attempt(client, student_id, "q_bst_ops_02", answer(graph, "q_bst_ops_02", misconception="recursion_base.m1"))
    assert a["next_action"]["kind"] == "probe"
    # walk the diagnostic, then the probe question is served
    for _ in range(8):
        nxt = client.get("/next-question", params={"student_id": student_id}).json()
        q = nxt["question"]
        if nxt["phase"] == "probe":
            res = _attempt(client, student_id, q["id"], answer(graph, q["id"]))
            assert res["next_action"]["kind"] == "lesson"
            assert res["next_action"]["concept_id"] == "bst_ops"
            return
        _attempt(client, student_id, q["id"], answer(graph, q["id"]))
    raise AssertionError("probe was never scheduled")


def test_anti_farming(client, graph, student_id):
    _start(client, student_id)
    a1 = _attempt(client, student_id, "q_arrays_01", answer(graph, "q_arrays_01"))
    a2 = _attempt(client, student_id, "q_arrays_01", answer(graph, "q_arrays_01"))
    assert a1["progress_awarded"] and not a2["progress_awarded"]
    assert a2["concept_state"]["mastery"] == a1["concept_state"]["mastery"]


def test_hints_cost_xp(client, graph, student_id):
    _start(client, student_id)
    h = client.get("/hint/q_arrays_02", params={"level": 2, "student_id": student_id}).json()
    correct = graph.questions["q_arrays_02"].correct_option.text
    assert h["hint"] and correct not in h["hint"]
    a = _attempt(client, student_id, "q_arrays_02", answer(graph, "q_arrays_02"), hints_used=2)
    assert any(x["kind"] == "hint" and x["amount"] == -20 for x in a["xp_events"])


def test_unknown_option_is_422(client, student_id):
    _start(client, student_id)
    r = client.post("/attempts", json={"student_id": student_id, "question_id": "q_arrays_01", "option_id": "zz",
                                       "confidence": "sure"})
    assert r.status_code == 422


def test_map_and_report_shapes(client, graph, student_id):
    _start(client, student_id)
    mp = client.get(f"/students/{student_id}/map").json()
    assert len(mp["nodes"]) == 21 and len(mp["edges"]) > 20
    states = {n["id"]: n["state"] for n in mp["nodes"]}
    assert states["memory_basics"] == "not_started" and states["bst_delete"] == "locked"
    rep = client.get(f"/students/{student_id}/report").json()
    assert {b["level"] for b in rep["bloom_radar"]} == {"remember", "understand", "apply", "analyze"}
    assert rep["next_step"]["label"]


def test_boss_battle_win_clears_misconception(client, graph, student_id):
    _start(client, student_id)
    _attempt(client, student_id, "q_queues_02", answer(graph, "q_queues_02", misconception="queues.m1"))
    b = client.get(f"/boss/{student_id}").json()
    assert b["status"] == "active" and "queues.m1" in b["misconception_ids"] and len(b["questions"]) >= 3
    blooms = [graph.questions[q["id"]].bloom_index for q in b["questions"]]
    assert blooms == sorted(blooms)
    cleared = []
    for q in b["questions"]:
        res = client.post(f"/boss/{b['id']}/attempt", json={"question_id": q["id"], "option_id": answer(graph, q["id"]),
                                                            "confidence": "sure"}).json()
        cleared += res["cleared_misconception_ids"]
        if res["status"] != "active":
            break
    assert res["status"] == "won"
    assert any(x["kind"] == "boss_defeated" for x in res["xp_events"])
    assert "queues.m1" in cleared
    mp = client.get(f"/students/{student_id}/map").json()
    assert not any("queues.m1" in n["active_misconception_ids"] for n in mp["nodes"])


def test_teach_the_bot(client, student_id):
    _start(client, student_id)
    r = client.post("/teach/stacks", json={"student_id": student_id, "message": "A stack is last in, first out."})
    ev = _sse(r.text)
    sess = ev[0][1]["session_id"]
    done = ev[-1][1]
    assert ev[-1][0] == "done" and done["reply"] and 0 <= done["coverage"] <= 1
    r = client.post("/teach/stacks", json={"student_id": student_id, "session_id": sess,
                                           "message": "Push adds to the top and pop removes from the top, both O(1). "
                                                      "Popping an empty stack is an underflow error you must check."})
    s = client.post(f"/teach/{sess}/score").json()
    assert 0 <= s["score"] <= 100 and s["covered_points"]


def test_class_endpoints_and_admin(client):
    from app.observability.writer import flush

    flush()
    hm = client.get("/class/heatmap").json()
    assert hm["concepts"] and hm["students"]
    assert len(hm["cells"]) == len(hm["students"]) * len(hm["concepts"])
    al = client.get("/class/alerts").json()
    assert "alerts" in al and "clusters" in al
    for a in al["alerts"]:
        assert a["reason"] and a["message"]
    mt = client.get("/admin/metrics").json()
    assert mt["llm_mode"] == "offline"
    assert mt["ai_quality"]["verifier_pass_rate"] == 1.0
    assert mt["system"]["requests"] > 0
    tr = client.get("/admin/traces", params={"limit": 5}).json()
    assert len(tr["calls"]) <= 5
    fb = client.post("/feedback", json={"student_id": "x", "target_kind": "question", "target_id": "q_arrays_01",
                                        "rating": 0, "comment": "typo"}).json()
    assert fb["queued_for_review"]


def test_trace_id_header_and_body(client, student_id):
    r = client.post("/session/start", json={"student_id": student_id}, headers={"x-trace-id": "tr_custom123"})
    assert r.headers["x-trace-id"] == "tr_custom123"
    assert r.json()["trace_id"] == "tr_custom123"


def test_replay_rebuilds_live_state(client, graph, db):
    """Event sourcing: folding the attempt log reproduces the live learner state (simulated student, no b updates)."""
    sid = "sim_replay_01"
    db.add(m.Student(id=sid, display_name="Replay", is_simulated=True, planted_misconceptions=[]))
    db.commit()
    _start(client, sid)
    script = [("q_bst_ops_02", "recursion_base.m1"), ("q_recursion_base_02", "recursion_base.m1"),
              ("q_recursion_base_03", None), ("q_recursion_base_04", None), ("q_arrays_02", None),
              ("q_arrays_03", None), ("q_queues_02", "queues.m1")]
    for qid, mis in script:
        _attempt(client, sid, qid, answer(graph, qid, misconception=mis))
    db.expire_all()
    live = load_rows(db, sid, graph)
    rebuilt = rebuild(db, sid, graph)
    for cid in graph.concepts:
        assert abs(live[cid].theta - rebuilt[cid].theta) < 1e-9, cid
        assert sorted(live[cid].active_misconception_ids or []) == sorted(rebuilt[cid].active_misconception_ids), cid


def test_llm_never_writes_state_directly(db):
    """Rule 1: no LLM-facing module imports the DB models that hold mastery/XP (only core/ does)."""
    import pathlib

    root = pathlib.Path(__file__).resolve().parent.parent / "app" / "ai"
    for f in root.glob("*.py"):
        src = f.read_text()
        assert "MasteryState" not in src and "XPEvent" not in src, f.name
    assert db.scalars(select(m.Concept)).first() is not None
