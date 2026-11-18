"""Moderation (§13.1): OpenAI moderation endpoint when available, small local list otherwise."""

from __future__ import annotations

import re

from app.config import get_settings

# Offline safety net only — deliberately small and generic.
_LOCAL = re.compile(
    r"\b(kill (myself|yourself|him|her|them)|suicide|self[- ]harm|bomb (making|recipe)|"
    r"how to (make|build) (a )?(bomb|weapon)|n[i1]gg|f[a@]gg)\w*",
    re.I,
)


def moderate(text: str) -> tuple[bool, list[str]]:
    """Return (flagged, flags)."""
    s = get_settings()
    if s.llm_enabled:
        try:
            from app.ai.llm_client import get_client

            client = get_client()
            if client is not None:
                res = client.moderations.create(model=s.openai_moderation_model, input=text)
                r = res.results[0]
                if r.flagged:
                    cats = [k for k, v in r.categories.model_dump().items() if v]
                    return True, ["moderation_flagged", *[f"mod_{c}" for c in cats[:3]]]
                return False, []
        except Exception:
            pass  # fall through to local check
    if _LOCAL.search(text):
        return True, ["moderation_flagged", "mod_local"]
    return False, []
