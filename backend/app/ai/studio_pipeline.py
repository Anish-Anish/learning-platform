"""Teacher studio pipeline: uploaded material -> draft subject (concept graph, notes, quizzes, flashcards).

Pure with respect to the content DB (only llm_calls rows are written, via llm_client). Stages:
  1. figures   - vision model describes figures / OCRs scanned pages; markers replaced in the page text
  2. chunk     - heading-aware chunks with page references
  3. extract   - map: candidate concepts per chunk (parallel)
  4. graph     - reduce: merged concept graph + units; validated by core.studio_graph (code decides)
  5. author    - per concept (parallel): grounded notes + misconceptions, quizzes (generate_questions +
                 verifier), flashcards
Every LLM step has a deterministic fallback, so offline mode still yields a reviewable draft.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any

from app.ai.ingest.chunk import Chunk, chunk_documents
from app.ai.ingest.parse import Figure, ParsedDocument
from app.ai.llm_client import call
from app.ai.pipeline import extract_concepts, generate_questions
from app.config import get_settings
from app.core.studio_graph import GraphConcept, assign_units, concept_id, normalize_graph, slugify
from app.observability.logging import get_logger
from app.schemas.ai import (
    ChunkConcepts,
    ConceptNotesOut,
    FigureInsight,
    FlashcardSet,
    PageTranscript,
    SubjectGraphProposal,
)
from app.schemas.content import SeedConcept, SeedMisconception

log = get_logger(__name__)

Progress = Callable[[str, float, str], None]
EXCERPT_BUDGET = 16_000
_WORD = re.compile(r"[a-z0-9]{3,}")


class PipelineError(RuntimeError):
    pass


@dataclass
class DraftConcept:
    id: str
    key: str
    name: str
    description: str
    prerequisites: list[str]
    notes_md: str = ""
    key_points: list[str] = field(default_factory=list)
    misconceptions: list[dict[str, Any]] = field(default_factory=list)
    questions: list[dict[str, Any]] = field(default_factory=list)
    flashcards: list[dict[str, str]] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)


@dataclass
class StudioDraft:
    concepts: list[DraftConcept]
    units: list[dict]
    stats: dict[str, Any]
    warnings: list[str]


def _noop(_stage: str, _p: float, _msg: str) -> None:
    pass


def _parallel(fn: Callable[[Any], Any], items: list[Any], workers: int, on_done: Callable[[int], None]) -> list[Any]:
    out: list[Any] = [None] * len(items)
    if not items:
        return out
    with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        futs = {ex.submit(fn, it): i for i, it in enumerate(items)}
        done = 0
        for f in as_completed(futs):
            out[futs[f]] = f.result()
            done += 1
            on_done(done)
    return out


# ------------------------------------------------------------------ 1. figures
def describe_figures(docs: list[ParsedDocument], subject: str, trace_id: str, progress: Progress,
                     lo: float = 0.05, hi: float = 0.25) -> dict[str, int]:
    s = get_settings()
    scans = [(d, f) for d in docs for f in d.figures if f.kind == "scan"][: s.studio_max_ocr_pages]
    others = sorted(((d, f) for d in docs for f in d.figures if f.kind != "scan"), key=lambda t: -t[1].area)
    others = others[: s.studio_max_vision_images]
    work = scans + others
    replacement: dict[str, str] = {}
    stats = {"figures_described": 0, "figures_decorative": 0, "pages_ocr": 0, "figures_skipped": 0}

    def context_for(d: ParsedDocument, f: Figure) -> str:
        page = next((p for p in d.pages if p.number == f.page), None)
        text = page.markdown if page else ""
        i = text.find(f"[[FIGURE:{f.id}]]")
        return text[max(0, i - 700): i + 700] if i >= 0 else text[:1200]

    def run(item: tuple[ParsedDocument, Figure]) -> tuple[str, str, str]:
        d, f = item
        if f.kind == "scan":
            res = call(feature="studio_ocr", prompt_name="page_ocr", inputs={"subject": subject, "page": f.page},
                       output_schema=PageTranscript, model_tier="fast", trace_id=trace_id,
                       fallback=lambda: PageTranscript(markdown=""), images=[f.png], image_detail="high",
                       timeout_s=s.studio_llm_timeout_s)
            return f.id, "scan", res.output.markdown.strip()
        res = call(feature="studio_figure", prompt_name="figure_describe",
                   inputs={"subject": subject, "page": f.page, "context": context_for(d, f)},
                   document_keys=("context",), output_schema=FigureInsight, model_tier="fast", trace_id=trace_id,
                   fallback=lambda: FigureInsight(kind="decorative", description="", extracted_text=""),
                   images=[f.png], timeout_s=s.studio_llm_timeout_s)
        o: FigureInsight = res.output
        if o.kind == "decorative" or not o.description.strip():
            return f.id, "decorative", ""
        extra = f"\n> Details: {o.extracted_text.strip()}" if o.extracted_text.strip() else ""
        return f.id, o.kind, f"> **{o.kind.capitalize()} (p. {f.page}):** {o.description.strip()}{extra}"

    def tick(n: int) -> None:
        progress("figures", lo + (hi - lo) * n / max(1, len(work)), f"Reading figures and scanned pages ({n}/{len(work)})")

    for fid, kind, text in _parallel(run, work, s.studio_workers, tick):
        replacement[fid] = text
        if kind == "scan":
            stats["pages_ocr"] += 1 if text else 0
        elif kind == "decorative":
            stats["figures_decorative"] += 1
        else:
            stats["figures_described"] += 1
    stats["figures_skipped"] = sum(len(d.figures) for d in docs) - len(work)

    marker = re.compile(r"\[\[FIGURE:([^\]]+)\]\]")
    for d in docs:
        for p in d.pages:
            p.markdown = marker.sub(lambda m: replacement.get(m.group(1), ""), p.markdown).strip()
    return stats


# ------------------------------------------------------------------ 3. map
def _fallback_candidates(chunk: Chunk) -> ChunkConcepts:
    out = []
    for c in extract_concepts(chunk.text)[:8]:
        sentences = [x.strip() for x in re.split(r"(?<=[.!?])\s+", c["notes"]) if len(x.strip()) > 20]
        out.append({"name": c["name"][:100], "summary": sentences[0][:300] if sentences else c["name"],
                    "key_points": [x[:200] for x in sentences[:3]], "prerequisite_names": []})
    return ChunkConcepts.model_validate({"concepts": out})


def extract_candidates(chunks: list[Chunk], subject: str, trace_id: str, progress: Progress,
                       lo: float = 0.25, hi: float = 0.5) -> list[tuple[int, list[dict]]]:
    s = get_settings()

    def run(ch: Chunk) -> tuple[int, list[dict]]:
        res = call(feature="studio_extract", prompt_name="concept_extract",
                   inputs={"subject": subject, "chunk_index": ch.index, "ref": ch.ref, "text": ch.text},
                   document_keys=("text",), output_schema=ChunkConcepts, model_tier="fast", trace_id=trace_id,
                   fallback=lambda: _fallback_candidates(ch), timeout_s=s.studio_llm_timeout_s)
        return ch.index, [c.model_dump() for c in res.output.concepts[:8]]

    def tick(n: int) -> None:
        progress("extracting", lo + (hi - lo) * n / len(chunks), f"Finding concepts ({n}/{len(chunks)} sections)")

    return _parallel(run, chunks, s.studio_workers, tick)


# ------------------------------------------------------------------ 4. reduce
def _fallback_graph(candidates: list[tuple[int, list[dict]]], max_concepts: int) -> SubjectGraphProposal:
    merged: dict[str, dict] = {}
    for idx, cs in candidates:
        for c in cs:
            k = slugify(c["name"])
            if k not in merged:
                if len(merged) >= max_concepts:
                    continue
                merged[k] = {"key": k, "name": c["name"], "description": c["summary"], "prerequisites": [],
                             "source_chunks": []}
            merged[k]["source_chunks"].append(idx)
    names = {slugify(c["name"]): c for _, cs in candidates for c in cs}
    for k, m in merged.items():
        m["prerequisites"] = [slugify(p) for p in names.get(k, {}).get("prerequisite_names", []) if slugify(p) in merged]
    return SubjectGraphProposal.model_validate({"concepts": list(merged.values()), "units": []})


def build_graph(candidates: list[tuple[int, list[dict]]], n_chunks: int, subject: str, trace_id: str
                ) -> tuple[list[GraphConcept], list[dict], list[str]]:
    s = get_settings()
    compact = [{"chunk": idx, "concepts": [{"name": c["name"], "summary": c["summary"],
                                             "prerequisites": c.get("prerequisite_names", [])} for c in cs]}
               for idx, cs in candidates if cs]
    if not compact:
        raise PipelineError("no teachable concepts were found in the material")
    n_cand = sum(len(x["concepts"]) for x in compact)
    max_c = s.studio_max_concepts
    res = call(feature="studio_graph", prompt_name="concept_graph",
               inputs={"subject": subject, "candidates": compact, "min_concepts": min(max_c, max(3, n_cand // 6)),
                       "max_concepts": max_c},
               document_keys=(), output_schema=SubjectGraphProposal, model_tier="smart", trace_id=trace_id,
               fallback=lambda: _fallback_graph(candidates, max_c), timeout_s=s.studio_llm_timeout_s * 2)
    proposal: SubjectGraphProposal = res.output
    concepts, warnings = normalize_graph([c.model_dump() for c in proposal.concepts], n_chunks, max_c)
    if not concepts:
        raise PipelineError("the concept graph came back empty")
    names = {c.key: c.name for c in concepts}
    units = assign_units([c.key for c in concepts], [u.model_dump() for u in proposal.units], names)
    return concepts, units, warnings


# ------------------------------------------------------------------ 5. author
def _terms(text: str) -> set[str]:
    return set(_WORD.findall(text.lower()))


def select_excerpts(chunks: list[Chunk], idxs: list[int], name: str, description: str,
                    budget: int = EXCERPT_BUDGET) -> tuple[str, list[str]]:
    """Most relevant paragraphs from the concept's source chunks (or the best-matching chunks), in order."""
    terms = _terms(f"{name} {description}")
    pool = [chunks[i] for i in idxs if 0 <= i < len(chunks)]
    if not pool:
        ranked = sorted(chunks, key=lambda ch: -len(terms & _terms(ch.text)))
        pool = sorted(ranked[:3], key=lambda ch: ch.index)
    paras: list[tuple[int, int, str, str]] = []  # (score, order, text, ref)
    order = 0
    for ch in pool:
        for p in ch.text.split("\n\n"):
            if p.strip():
                paras.append((len(terms & _terms(p)), order, p.strip(), ch.ref))
                order += 1
    total = sum(len(p[2]) for p in paras)
    if total > budget:
        keep, used = [], 0
        for sc, o, t, r in sorted(paras, key=lambda x: (-x[0], x[1])):
            if used + len(t) > budget:
                continue
            keep.append((sc, o, t, r))
            used += len(t)
        paras = sorted(keep, key=lambda x: x[1])
    refs = list(dict.fromkeys(p[3] for p in paras))
    return "\n\n".join(p[2] for p in paras), refs


