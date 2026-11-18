"""Eval harness (PROJECT_CONTEXT §15.2): `uv run python -m app.evals.run [--students 30]`.

Runs everything on throwaway databases (never touches rootwise.db):
  1. Simulated class WITH remediation -> root-gap detection accuracy, latency, cost per session.
  2. Same students (same seed) WITHOUT remediation -> control group for mastery gain.
  3. Verifier pass rate over the question bank (deterministic + LLM when online).
  4. Teach-the-bot scorer agreement on a hand-labelled set.
Saves backend/app/evals/results/<timestamp>.json and diffs against the previous run (prompt regression).
"""

from __future__ import annotations

import argparse
import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import func, select

from app.config import EVAL_RESULTS_DIR
from app.core import graph as graph_mod
from app.db import models as m
from app.db import session as db_session
from app.evals.datasets import TEACH_LABELLED
from app.observability.metrics import percentile
from app.observability.writer import flush

HEADLINE = [
    ("detection.accuracy_exercised", "Root-gap detection (exercised)"),
    ("detection.accuracy", "Root-gap detection (all planted)"),
    ("detection.root_concept_accuracy", "Root concept accuracy"),
    ("mastery.gain_vs_control", "Mastery gain vs control (planted concepts)"),
    ("mastery.misconceptions_resolved_pct", "Planted misconceptions resolved"),
    ("verifier.pass_rate", "Verifier pass rate"),
    ("teach_scorer.agreement_within_15", "Teach scorer agreement (+/-15)"),
    ("latency.p95_ms", "API p95 latency (ms)"),
    ("cost.usd_per_session", "USD per session"),
]


def _fresh_db(tag: str) -> str:
    path = Path(tempfile.mkdtemp(prefix=f"rootwise-eval-{tag}-")) / "eval.db"
    url = f"sqlite:///{path}"
    flush()
    db_session.configure(url)
    db_session.create_all()
    graph_mod.invalidate()
    from app.db.seed import seed

    with db_session.SessionLocal() as db:
        seed(db)
    return url


def _simulate(tag: str, students: int, attempts: int, seed: int, remediation: bool) -> dict:
    from fastapi.testclient import TestClient

    from app.main import app
    from app.sim.run import run_simulation

    _fresh_db(tag)
    with TestClient(app) as client:
        stats = run_simulation(client, students, attempts, seed, remediation)
    flush()
    with db_session.SessionLocal() as db:
        lat = [x for (x,) in db.execute(select(m.RequestMetric.latency_ms)).all()]
        att_lat = [x for (x,) in db.execute(select(m.RequestMetric.latency_ms).where(m.RequestMetric.route == "/attempts")).all()]
        cost = db.scalar(select(func.coalesce(func.sum(m.LLMCall.cost_usd), 0.0))) or 0.0
        tokens = db.scalar(select(func.coalesce(func.sum(m.LLMCall.input_tokens + m.LLMCall.output_tokens), 0))) or 0
        llm_calls = db.scalar(select(func.count(m.LLMCall.id))) or 0
        fallbacks = db.scalar(select(func.count(m.LLMCall.id)).where(m.LLMCall.fallback_used.is_(True))) or 0
        sessions = db.scalar(select(func.count(m.Session.id))) or 1
        llm_lat = [x for (x,) in db.execute(select(m.LLMCall.latency_ms)).all()]
    out = stats.as_dict()
    out.update(
        latency={"p50_ms": percentile(lat, 50), "p95_ms": percentile(lat, 95),
                 "attempt_p95_ms": percentile(att_lat, 95), "llm_p95_ms": percentile(llm_lat, 95), "requests": len(lat)},
        cost={"usd_total": round(cost, 5), "usd_per_session": round(cost / sessions, 6),
              "tokens_per_session": round(tokens / sessions, 1), "llm_calls": llm_calls,
              "fallback_rate": round(fallbacks / llm_calls, 3) if llm_calls else None},
    )
    return out


