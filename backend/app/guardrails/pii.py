"""PII scrubbing (§13.1). Students may be minors: keep personal data out of prompts and logs."""

from __future__ import annotations

import re

EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE = re.compile(r"(?<!\w)(?:\+?\d[\d\s().-]{7,}\d)(?!\w)")
URL_WITH_PARAMS = re.compile(r"https?://\S+\?\S+")


def scrub(text: str, extra_names: list[str] | None = None) -> tuple[str, list[str]]:
    """Return (scrubbed_text, flags)."""
    flags: list[str] = []
    out = text
    if EMAIL.search(out):
        out = EMAIL.sub("[email]", out)
        flags.append("pii_email")
    if PHONE.search(out):
        out = PHONE.sub("[phone]", out)
        flags.append("pii_phone")
    if URL_WITH_PARAMS.search(out):
        out = URL_WITH_PARAMS.sub("[link]", out)
        flags.append("pii_url")
    for name in extra_names or []:
        if name and len(name) > 2 and re.search(rf"\b{re.escape(name)}\b", out, re.I):
            out = re.sub(rf"\b{re.escape(name)}\b", "[name]", out, flags=re.I)
            flags.append("pii_name")
    return out, flags
