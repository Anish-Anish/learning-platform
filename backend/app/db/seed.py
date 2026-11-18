"""Seed loader: `uv run python -m app.db.seed [--reset]`.

Loads backend/seed/*.json + notes/*.md, validates (Pydantic + DAG + deterministic verifier) and
upserts into the DB. 5B auto-approves content (`status=approved`); 5A will route through review.
"""

from __future__ import annotations

import argparse
import json

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.ai.verifier import deterministic_check
from app.config import SEED_DIR
from app.core import graph as graph_mod
from app.db import models as m
from app.db.session import SessionLocal, create_all, get_engine
from app.observability.logging import get_logger
from app.schemas.content import SeedConcept, SeedMisconception, SeedQuestion

log = get_logger(__name__)


class SeedError(ValueError):
    pass


def load_seed_files() -> tuple[list[SeedConcept], list[SeedMisconception], list[SeedQuestion], dict[str, str]]:
    concepts = [SeedConcept.model_validate(c) for c in json.loads((SEED_DIR / "concepts.json").read_text())]
    mis = [SeedMisconception.model_validate(x) for x in json.loads((SEED_DIR / "misconceptions.json").read_text())]
    questions = [SeedQuestion.model_validate(q) for q in json.loads((SEED_DIR / "questions.json").read_text())]
    notes = {}
    for c in concepts:
        p = SEED_DIR / "notes" / f"{c.id}.md"
        notes[c.id] = p.read_text() if p.exists() else ""
    return concepts, mis, questions, notes


def validate(
    concepts: list[SeedConcept], mis: list[SeedMisconception], questions: list[SeedQuestion], notes: dict[str, str]
) -> dict[str, list[str]]:
    ids = {c.id for c in concepts}
    if len(ids) != len(concepts):
        raise SeedError("duplicate concept ids")
    for c in concepts:
        for p in c.prerequisites:
            if p not in ids:
                raise SeedError(f"{c.id}: unknown prerequisite {p}")
        if not notes.get(c.id):
            raise SeedError(f"{c.id}: missing notes/{c.id}.md")
    cycle = graph_mod.find_cycle({c.id: c.prerequisites for c in concepts})
    if cycle:
        raise SeedError(f"prerequisite graph has a cycle: {' -> '.join(cycle)}")
    mis_ids = {x.id for x in mis}
    for x in mis:
        if x.concept_id not in ids:
            raise SeedError(f"{x.id}: unknown concept {x.concept_id}")
    qids = set()
    issues: dict[str, list[str]] = {}
    for q in questions:
        if q.id in qids:
            raise SeedError(f"duplicate question id {q.id}")
        qids.add(q.id)
        if q.concept_id not in ids:
            raise SeedError(f"{q.id}: unknown concept {q.concept_id}")
        found = deterministic_check(q.model_dump(), mis_ids)
        if found:
            issues[q.id] = found
    return issues


def seed(db: Session, reset: bool = False) -> dict[str, int]:
    concepts, mis, questions, notes = load_seed_files()
    issues = validate(concepts, mis, questions, notes)
    if issues:
        raise SeedError(f"verifier rejected seed questions: {issues}")

    if reset:
        for model in (m.Option, m.Question, m.Misconception, m.Prerequisite, m.Concept):
            db.execute(delete(model))
        db.flush()

    for c in concepts:
        row = db.get(m.Concept, c.id) or m.Concept(id=c.id)
        row.name, row.description = c.name, c.description
        row.notes_md = notes[c.id]
        row.key_points, row.bloom_levels = c.key_points, list(c.bloom_levels)
        row.status = "approved"
        db.merge(row)
    db.flush()
    db.execute(delete(m.Prerequisite))
    for c in concepts:
        for p in c.prerequisites:
            db.add(m.Prerequisite(concept_id=c.id, prerequisite_id=p))
    for x in mis:
        db.merge(
            m.Misconception(
                id=x.id,
                concept_id=x.concept_id,
                description=x.description,
                correct_belief=x.correct_belief,
                analogy=x.analogy,
                socratic=x.socratic,
                replay_id=x.replay_id,
            )
        )
    db.flush()
    for q in questions:
        existing = db.get(m.Question, q.id)
        if existing is not None:
            db.execute(delete(m.Option).where(m.Option.question_id == q.id))
            db.delete(existing)
            db.flush()
        row = m.Question(
            id=q.id,
            concept_id=q.concept_id,
            bloom_level=q.bloom_level,
            type=q.type,
            stem=q.stem,
            explanation=q.explanation,
            difficulty_b=q.difficulty_b,
            hints=q.hints,
            content_version=q.content_version,
            status="approved",
            source=q.source,
            verifier_report={"deterministic_ok": True, "llm_checked": False, "issues": [], "pass": True},
        )
        row.options = [
            m.Option(
                id=o.id,
                position=i,
                text=o.text,
                is_correct=o.is_correct,
                misconception_id=o.misconception_id,
            )
            for i, o in enumerate(q.options)
        ]
        db.add(row)
    db.commit()
    graph_mod.invalidate()
    counts = {"concepts": len(concepts), "misconceptions": len(mis), "questions": len(questions)}
    log.info("seed_loaded", **counts)
    return counts


def ensure_seeded(db: Session) -> bool:
    """Seed on first start. Returns True if seeding happened."""
    if db.scalars(select(m.Concept).limit(1)).first() is None:
        seed(db)
        return True
    return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Load Rootwise seed content")
    parser.add_argument("--reset", action="store_true", help="delete content tables before loading")
    args = parser.parse_args()
    create_all()
    get_engine()
    with SessionLocal() as db:
        counts = seed(db, reset=args.reset)
    print(f"Seeded {counts['concepts']} concepts, {counts['misconceptions']} misconceptions, "
          f"{counts['questions']} questions.")


if __name__ == "__main__":
    main()
