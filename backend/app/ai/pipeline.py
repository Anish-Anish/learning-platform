"""Content pipeline (PROJECT_CONTEXT §10.2). Pure functions reused by 5A (teacher studio).

    uv run python -m app.ai.pipeline --concept bst_property --bloom apply --n 3

writes candidates to backend/seed/generated/<concept>.json for human review (never straight into the bank).
"""

from __future__ import annotations

import argparse
import json
import re
from typing import Any

from app.ai.llm_client import call
from app.ai.verifier import verify
from app.config import SEED_DIR
from app.observability.tracing import new_trace_id
from app.schemas.ai import GeneratedQuestionSet
from app.schemas.content import SeedConcept, SeedMisconception


def extract_concepts(text: str) -> list[dict[str, str]]:
    """5A hook: split uploaded Markdown notes into candidate concepts by headings (deterministic)."""
    out: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for line in text.splitlines():
        m = re.match(r"^#{1,3}\s+(.*)", line)
        if m:
            if current:
                out.append(current)
            name = m.group(1).strip()
            current = {"id": re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_"), "name": name, "notes": ""}
        elif current is not None:
            current["notes"] += line + "\n"
    if current:
        out.append(current)
    return [c for c in out if c["notes"].strip()]


def generate_questions(
    concept: SeedConcept,
    notes: str,
    misconceptions: list[SeedMisconception],
    bloom_level: str,
    difficulty: float,
    n: int,
    trace_id: str | None = None,
    id_prefix: str = "q_gen",
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Generate n questions; verify; regenerate failures once; drop the rest.

    Returns (accepted questions as SeedQuestion dicts with status 'draft', stats).
    """
    trace_id = trace_id or new_trace_id()
    known = {m.id for m in misconceptions}
    inputs = {
        "concept": {"id": concept.id, "name": concept.name, "key_points": concept.key_points},
        "notes": notes,
        "misconceptions": [{"id": m.id, "description": m.description} for m in misconceptions],
        "bloom_level": bloom_level,
        "difficulty": difficulty,
        "n": n,
    }
    accepted: list[dict[str, Any]] = []
    stats = {"generated": 0, "passed": 0, "regenerated": 0, "dropped": 0}

    def gen(extra: dict[str, Any]) -> list[dict[str, Any]]:
        res = call(feature="question_gen", prompt_name="question_gen", inputs={**inputs, **extra},
                   output_schema=GeneratedQuestionSet, model_tier="smart", trace_id=trace_id,
                   fallback=lambda: GeneratedQuestionSet(questions=[]), use_cache=False)
        out = []
        for i, q in enumerate(res.output.questions):
            d = q.model_dump()
            d["options"] = [{**o, "id": "abcde"[j]} for j, o in enumerate(d["options"])]
            d.update(concept_id=concept.id, type="mcq", status="draft", source="generated")
            d["id"] = f"{id_prefix}_{concept.id}_{len(accepted) + i + 1:02d}"
            out.append(d)
        return out

    for q in gen({}):
        stats["generated"] += 1
        report = verify(q, known, notes, trace_id)
        if report["pass"]:
            q["verifier_report"] = report
            accepted.append(q)
            stats["passed"] += 1
            continue
        stats["regenerated"] += 1
        retry = gen({"n": 1, "fix_these_issues": report["issues"], "previous_attempt": q["stem"]})
        if retry:
            r = retry[0]
            r2 = verify(r, known, notes, trace_id)
            if r2["pass"]:
                r["verifier_report"] = r2
                accepted.append(r)
                continue
        stats["dropped"] += 1
    stats["pass_rate"] = round(stats["passed"] / stats["generated"], 3) if stats["generated"] else None
    return accepted, stats


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate candidate questions for human review")
    ap.add_argument("--concept", required=True)
    ap.add_argument("--bloom", default="apply", choices=["remember", "understand", "apply", "analyze"])
    ap.add_argument("--difficulty", type=float, default=0.3)
    ap.add_argument("--n", type=int, default=3)
    args = ap.parse_args()

    from app.db.session import create_all

    create_all()
    concepts = {c["id"]: SeedConcept.model_validate(c) for c in json.loads((SEED_DIR / "concepts.json").read_text())}
    mis = [SeedMisconception.model_validate(m) for m in json.loads((SEED_DIR / "misconceptions.json").read_text())]
    c = concepts[args.concept]
    related = [m for m in mis if m.concept_id == c.id or m.concept_id in c.prerequisites]
    notes = (SEED_DIR / "notes" / f"{c.id}.md").read_text()
    qs, stats = generate_questions(c, notes, related, args.bloom, args.difficulty, args.n)
    out_dir = SEED_DIR / "generated"
    out_dir.mkdir(exist_ok=True)
    path = out_dir / f"{c.id}.json"
    path.write_text(json.dumps(qs, indent=2))
    print(json.dumps(stats))
    print(f"Wrote {len(qs)} candidates to {path} — review before merging into questions.json.")


if __name__ == "__main__":
    main()
