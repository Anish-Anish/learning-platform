"""Quality metrics shared by /admin and the eval harness (§14.2, §15.2)."""

from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models as m


def detection_stats(db: Session) -> dict[str, float | int | None]:
    """Root-gap detection vs simulator ground truth (planted misconceptions)."""
    students = db.scalars(select(m.Student).where(m.Student.is_simulated.is_(True))).all()
    if not students:
        return {"planted": 0, "exercised": 0, "detected": 0, "accuracy": None, "accuracy_exercised": None,
                "root_concept_accuracy": None}
    dx_by_student: dict[str, list[m.Diagnosis]] = defaultdict(list)
    for d in db.scalars(select(m.Diagnosis).where(m.Diagnosis.status == "applied", m.Diagnosis.needs_probe.is_(False))):
        dx_by_student[d.student_id].append(d)
    exercised_by: dict[str, set[str]] = defaultdict(set)
    for a in db.scalars(select(m.Attempt).where(m.Attempt.selected_misconception_id.is_not(None))):
        exercised_by[a.student_id].add(a.selected_misconception_id)  # type: ignore[arg-type]
    planted = exercised = detected = root_ok = 0
    for s in students:
        p = set(s.planted_misconceptions or [])
        found = {d.misconception_id for d in dx_by_student[s.id] if d.misconception_id}
        planted += len(p)
        ex = p & exercised_by[s.id]
        exercised += len(ex)
        hits = p & found
        detected += len(hits)
        for mid in hits:
            concept = mid.split(".")[0]
            if any(d.misconception_id == mid and d.root_concept_id == concept for d in dx_by_student[s.id]):
                root_ok += 1
    return {
        "planted": planted,
        "exercised": exercised,
        "detected": detected,
        "accuracy": round(detected / planted, 3) if planted else None,
        "accuracy_exercised": round(detected / exercised, 3) if exercised else None,
        "root_concept_accuracy": round(root_ok / detected, 3) if detected else None,
    }


def verifier_pass_rate(db: Session) -> dict[str, float | int | None]:
    qs = db.scalars(select(m.Question)).all()
    reports = [q.verifier_report for q in qs if q.verifier_report]
    passed = sum(1 for r in reports if r.get("pass"))
    return {"checked": len(reports), "passed": passed,
            "pass_rate": round(passed / len(reports), 3) if reports else None}