def _verifier(use_llm: bool) -> dict:
    from app.ai.verifier import verify
    from app.observability.tracing import new_trace_id

    tid = new_trace_id()
    with db_session.SessionLocal() as db:
        g = graph_mod.get_graph(db)
    known = set(g.misconceptions)
    passed, issues = 0, {}
    for q in g.questions.values():
        d = {"stem": q.stem, "bloom_level": q.bloom_level, "explanation": q.explanation, "type": q.type,
             "options": [o.__dict__ for o in q.options]}
        rep = verify(d, known, g.concepts[q.concept_id].notes_md, tid, use_llm=use_llm)
        if rep["pass"]:
            passed += 1
        else:
            issues[q.id] = rep["issues"]
    n = len(g.questions)
    return {"checked": n, "passed": passed, "pass_rate": round(passed / n, 3), "llm_checked": use_llm,
            "failures": issues}


def _teach_scorer() -> dict:
    from app.ai.teach_bot import score
    from app.observability.tracing import new_trace_id

    with db_session.SessionLocal() as db:
        g = graph_mod.get_graph(db)
    rows = []
    for item in TEACH_LABELLED:
        res, source = score(g, item["concept_id"], [{"role": "student", "text": item["text"]}], new_trace_id(), "eval")
        rows.append({"concept_id": item["concept_id"], "reference": item["reference"], "predicted": res.score,
                     "source": source})
    errs = [abs(r["predicted"] - r["reference"]) for r in rows]
    return {"n": len(rows), "mae": round(sum(errs) / len(errs), 1),
            "agreement_within_15": round(sum(e <= 15 for e in errs) / len(errs), 3), "items": rows}


def _get(d: dict, dotted: str):
    for k in dotted.split("."):
        if not isinstance(d, dict):
            return None
        d = d.get(k)  # type: ignore[assignment]
    return d


def run(students: int = 30, attempts: int = 40, seed: int = 7) -> dict:
    from app.ai.llm_client import llm_mode

    treat = _simulate("treat", students, attempts, seed, remediation=True)
    verifier = _verifier(use_llm=llm_mode() == "online")
    teach = _teach_scorer()
    control = _simulate("control", students, attempts, seed, remediation=False)

    t_m, c_m = treat["avg_mastery_planted_end"], control["avg_mastery_planted_end"]
    return {
        "timestamp": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "llm_mode": llm_mode(),
        "config": {"students": students, "attempts_per_student": attempts, "seed": seed},
        "detection": treat["detection"],
        "mastery": {
            "treatment_planted_mastery": t_m,
            "control_planted_mastery": c_m,
            "gain_vs_control": round(t_m - c_m, 4) if t_m is not None and c_m is not None else None,
            "misconceptions_resolved_pct": round(treat["unlearned"] / treat["planted"], 3) if treat["planted"] else None,
            "lessons": treat["lessons"],
            "bosses_won": treat["bosses_won"],
        },
        "verifier": verifier,
        "teach_scorer": teach,
        "latency": treat["latency"],
        "cost": treat["cost"],
        "sim": {k: treat[k] for k in ("students", "attempts", "diagnoses", "duration_s")},
    }


def compare(curr: dict, prev: dict | None) -> list[str]:
    lines = []
    for key, label in HEADLINE:
        c = _get(curr, key)
        p = _get(prev, key) if prev else None
        delta = ""
        if isinstance(c, (int, float)) and isinstance(p, (int, float)):
            d = c - p
            delta = f"  ({'+' if d >= 0 else ''}{d:.3f} vs last)" if abs(d) > 1e-9 else "  (=)"
        lines.append(f"  {label:<44} {c!s:>10}{delta}")
    return lines


def main() -> None:
    ap = argparse.ArgumentParser(description="Run Rootwise evals")
    ap.add_argument("--students", type=int, default=30)
    ap.add_argument("--attempts", type=int, default=40)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()
    EVAL_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    prev_files = sorted(EVAL_RESULTS_DIR.glob("*.json"))
    prev = json.loads(prev_files[-1].read_text(encoding="utf-8")) if prev_files else None
    res = run(args.students, args.attempts, args.seed)
    path = EVAL_RESULTS_DIR / f"{res['timestamp'].replace(':', '')}.json"
    path.write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(f"\nRootwise eval ({res['llm_mode']} mode, {args.students} simulated students)")
    print("\n".join(compare(res, prev)))
    print(f"\nSaved {path}")


if __name__ == "__main__":
    main()
