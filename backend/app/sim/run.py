"""Run synthetic students through the REAL API (same event path as real students).

    uv run python -m app.sim.run --students 30 [--attempts 40] [--no-remediation] [--reset]
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass

from sqlalchemy import delete, select

from app.config import get_settings
from app.core.graph import get_graph
from app.core.learner_model import mastery
from app.core.quality import detection_stats
from app.db import models as m
from app.db.session import SessionLocal
from app.sim.students import SimStudent, make_students


@dataclass
class SimStats:
    students: int
    attempts: int
    lessons: int
    bosses: int
    bosses_won: int
    diagnoses: int
    duration_s: float
    detection: dict
    avg_mastery_planted_start: float | None
    avg_mastery_planted_end: float | None
    unlearned: int
    planted: int

    def as_dict(self) -> dict:
        return self.__dict__.copy()


def reset_sim_data(prefix: str = "sim") -> None:
    with SessionLocal() as db:
        ids = [s.id for s in db.scalars(select(m.Student).where(m.Student.is_simulated.is_(True)))
               if s.id.startswith(prefix)]
        if ids:
            for model in (m.Attempt, m.MasteryState, m.Diagnosis, m.ScheduledItem, m.XPEvent, m.StudentBadge,
                          m.BossBattle, m.TeachSession, m.Session):
                db.execute(delete(model).where(model.student_id.in_(ids)))
            db.execute(delete(m.Student).where(m.Student.id.in_(ids)))
            db.commit()


def _register(students: list[SimStudent]) -> None:
    with SessionLocal() as db:
        for s in students:
            if db.get(m.Student, s.id) is None:
                db.add(m.Student(id=s.id, display_name=s.display_name, is_simulated=True,
                                 planted_misconceptions=s.planted))
        db.commit()


def _planted_mastery(student_ids: list[str], planted: dict[str, list[str]]) -> float | None:
    vals = []
    with SessionLocal() as db:
        for sid in student_ids:
            rows = {r.concept_id: r for r in db.scalars(select(m.MasteryState).where(m.MasteryState.student_id == sid))}
            for mid in planted[sid]:
                r = rows.get(mid.split(".")[0])
                vals.append(mastery(r.theta) if r else 0.5)
    return round(sum(vals) / len(vals), 4) if vals else None


def run_simulation(
    client,
    n_students: int = 30,
    attempts_per_student: int = 40,
    seed: int = 7,
    remediation: bool = True,
    prefix: str = "sim",
    boss_prob: float = 0.6,
    levels_per_student: int = 3,
) -> SimStats:
    """`client` is anything with .get/.post like fastapi.testclient.TestClient (or httpx.Client)."""
    settings = get_settings()
    old_delay = settings.lesson_stream_delay_ms
    settings.lesson_stream_delay_ms = 0
    t0 = time.perf_counter()
    with SessionLocal() as db:
        graph = get_graph(db)
    students = make_students(n_students, graph, seed=seed, prefix=prefix)
    _register(students)
    attempts = lessons = bosses = won = 0
    start_mastery_samples: dict[str, float] = {}
    try:
        for st in students:
            r = client.post("/session/start", json={"student_id": st.id})
            r.raise_for_status()
            body = r.json()
            session_id = body["session_id"]
            nxt = body["next"]
            for i in range(attempts_per_student):
                q = nxt.get("question")
                if not q:
                    break
                opt, conf = st.answer(q, graph)
                res = client.post("/attempts", json={
                    "student_id": st.id, "question_id": q["id"], "option_id": opt, "confidence": conf,
                    "time_ms": int(st.rng.uniform(4000, 30000)), "hints_used": 0, "session_id": session_id,
                })
                res.raise_for_status()
                a = res.json()
                attempts += 1
                if i == 4:  # after the diagnostic
                    start_mastery_samples[st.id] = 1.0
                dx = a["diagnosis"]
                if dx.get("id") and dx.get("status") == "pending":
                    for _ in range(50):  # poll (background agent)
                        d = client.get(f"/diagnoses/{dx['id']}").json()
                        if d["status"] != "pending":
                            break
                        time.sleep(0.1)
                na = a["next_action"]
                if remediation and na["kind"] == "lesson" and na.get("concept_id") and st.rng.random() < st.engagement:
                    params = {"student_id": st.id}
                    if na.get("misconception_id"):
                        params["misconception_id"] = na["misconception_id"]
                    client.get(f"/lesson/{na['concept_id']}", params=params)
                    lessons += 1
                    st.study(na["concept_id"], na.get("misconception_id"), graph)
                if remediation and na["kind"] == "boss" and st.rng.random() < boss_prob * st.engagement:
                    b = client.get(f"/boss/{st.id}")
                    if b.status_code == 200:
                        bosses += 1
                        battle = b.json()
                        for bq in battle["questions"][battle["current_index"]:]:
                            o, c = st.answer(bq, graph)
                            br = client.post(f"/boss/{battle['id']}/attempt",
                                             json={"question_id": bq["id"], "option_id": o, "confidence": c})
                            if br.status_code != 200:
                                break
                            attempts += 1
                            if br.json()["status"] != "active":
                                won += br.json()["status"] == "won"
                                break
                nxt = client.get("/next-question", params={"student_id": st.id}).json()
            # Adventure mode: the student picks levels themselves (the map's recommendation, like most players).
            for _ in range(levels_per_student):
                world = client.get(f"/students/{st.id}/world").json()
                cid = world.get("recommended_concept_id")
                if not cid:
                    break
                r = client.post(f"/levels/{cid}/start", json={"student_id": st.id, "restart": True})
                if r.status_code != 200:
                    break
                run = r.json()["run"]
                while run["status"] == "active" and run["question"]:
                    if run["fifty_left"] and st.rng.random() < 0.15:
                        run = client.post(f"/levels/runs/{run['id']}/fifty").json()["run"]
                    opt, conf = st.answer(run["question"], graph)
                    if opt in run.get("removed_option_ids", []):
                        opt = next(o["id"] for o in run["question"]["options"] if o["id"] not in run["removed_option_ids"])
                    ar = client.post(f"/levels/runs/{run['id']}/answer",
                                     json={"option_id": opt, "confidence": conf, "session_id": session_id})
                    if ar.status_code != 200:
                        break
                    attempts += 1
                    run = ar.json()["run"]
    finally:
        settings.lesson_stream_delay_ms = old_delay
        from app.observability.writer import flush

        flush()

    with SessionLocal() as db:
        det = detection_stats(db)
        n_dx = db.scalar(select(m.Diagnosis.id).where(m.Diagnosis.student_id.in_([s.id for s in students])).limit(1))
        dx_count = len(db.scalars(select(m.Diagnosis.id).where(m.Diagnosis.student_id.in_([s.id for s in students]))).all()) if n_dx else 0
    planted = {s.id: s.planted for s in students}
    return SimStats(
        students=len(students), attempts=attempts, lessons=lessons, bosses=bosses, bosses_won=won,
        diagnoses=dx_count, duration_s=round(time.perf_counter() - t0, 2), detection=det,
        avg_mastery_planted_start=None, avg_mastery_planted_end=_planted_mastery([s.id for s in students], planted),
        unlearned=sum(len(s.unlearned) for s in students), planted=sum(len(s.planted) for s in students),
    )


def main() -> None:
    ap = argparse.ArgumentParser(description="Run simulated students through the API")
    ap.add_argument("--students", type=int, default=30)
    ap.add_argument("--attempts", type=int, default=40)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--no-remediation", action="store_true")
    ap.add_argument("--reset", action="store_true", help="delete previous simulated students first")
    args = ap.parse_args()

    from fastapi.testclient import TestClient

    from app.main import app

    if args.reset:
        reset_sim_data()
    with TestClient(app) as client:
        stats = run_simulation(client, args.students, args.attempts, args.seed, not args.no_remediation)
    print(json.dumps(stats.as_dict(), indent=2))


if __name__ == "__main__":
    main()
