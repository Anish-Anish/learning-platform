"""Question verifier (PROJECT_CONTEXT §10.3).

1. Deterministic checks — always run (seed loader, pipeline, evals).
2. LLM check (`prompts/verifier.md`) — answerable from notes? single correct answer? Bloom matches?
"""

from __future__ import annotations

from typing import Any

from app.schemas.ai import VerifierReport
from app.schemas.common import BLOOM_ORDER

MIN_STEM, MAX_STEM = 10, 900
MAX_OPTION = 240


def deterministic_check(question: dict[str, Any], known_misconceptions: set[str]) -> list[str]:
    """Return a list of issues (empty = pass). `question` is a SeedQuestion-shaped dict."""
    issues: list[str] = []
    stem = (question.get("stem") or "").strip()
    if not (MIN_STEM <= len(stem) <= MAX_STEM):
        issues.append(f"stem length {len(stem)} outside {MIN_STEM}-{MAX_STEM}")
    if question.get("bloom_level") not in BLOOM_ORDER:
        issues.append(f"invalid bloom level {question.get('bloom_level')!r}")
    if not (question.get("explanation") or "").strip():
        issues.append("missing explanation")

    options = question.get("options") or []
    if question.get("type", "mcq") == "mcq":
        if not 2 <= len(options) <= 5:
            issues.append(f"mcq needs 2-5 options, has {len(options)}")
        texts = [(o.get("text") or "").strip().lower() for o in options]
        if len(set(texts)) != len(texts):
            issues.append("duplicate option text")
        ids = [o.get("id") for o in options]
        if len(set(ids)) != len(ids):
            issues.append("duplicate option id")
        n_correct = sum(1 for o in options if o.get("is_correct"))
        if n_correct != 1:
            issues.append(f"exactly one correct option required, found {n_correct}")
        for o in options:
            if len((o.get("text") or "").strip()) == 0:
                issues.append(f"option {o.get('id')} is empty")
            if len(o.get("text") or "") > MAX_OPTION:
                issues.append(f"option {o.get('id')} longer than {MAX_OPTION} chars")
            if not o.get("is_correct"):
                mid = o.get("misconception_id")
                if not mid:
                    issues.append(f"wrong option {o.get('id')} has no misconception_id")
                elif mid not in known_misconceptions:
                    issues.append(f"wrong option {o.get('id')} references unknown misconception {mid}")
            elif o.get("misconception_id"):
                issues.append(f"correct option {o.get('id')} must not carry a misconception")
    return issues


def llm_check(question: dict[str, Any], notes_md: str, trace_id: str) -> VerifierReport | None:
    """LLM verification. Returns None when the LLM is unavailable (offline mode)."""
    from app.ai.llm_client import call

    def _fallback() -> VerifierReport | None:
        return None

    result = call(
        feature="verifier",
        prompt_name="verifier",
        inputs={
            "notes": notes_md,
            "question": {
                "stem": question["stem"],
                "bloom_level": question["bloom_level"],
                "options": [{"text": o["text"], "is_correct": o["is_correct"]} for o in question["options"]],
            },
        },
        output_schema=VerifierReport,
        model_tier="fast",
        trace_id=trace_id,
        fallback=_fallback,
    )
    return result.output if isinstance(result.output, VerifierReport) else None


def verify(
    question: dict[str, Any], known_misconceptions: set[str], notes_md: str, trace_id: str, use_llm: bool = True
) -> dict[str, Any]:
    issues = deterministic_check(question, known_misconceptions)
    report: dict[str, Any] = {
        "deterministic_ok": not issues,
        "llm_checked": False,
        "issues": list(issues),
        "bloom_detected": None,
    }
    if not issues and use_llm:
        llm = llm_check(question, notes_md, trace_id)
        if llm is not None:
            report["llm_checked"] = True
            report["issues"].extend(llm.issues)
            report["bloom_detected"] = llm.bloom_detected
            if not llm.passed:
                report["issues"].append("llm verifier failed")
    report["pass"] = not report["issues"]
    return report
