"""In-memory snapshot of the content graph (concepts, prerequisites, misconceptions, questions).

Loaded once from the DB and cached; `invalidate()` after re-seeding. Pure helpers for graph walks.
"""

from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import DEFAULT_SUBJECT_ID, get_settings
from app.db import models as m
from app.schemas.common import BLOOM_ORDER


@dataclass
class OptionInfo:
    id: str
    text: str
    is_correct: bool
    misconception_id: str | None


@dataclass
class QuestionInfo:
    id: str
    concept_id: str
    bloom_level: str
    type: str
    stem: str
    explanation: str
    b: float
    options: list[OptionInfo]
    hints: list[str]
    status: str

    @property
    def correct_option(self) -> OptionInfo | None:
        return next((o for o in self.options if o.is_correct), None)

    @property
    def targets(self) -> set[str]:
        """Misconceptions this question can reveal (tagged on its wrong options)."""
        return {o.misconception_id for o in self.options if o.misconception_id}

    @property
    def bloom_index(self) -> int:
        return BLOOM_ORDER.index(self.bloom_level) if self.bloom_level in BLOOM_ORDER else 1


@dataclass
class ConceptInfo:
    id: str
    name: str
    description: str
    notes_md: str
    key_points: list[str]
    prerequisites: list[str]
    dependents: list[str] = field(default_factory=list)
    depth: int = 0


@dataclass
class MisconceptionInfo:
    id: str
    concept_id: str
    description: str
    correct_belief: str
    analogy: str
    socratic: list[str]
    replay_id: str | None


@dataclass
class ContentGraph:
    concepts: dict[str, ConceptInfo]
    misconceptions: dict[str, MisconceptionInfo]
    questions: dict[str, QuestionInfo]
    topo_order: list[str]
    questions_by_concept: dict[str, list[str]]
    questions_by_misconception: dict[str, list[str]]
    subject_id: str = DEFAULT_SUBJECT_ID
    worlds: list[dict] = field(default_factory=list)
    diagnostic_concepts: list[str] = field(default_factory=list)

    # ------------------------------------------------------------ walks
    def ancestors(self, concept_id: str) -> list[str]:
        """All transitive prerequisites, nearest first (BFS order)."""
        seen: list[str] = []
        q = deque(self.concepts[concept_id].prerequisites)
        while q:
            c = q.popleft()
            if c in seen:
                continue
            seen.append(c)
            q.extend(self.concepts[c].prerequisites)
        return seen

    def descendants(self, concept_id: str) -> list[str]:
        seen: list[str] = []
        q = deque(self.concepts[concept_id].dependents)
        while q:
            c = q.popleft()
            if c in seen:
                continue
            seen.append(c)
            q.extend(self.concepts[c].dependents)
        return seen

    def prereq_path(self, start: str, target: str) -> list[str]:
        """Shortest path start -> ... -> target following prerequisite edges. [] if unreachable."""
        if start == target:
            return [start]
        parent: dict[str, str] = {}
        q = deque([start])
        seen = {start}
        while q:
            c = q.popleft()
            for p in self.concepts[c].prerequisites:
                if p in seen:
                    continue
                parent[p] = c
                if p == target:
                    path = [p]
                    while path[-1] != start:
                        path.append(parent[path[-1]])
                    return list(reversed(path))
                seen.add(p)
                q.append(p)
        return []

    def name(self, concept_id: str | None) -> str:
        if not concept_id:
            return ""
        c = self.concepts.get(concept_id)
        return c.name if c else concept_id

    def names(self) -> dict[str, str]:
        return {cid: c.name for cid, c in self.concepts.items()}


def find_cycle(prereqs: dict[str, list[str]]) -> list[str] | None:
    """Return a cycle if the prerequisite graph is not a DAG."""
    WHITE, GREY, BLACK = 0, 1, 2
    color = {c: WHITE for c in prereqs}
    stack: list[str] = []

    def visit(c: str) -> list[str] | None:
        color[c] = GREY
        stack.append(c)
        for p in prereqs.get(c, []):
            if color.get(p, WHITE) == GREY:
                return stack[stack.index(p) :] + [p]
            if color.get(p, WHITE) == WHITE:
                found = visit(p)
                if found:
                    return found
        stack.pop()
        color[c] = BLACK
        return None

    for c in prereqs:
        if color[c] == WHITE:
            found = visit(c)
            if found:
                return found
    return None


def topo_sort(prereqs: dict[str, list[str]]) -> list[str]:
    """Prerequisites before dependents; ties broken by original order."""
    indeg = {c: len(ps) for c, ps in prereqs.items()}
    deps: dict[str, list[str]] = {c: [] for c in prereqs}
    for c, ps in prereqs.items():
        for p in ps:
            deps[p].append(c)
    order: list[str] = []
    ready = deque([c for c in prereqs if indeg[c] == 0])
    while ready:
        c = ready.popleft()
        order.append(c)
        for d in deps[c]:
            indeg[d] -= 1
            if indeg[d] == 0:
                ready.append(d)
    return order


