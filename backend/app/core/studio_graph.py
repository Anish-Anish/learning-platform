"""Deterministic rules for studio-generated subjects (rule 1: the LLM proposes, this code decides).

Pure functions: id normalisation, proposal -> valid DAG, unit (world) assignment, diagnostic picks,
and prerequisite rewiring when a teacher deletes a concept.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.core.graph import find_cycle, topo_sort

WORLD_COLORS = ["emerald", "violet", "sky", "cyan", "lime", "amber", "fuchsia", "rose"]
MAX_KEY = 40


def slugify(text: str, max_len: int = MAX_KEY) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", (text or "").lower()).strip("_")
    return (s[:max_len].rstrip("_")) or "concept"


def subject_id_for(name: str, suffix: str) -> str:
    return f"{slugify(name, 28)}_{suffix}"


def concept_id(subject_id: str, key: str) -> str:
    return f"{subject_id}__{key}"


@dataclass
class GraphConcept:
    key: str
    name: str
    description: str
    prerequisites: list[str] = field(default_factory=list)
    source_chunks: list[int] = field(default_factory=list)


def normalize_graph(
    proposed: list[dict], n_chunks: int, max_concepts: int
) -> tuple[list[GraphConcept], list[str]]:
    """Validate an LLM concept-graph proposal. Returns (concepts in topo order, warnings).

    - keys slugified and made unique; empty names dropped; capped at max_concepts
    - prerequisites resolved by key or by name; unknown / self edges dropped
    - cycles broken by removing the edge that closes each cycle (reported as a warning)
    - chunk indices clipped to the real range
    """
    warnings: list[str] = []
    concepts: list[GraphConcept] = []
    used: set[str] = set()
    alias: dict[str, str] = {}
    raw_prereqs: dict[str, list[str]] = {}
    for p in proposed:
        name = (p.get("name") or "").strip()
        if not name:
            continue
        if len(concepts) >= max_concepts:
            warnings.append(f"kept the first {max_concepts} concepts; dropped '{name}' and later ones")
            break
        key = base = slugify(p.get("key") or name)
        n = 2
        while key in used:
            key = f"{base[: MAX_KEY - 3]}_{n}"
            n += 1
        used.add(key)
        for a in {slugify(p.get("key") or ""), slugify(name), name.lower()}:
            if a:
                alias.setdefault(a, key)
        chunks = sorted({int(c) for c in p.get("source_chunks") or [] if isinstance(c, int) and 0 <= c < n_chunks})
        concepts.append(GraphConcept(key, name[:120], (p.get("description") or "").strip()[:500], [], chunks))
        raw_prereqs[key] = list(p.get("prerequisites") or [])

    for c in concepts:
        out: list[str] = []
        for ref in raw_prereqs[c.key]:
            k = alias.get(slugify(str(ref))) or alias.get(str(ref).lower())
            if k and k != c.key and k not in out:
                out.append(k)
        c.prerequisites = out

    prereqs = {c.key: c.prerequisites for c in concepts}
    position = {c.key: i for i, c in enumerate(concepts)}
    while True:
        cycle = find_cycle(prereqs)
        if not cycle:
            break
        # Material usually teaches prerequisites first: drop the edge whose prerequisite comes latest
        # relative to the concept that needs it.
        edges = list(zip(cycle, cycle[1:], strict=False))
        a, b = max(edges, key=lambda e: (position[e[1]] - position[e[0]], e))
        prereqs[a] = [p for p in prereqs[a] if p != b]
        warnings.append(f"removed prerequisite {b} from {a} to break a cycle")
    by_key = {c.key: c for c in concepts}
    for k, ps in prereqs.items():
        by_key[k].prerequisites = ps
    return [by_key[k] for k in topo_sort(prereqs)], warnings


def assign_units(
    concept_keys: list[str], proposed_units: list[dict], names: dict[str, str]
) -> list[dict]:
    """Every concept in exactly one unit, in the order given; leftovers go to a final unit.
    Returns world dicts shaped like seed/worlds.json (with concept keys, not ids)."""
    valid = set(concept_keys)
    seen: set[str] = set()
    units: list[dict] = []
    for u in proposed_units:
        keys = []
        for ref in u.get("concept_keys") or []:
            k = ref if ref in valid else slugify(str(ref))
            if k in valid and k not in seen:
                keys.append(k)
                seen.add(k)
        if keys:
            units.append({"name": (u.get("name") or "").strip()[:60] or f"Unit {len(units) + 1}",
                          "tagline": (u.get("tagline") or "").strip()[:120],
                          "emoji": (u.get("emoji") or "📘").strip()[:4] or "📘", "concepts": keys})
    rest = [k for k in concept_keys if k not in seen]
    if rest:
        if not units:
            for i in range(0, len(rest), 4):
                part = rest[i : i + 4]
                units.append({"name": f"Unit {len(units) + 1}: {names.get(part[0], part[0])}", "tagline": "",
                              "emoji": "📘", "concepts": part})
        else:
            units.append({"name": "More to explore", "tagline": "Everything else from your material.", "emoji": "🧭",
                          "concepts": rest})
    for i, u in enumerate(units):
        u["id"] = f"u{i + 1}"
        u["color"] = WORLD_COLORS[i % len(WORLD_COLORS)]
        u["tagline"] = u["tagline"] or f"{len(u['concepts'])} concepts to master."
    return units


def pick_diagnostic(topo_ids: list[str], has_questions: set[str], k: int = 5) -> list[str]:
    """Spread k diagnostic concepts evenly over the learning order (only ones with questions)."""
    pool = [c for c in topo_ids if c in has_questions]
    if len(pool) <= k:
        return pool
    step = (len(pool) - 1) / (k - 1)
    picks: list[str] = []
    for i in range(k):
        c = pool[round(i * step)]
        if c not in picks:
            picks.append(c)
    return picks


def rewire_without(prereqs: dict[str, list[str]], removed: str) -> dict[str, list[str]]:
    """Delete a concept; its dependents inherit its prerequisites so unlock paths stay intact."""
    inherited = prereqs.get(removed, [])
    out: dict[str, list[str]] = {}
    for c, ps in prereqs.items():
        if c == removed:
            continue
        if removed in ps:
            merged = [p for p in ps if p != removed]
            merged += [p for p in inherited if p not in merged and p != c]
            out[c] = merged
        else:
            out[c] = list(ps)
    return out
