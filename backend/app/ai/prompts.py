"""Prompt registry: loads versioned prompt files from backend/prompts/*.md (rule 4).

File format:
    ---
    name: lesson
    version: 1.0.0
    max_tokens: 900
    ---
    ## system
    ...
    ## user
    ... {{key}} placeholders (strings inserted as-is, other values as JSON) ...
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from app.config import PROMPTS_DIR

_FRONT = re.compile(r"^---\n(.*?)\n---\n", re.S)
_SECTION = re.compile(r"^## (system|user)\s*$", re.M)
_PLACEHOLDER = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")


@dataclass(frozen=True)
class Prompt:
    name: str
    version: str
    max_tokens: int
    system: str
    user: str

    def render(self, inputs: dict[str, Any]) -> tuple[str, str]:
        def sub(m: re.Match[str]) -> str:
            key = m.group(1)
            if key == "inputs":
                return json.dumps(inputs, indent=2, ensure_ascii=False, default=str)
            v = inputs.get(key, "")
            return v if isinstance(v, str) else json.dumps(v, indent=2, ensure_ascii=False, default=str)

        return _PLACEHOLDER.sub(sub, self.system), _PLACEHOLDER.sub(sub, self.user)


class PromptError(ValueError):
    pass


def parse_prompt(text: str, fallback_name: str) -> Prompt:
    fm = _FRONT.match(text)
    if not fm:
        raise PromptError(f"{fallback_name}: missing front matter with version")
    meta: dict[str, str] = {}
    for line in fm.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    if "version" not in meta:
        raise PromptError(f"{fallback_name}: front matter must include `version:`")
    body = text[fm.end() :]
    parts = _SECTION.split(body)
    sections: dict[str, str] = {}
    for i in range(1, len(parts) - 1, 2):
        sections[parts[i]] = parts[i + 1].strip()
    if "system" not in sections or "user" not in sections:
        raise PromptError(f"{fallback_name}: needs '## system' and '## user' sections")
    return Prompt(
        name=meta.get("name", fallback_name),
        version=meta["version"],
        max_tokens=int(meta.get("max_tokens", "800")),
        system=sections["system"],
        user=sections["user"],
    )


@lru_cache(maxsize=64)
def load(name: str) -> Prompt:
    path = PROMPTS_DIR / f"{name}.md"
    if not path.exists():
        raise PromptError(f"prompt file not found: {path}")
    return parse_prompt(path.read_text(encoding="utf-8"), name)


def all_prompts() -> list[Prompt]:
    return [load(p.stem) for p in sorted(PROMPTS_DIR.glob("*.md"))]