def author_concept(gc: GraphConcept, subject_id: str, subject: str, chunks: list[Chunk],
                   candidate_points: dict[str, list[str]], trace_id: str) -> DraftConcept:
    s = get_settings()
    cid = concept_id(subject_id, gc.key)
    dc = DraftConcept(id=cid, key=gc.key, name=gc.name, description=gc.description,
                      prerequisites=[concept_id(subject_id, p) for p in gc.prerequisites])
    excerpts, refs = select_excerpts(chunks, gc.source_chunks, gc.name, gc.description)
    dc.sources = refs

    def notes_fallback() -> ConceptNotesOut:
        return ConceptNotesOut(notes_md=excerpts[:2500], key_points=candidate_points.get(gc.key, [])[:5]
                               or [gc.description or gc.name], misconceptions=[])

    notes = call(feature="studio_notes", prompt_name="concept_notes",
                 inputs={"subject": subject, "concept": {"name": gc.name, "description": gc.description},
                         "excerpts": excerpts},
                 document_keys=("excerpts",), output_schema=ConceptNotesOut, model_tier="smart",
                 trace_id=trace_id, fallback=notes_fallback, timeout_s=s.studio_llm_timeout_s).output
    dc.notes_md = notes.notes_md.strip() or excerpts[:2500]
    dc.key_points = [k.strip()[:300] for k in notes.key_points if k.strip()][:6] or [gc.description or gc.name]
    dc.misconceptions = [
        {"id": f"{cid}.m{i + 1}", "concept_id": cid, "description": m.description.strip()[:400],
         "correct_belief": m.correct_belief.strip()[:400], "analogy": m.analogy.strip()[:600],
         "socratic": [q.strip()[:300] for q in m.socratic if q.strip()][:2]}
        for i, m in enumerate(notes.misconceptions[:3]) if m.description.strip()
    ]

    if dc.misconceptions:
        concept = SeedConcept(id=cid, name=gc.name, description=gc.description or gc.name, key_points=dc.key_points)
        mis = [SeedMisconception.model_validate(m) for m in dc.misconceptions]
        n = s.studio_questions_per_concept
        plan = [("understand", -0.3, (n + 1) // 2), ("apply", 0.3, n // 2)]
        if n > 4:
            plan.append(("analyze", 0.7, n - 4))
        for bloom, diff, k in plan:
            if k <= 0:
                continue
            qs, _stats = generate_questions(concept, dc.notes_md, mis, bloom, diff, k, trace_id=trace_id,
                                            id_prefix=f"q_{bloom[:3]}", subject=subject,
                                            timeout_s=s.studio_llm_timeout_s)
            dc.questions.extend(qs)

    def cards_fallback() -> FlashcardSet:
        cards = [{"front": f"{gc.name}: what is key idea #{i + 1}?", "back": kp} for i, kp in enumerate(dc.key_points)]
        cards += [{"front": f"True or false, and why: {m['description']}", "back": m["correct_belief"]}
                  for m in dc.misconceptions]
        return FlashcardSet.model_validate({"cards": cards})

    cards = call(feature="studio_flashcards", prompt_name="flashcards",
                 inputs={"subject": subject, "concept": gc.name, "key_points": dc.key_points,
                         "misconceptions": [m["description"] for m in dc.misconceptions], "notes": dc.notes_md,
                         "n": s.studio_flashcards_per_concept},
                 document_keys=("notes",), output_schema=FlashcardSet, model_tier="fast", trace_id=trace_id,
                 fallback=cards_fallback, timeout_s=s.studio_llm_timeout_s).output
    seen: set[str] = set()
    for c in cards.cards:
        front, back = c.front.strip()[:300], c.back.strip()[:600]
        if front and back and front.lower() not in seen:
            seen.add(front.lower())
            dc.flashcards.append({"front": front, "back": back})
    dc.flashcards = dc.flashcards[: s.studio_flashcards_per_concept + 2]
    return dc


# ------------------------------------------------------------------ entry point
def build_subject(docs: list[ParsedDocument], subject_id: str, subject: str, trace_id: str,
                  progress: Progress = _noop) -> StudioDraft:
    s = get_settings()
    fig_stats = describe_figures(docs, subject, trace_id, progress)

    chunks = chunk_documents(docs, s.studio_chunk_chars, s.studio_max_chunks)
    if not chunks:
        raise PipelineError("no readable text was found in the uploaded material")
    progress("extracting", 0.25, f"Finding concepts in {len(chunks)} sections")
    candidates = extract_candidates(chunks, subject, trace_id, progress)

    progress("graph", 0.5, "Building the concept graph")
    graph, units, warnings = build_graph(candidates, len(chunks), subject, trace_id)
    points: dict[str, list[str]] = {}
    for _, cs in candidates:
        for c in cs:
            points.setdefault(slugify(c["name"]), []).extend(c.get("key_points", []))

    def tick(n: int) -> None:
        progress("authoring", 0.55 + 0.4 * n / len(graph), f"Writing notes, quizzes and flashcards ({n}/{len(graph)})")

    progress("authoring", 0.55, f"Writing notes, quizzes and flashcards for {len(graph)} concepts")
    drafts = _parallel(lambda gc: author_concept(gc, subject_id, subject, chunks, points, trace_id),
                       graph, max(1, s.studio_workers // 2), tick)
    key_to_id = {d.key: d.id for d in drafts}
    worlds = [{**u, "concepts": [key_to_id[k] for k in u["concepts"] if k in key_to_id]} for u in units]
    stats = {
        **fig_stats,
        "documents": len(docs),
        "pages": sum(d.stats.get("pages", 0) for d in docs),
        "chunks": len(chunks),
        "candidates": sum(len(cs) for _, cs in candidates),
        "concepts": len(drafts),
        "questions": sum(len(d.questions) for d in drafts),
        "flashcards": sum(len(d.flashcards) for d in drafts),
        "misconceptions": sum(len(d.misconceptions) for d in drafts),
    }
    log.info("studio_pipeline_done", subject_id=subject_id, **{k: v for k, v in stats.items() if isinstance(v, int)})
    return StudioDraft(concepts=drafts, units=worlds, stats=stats, warnings=warnings)