def build_graph(db: Session, subject_id: str = DEFAULT_SUBJECT_ID) -> ContentGraph:
    q = select(m.Concept).where(m.Concept.subject_id == subject_id)
    if subject_id != DEFAULT_SUBJECT_ID:  # the seed keeps its file order
        q = q.order_by(m.Concept.position, m.Concept.id)
    concepts_rows = db.scalars(q).all()
    ids = [c.id for c in concepts_rows]
    prereq_rows = db.scalars(select(m.Prerequisite).where(m.Prerequisite.concept_id.in_(ids))).all()
    prereqs: dict[str, list[str]] = {c.id: [] for c in concepts_rows}
    for r in prereq_rows:
        if r.prerequisite_id in prereqs:
            prereqs[r.concept_id].append(r.prerequisite_id)

    concepts = {
        c.id: ConceptInfo(
            id=c.id,
            name=c.name,
            description=c.description,
            notes_md=c.notes_md,
            key_points=list(c.key_points or []),
            prerequisites=sorted(prereqs[c.id]),
        )
        for c in concepts_rows
    }
    for cid, ps in prereqs.items():
        for p in ps:
            concepts[p].dependents.append(cid)
    order = topo_sort(prereqs)
    for cid in order:
        ps = concepts[cid].prerequisites
        concepts[cid].depth = 0 if not ps else 1 + max(concepts[p].depth for p in ps)
    # Keep a stable, readable order: topo order.
    concepts = {cid: concepts[cid] for cid in order}

    misconceptions = {
        mc.id: MisconceptionInfo(
            id=mc.id,
            concept_id=mc.concept_id,
            description=mc.description,
            correct_belief=mc.correct_belief,
            analogy=mc.analogy or "",
            socratic=list(mc.socratic or []),
            replay_id=mc.replay_id,
        )
        for mc in db.scalars(select(m.Misconception).where(m.Misconception.concept_id.in_(ids))).all()
    }

    questions: dict[str, QuestionInfo] = {}
    q_rows = db.scalars(
        select(m.Question)
        .where(m.Question.status == "approved", m.Question.concept_id.in_(ids))
        .options(selectinload(m.Question.options))
    ).all()
    for q in q_rows:
        questions[q.id] = QuestionInfo(
            id=q.id,
            concept_id=q.concept_id,
            bloom_level=q.bloom_level,
            type=q.type,
            stem=q.stem,
            explanation=q.explanation,
            b=q.difficulty_b,
            options=[OptionInfo(o.id, o.text, o.is_correct, o.misconception_id) for o in q.options],
            hints=list(q.hints or []),
            status=q.status,
        )
    by_concept: dict[str, list[str]] = {cid: [] for cid in concepts}
    by_mis: dict[str, list[str]] = {mid: [] for mid in misconceptions}
    for qid, q in sorted(questions.items()):
        by_concept.setdefault(q.concept_id, []).append(qid)
        for t in q.targets:
            by_mis.setdefault(t, []).append(qid)

    subject = db.get(m.Subject, subject_id)
    worlds = list(subject.worlds) if subject is not None and subject.worlds else []
    diagnostic = list(subject.diagnostic_concepts) if subject is not None and subject.diagnostic_concepts else []
    if subject_id == DEFAULT_SUBJECT_ID:
        from app.core.levels import worlds as default_worlds

        worlds = worlds or default_worlds()
        diagnostic = diagnostic or get_settings().diagnostic_concept_ids

    return ContentGraph(
        concepts=concepts,
        misconceptions=misconceptions,
        questions=questions,
        topo_order=order,
        questions_by_concept=by_concept,
        questions_by_misconception=by_mis,
        subject_id=subject_id,
        worlds=worlds,
        diagnostic_concepts=[c for c in diagnostic if c in concepts],
    )


_lock = threading.Lock()
_graphs: dict[str, ContentGraph] = {}


def get_graph(db: Session, subject_id: str | None = None) -> ContentGraph:
    sid = subject_id or DEFAULT_SUBJECT_ID
    g = _graphs.get(sid)
    if g is None:
        with _lock:
            g = _graphs.get(sid)
            if g is None:
                g = _graphs[sid] = build_graph(db, sid)
    return g


def subject_of_concept(db: Session, concept_id: str) -> str:
    return db.scalar(select(m.Concept.subject_id).where(m.Concept.id == concept_id)) or DEFAULT_SUBJECT_ID


def invalidate(subject_id: str | None = None) -> None:
    with _lock:
        if subject_id is None:
            _graphs.clear()
        else:
            _graphs.pop(subject_id, None)
