"""Output guardrails for studio-generated learning content (§19.3): grounding, injected instructions, tone.

Pure functions. The pipeline uses them to retry/drop items; moderation flags become teacher review warnings
(the teacher is the human in the loop, and course material can legitimately touch sensitive topics).
"""

from __future__ import annotations

from collections.abc import Callable

from app.guardrails.input import detect_injection
from app.guardrails.output import fix_tone, grounding_ratio

NOTES_MIN_GROUNDING = 0.4
CARD_MIN_GROUNDING = 0.3


def screen_text(text: str) -> tuple[str, list[str], bool]:
    """Return (tone-fixed text, flags, drop). Drop if the output carries instruction-like text."""
    flags: list[str] = []
    if detect_injection(text):
        return text, ["output_injection"], True
    fixed, changed = fix_tone(text)
    if changed:
        flags.append("tone_fixed")
    return fixed, flags, False


def notes_validator(excerpts: str) -> Callable[[object], list[str]]:
    """llm_client validator: notes must be grounded in the source excerpts and free of injected instructions."""

    def check(out: object) -> list[str]:
        notes = getattr(out, "notes_md", "") or ""
        issues: list[str] = []
        if excerpts.strip() and grounding_ratio(notes, excerpts) < NOTES_MIN_GROUNDING:
            issues.append("grounding_failure")
        if detect_injection(notes):
            issues.append("output_injection")
        return issues

    return check


def card_ok(front: str, back: str, notes: str) -> tuple[bool, str | None]:
    text = f"{front} {back}"
    if detect_injection(text):
        return False, "output_injection"
    if notes.strip() and grounding_ratio(text, notes) < CARD_MIN_GROUNDING:
        return False, "grounding_failure"
    return True, None


def question_ok(q: dict) -> bool:
    text = " ".join([q.get("stem", ""), q.get("explanation", ""), *[o.get("text", "") for o in q.get("options", [])]])
    return not detect_injection(text)
