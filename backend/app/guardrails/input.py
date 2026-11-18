"""Input guardrails for student free text (§13.1).

- Length limit, PII scrub, moderation, prompt-injection detection.
- Text is wrapped in delimiters and the system prompts state it is data, never instructions.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.config import get_settings
from app.guardrails.moderation import moderate
from app.guardrails.pii import scrub

OPEN, CLOSE = "<<<STUDENT_TEXT", "STUDENT_TEXT>>>"

_INJECTION = re.compile(
    r"(ignore (all |any |the )?(previous|prior|above|earlier) (instructions|prompts?|rules)|"
    r"disregard (the |all )?(instructions|rules|system)|"
    r"you are now|act as (a|an|the) |new instructions|system prompt|developer mode|jailbreak|"
    r"mark (me|this|my answer) (as )?(correct|right)|give me (the )?(full )?(answer|xp|points)|"
    r"set (my )?(score|mastery|xp)|reveal (the )?answer)",
    re.I,
)


@dataclass
class GuardResult:
    text: str
    flags: list[str] = field(default_factory=list)
    blocked: bool = False
    injection: bool = False

    @property
    def wrapped(self) -> str:
        return wrap(self.text)


def wrap(text: str) -> str:
    safe = text.replace(OPEN, "").replace(CLOSE, "")
    return f"{OPEN}\n{safe}\n{CLOSE}"


def detect_injection(text: str) -> bool:
    return bool(_INJECTION.search(text))


DOC_OPEN, DOC_CLOSE = "<<<DOCUMENT_TEXT", "DOCUMENT_TEXT>>>"


def check_document_text(text: str, max_chars: int) -> GuardResult:
    """Uploaded teacher material: data, never instructions (rule 6). Truncate, scrub contact PII,
    flag (not block) injection-looking passages, and wrap in document delimiters."""
    flags: list[str] = []
    t = (text or "").replace(DOC_OPEN, "").replace(DOC_CLOSE, "").replace(OPEN, "").replace(CLOSE, "")
    if len(t) > max_chars:
        t = t[:max_chars]
        flags.append("document_truncated")
    t, pii_flags = scrub(t)
    flags.extend(f"document_{f}" for f in pii_flags)
    injection = detect_injection(t)
    if injection:
        flags.append("document_injection_suspect")
    return GuardResult(text=f"{DOC_OPEN}\n{t}\n{DOC_CLOSE}", flags=flags, injection=injection)


def check_free_text(text: str, max_chars: int | None = None, extra_names: list[str] | None = None) -> GuardResult:
    s = get_settings()
    limit = max_chars or s.max_free_text_chars
    flags: list[str] = []
    t = (text or "").strip()
    if len(t) > limit:
        t = t[:limit]
        flags.append("truncated")
    t, pii_flags = scrub(t, extra_names)
    flags.extend(pii_flags)
    injection = detect_injection(t)
    if injection:
        flags.append("injection_attempt")
    flagged, mod_flags = moderate(t)
    flags.extend(mod_flags)
    return GuardResult(text=t, flags=flags, blocked=flagged, injection=injection)
