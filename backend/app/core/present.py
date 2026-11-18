"""Presentation helpers shared by API routes and core game logic."""

from __future__ import annotations

import hashlib

from app.core.graph import ContentGraph, QuestionInfo
from app.schemas.content import OptionPublic, QuestionPublic


def _display_order(qid: str, oid: str) -> str:
    return hashlib.sha1(f"{qid}:{oid}".encode()).hexdigest()


def question_public(q: QuestionInfo, graph: ContentGraph) -> QuestionPublic:
    # Authors tend to list the correct option first; show options in a stable pseudo-random order
    # (deterministic per question, so a question always looks the same and option ids never change).
    opts = sorted(q.options, key=lambda o: _display_order(q.id, o.id))
    return QuestionPublic(
        id=q.id,
        concept_id=q.concept_id,
        concept_name=graph.name(q.concept_id),
        bloom_level=q.bloom_level,  # type: ignore[arg-type]
        type=q.type,  # type: ignore[arg-type]
        stem=q.stem,
        options=[OptionPublic(id=o.id, text=o.text) for o in opts],
        has_hints=True,
    )
