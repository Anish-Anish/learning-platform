"""Output guardrails (§13.2): grounding, answer leakage, tone."""

from __future__ import annotations

import re

_WORD = re.compile(r"[a-z][a-z0-9_]+")
STOP = set(
    """a an the and or but if then else of to in on at by for with from into onto is are was were be been being
    it its this that these those as so than too very can could should would will just not no yes you your we our
    they their them he she his her i me my do does did done have has had having what which who whom when where why
    how all any each every some such only own same other more most also there here up down out over under again
    let lets one two get gets got make makes made like use used using""".split()
)

_SHAMING = [
    (re.compile(r"\byou failed\b", re.I), "this didn't land yet"),
    (re.compile(r"\b(stupid|dumb|idiot(ic)?|lazy)\b", re.I), "tricky"),
    (re.compile(r"\bwrong again\b", re.I), "not quite yet"),
    (re.compile(r"\bobviously\b", re.I), "notice that"),
    (re.compile(r"\bthat's (just )?wrong\b", re.I), "here's the gap"),
]


def content_words(text: str) -> set[str]:
    return {w for w in _WORD.findall(text.lower()) if w not in STOP and len(w) > 2}


def grounding_ratio(text: str, source: str) -> float:
    """Share of the text's content words that appear in the source notes (prefix-tolerant)."""
    words = content_words(text)
    if not words:
        return 1.0
    src = content_words(source)
    stems = {w[:5] for w in src}
    hit = sum(1 for w in words if w in src or w[:5] in stems)
    return hit / len(words)


def is_grounded(text: str, source: str, threshold: float = 0.45) -> bool:
    return grounding_ratio(text, source) >= threshold


def leaks_answer(text: str, answers: list[str]) -> bool:
    """True if any (non-trivial) correct-answer text appears verbatim in `text`."""
    low = text.lower()
    for a in answers:
        a_norm = a.strip().lower().strip("`.")
        if len(a_norm) >= 12 and a_norm in low:
            return True
    return False


def fix_tone(text: str) -> tuple[str, bool]:
    changed = False
    for pat, repl in _SHAMING:
        if pat.search(text):
            text = pat.sub(repl, text)
            changed = True
    return text, changed
