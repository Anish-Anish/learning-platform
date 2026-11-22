"""Teacher studio services: subjects, uploads, ingestion jobs, review edits, publishing, enrollment.

The LLM pipeline (ai/studio_pipeline.py) only proposes a draft. This module validates and persists it,
and decides what students can see: nothing reaches a student until the teacher publishes (PROJECT_CONTEXT
§19.3), and only enrolled students see a non-default subject.
"""

from __future__ import annotations

import contextvars
import re
import shutil
import threading
import time
import uuid
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import BinaryIO

from opentelemetry.trace import Status, StatusCode
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, selectinload

from app.ai.verifier import deterministic_check
from app.config import DEFAULT_SUBJECT_ID, UPLOADS_DIR, get_settings
from app.core import graph as graph_mod
from app.core.graph import find_cycle, topo_sort
from app.core.student_state import get_or_create_student
from app.core.studio_graph import pick_diagnostic, rewire_without, subject_id_for
from app.db import models as m
from app.db.session import SessionLocal
from app.observability import otel
from app.observability.logging import get_logger
from app.observability.tracing import TokenBudget, new_trace_id, set_budget, set_llm_scope, set_trace_id
from app.schemas.common import BLOOM_ORDER
from app.schemas.studio import (
    ConceptPatch,
    EnrollmentList,
    EnrollmentStudent,
    FlashcardIn,
    QuestionPatch,
    SourceDocumentOut,
    StudentSubject,
    StudentSubjects,
    StudioConcept,
    StudioConceptContent,
    StudioFlashcard,
    StudioGraph,
    StudioJobOut,
    StudioMisconception,
    StudioOption,
    StudioQuestion,
    StudioWorld,
    SubjectDetail,
    SubjectSummary,
)

log = get_logger(__name__)

EDITABLE = {"draft", "review", "failed"}
STUDENT_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
PDF_MAGIC = b"%PDF-"


class StudioError(ValueError):
    status_code = 422


class StudioNotFound(StudioError):
    status_code = 404


class StudioConflict(StudioError):
    status_code = 409


class UploadTooLarge(StudioError):
    status_code = 413


# ------------------------------------------------------------------ lookups / guards
def get_subject(db: Session, subject_id: str) -> m.Subject:
    s = db.get(m.Subject, subject_id)
    if s is None:
        raise StudioNotFound(f"unknown subject {subject_id}")
    return s


def _require_editable(subject: m.Subject) -> None:
    if subject.is_default:
        raise StudioConflict("the built-in subject can't be edited in the studio")
    if subject.status == "processing":
        raise StudioConflict("generation is still running for this subject")
    if subject.status not in EDITABLE:
        raise StudioConflict("unpublish the subject before editing it")


def _concept_ids(subject_id: str):
    return select(m.Concept.id).where(m.Concept.subject_id == subject_id)


def _has_attempts(db: Session, concept_ids) -> bool:
    return db.scalar(select(m.Attempt.id).where(m.Attempt.concept_id.in_(concept_ids)).limit(1)) is not None


def _concept_in_editable_subject(db: Session, concept_id: str) -> tuple[m.Concept, m.Subject]:
    c = db.get(m.Concept, concept_id)
    if c is None:
        raise StudioNotFound(f"unknown concept {concept_id}")
    subject = get_subject(db, c.subject_id)
    _require_editable(subject)
    return c, subject


# ------------------------------------------------------------------ subjects + uploads
def create_subject(db: Session, name: str, description: str) -> m.Subject:
    name = name.strip()
    if not name:
        raise StudioError("subject name is required")
    s = m.Subject(id=subject_id_for(name, uuid.uuid4().hex[:6]), name=name[:120], description=description.strip()[:1000],
                  status="draft")
    db.add(s)
    db.flush()
    return s


def store_upload(db: Session, subject: m.Subject, filename: str, stream: BinaryIO) -> m.SourceDocument:
    """Stream an upload to disk (never fully in memory) with type + size checks."""
    from app.ai.ingest.parse import SUPPORTED_SUFFIXES

    s = get_settings()
    safe = Path(filename or "upload").name[:200] or "upload"
    suffix = Path(safe).suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise StudioError(f"{safe}: unsupported file type; upload PDF, Markdown (.md) or text (.txt)")
    n_docs = db.scalar(select(func.count(m.SourceDocument.id)).where(m.SourceDocument.subject_id == subject.id)) or 0
    if n_docs >= s.studio_max_files:
        raise StudioError(f"a subject can have at most {s.studio_max_files} files")
    doc = m.SourceDocument(id=m.new_id("doc"), owner_id=subject.owner_id, subject_id=subject.id, filename=safe,
                           status="uploaded")
    folder = UPLOADS_DIR / subject.id
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{doc.id}{suffix}"
    limit = s.studio_max_upload_mb * 1024 * 1024
    size = 0
    try:
        with path.open("wb") as out:
            first = True
            while chunk := stream.read(1024 * 1024):
                if first and suffix == ".pdf" and not chunk.startswith(PDF_MAGIC):
                    raise StudioError(f"{safe} is not a valid PDF")
                first = False
                size += len(chunk)
                if size > limit:
                    raise UploadTooLarge(f"{safe} is larger than {s.studio_max_upload_mb} MB")
                out.write(chunk)
    except Exception:
        path.unlink(missing_ok=True)
        raise
    if size == 0:
        path.unlink(missing_ok=True)
        raise StudioError(f"{safe} is empty")
    doc.storage_path, doc.size_bytes = str(path), size
    db.add(doc)
    db.flush()
    return doc


# ------------------------------------------------------------------ ingestion jobs
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="studio")
_run_inline = False


def set_inline(value: bool) -> None:
    """Tests run jobs synchronously."""
    global _run_inline
    _run_inline = value


def start_job(db: Session, subject: m.Subject) -> m.StudioJob:
    if subject.status == "processing":
        raise StudioConflict("generation is already running")
    if subject.is_default:
        raise StudioConflict("the built-in subject is loaded from seed files")
    if subject.status == "published":
        raise StudioConflict("unpublish the subject before regenerating it")
    if _has_attempts(db, _concept_ids(subject.id)):
        raise StudioConflict("students have already practised this subject; create a new subject instead")
    if not db.scalar(select(m.SourceDocument.id).where(m.SourceDocument.subject_id == subject.id).limit(1)):
        raise StudioError("upload at least one file first")
    job = m.StudioJob(subject_id=subject.id, trace_id=new_trace_id(), status="queued", stage="queued",
                      message="Waiting to start")
    subject.status = "processing"
    db.add(job)
    db.commit()
    if _run_inline:
        run_job(job.id)
    else:
        _executor.submit(run_job, job.id)
    db.expire_all()  # the job writes through its own sessions
    return job


class _Progress:
    def __init__(self, job_id: str) -> None:
        self.job_id = job_id
        self.stage = ""
        self.last = 0.0
        self.lock = threading.Lock()

    def __call__(self, stage: str, frac: float, message: str) -> None:
        now = time.monotonic()
        with self.lock:
            if stage == self.stage and now - self.last < 0.5:
                return
            self.stage, self.last = stage, now
        try:
            with SessionLocal() as db:
                job = db.get(m.StudioJob, self.job_id)
                if job is not None:
                    job.stage, job.progress, job.message = stage, round(min(1.0, max(0.0, frac)), 3), message[:300]
                    job.updated_at = m.utcnow()
                    db.commit()
        except Exception as exc:  # progress is best-effort
            log.warning("studio_progress_write_failed", error=str(exc))


def run_job(job_id: str) -> None:
    """Runs on a worker thread in a fresh context (nothing leaks between jobs sharing a pool thread)."""
    contextvars.Context().run(_run_job_traced, job_id)


def _run_job_traced(job_id: str) -> None:
    """Own trace, LLM cost scope 'studio' and a hard token budget for the whole job."""
    with SessionLocal() as db:
        job = db.get(m.StudioJob, job_id)
        if job is None:
            return
        trace_id, subject_id = job.trace_id, job.subject_id
    set_trace_id(trace_id)
    set_llm_scope("studio")
    set_budget(TokenBudget(get_settings().studio_max_tokens_per_job))
    with otel.span("studio.job", **{"rootwise.trace_id": trace_id, "rootwise.job_id": job_id,
                                    "rootwise.subject_id": subject_id}) as sp:
        ok = _run_job(job_id)
        if not ok:
            sp.set_status(Status(StatusCode.ERROR, "generation failed"))
    otel.STUDIO_JOBS.add(1, {"outcome": "done" if ok else "failed"})


def _run_job(job_id: str) -> bool:
    from app.ai.ingest.parse import ParseError, parse_file
    from app.ai.studio_pipeline import PipelineError, build_subject

    progress = _Progress(job_id)
    with SessionLocal() as db:
        job = db.get(m.StudioJob, job_id)
        if job is None:
            return False
        subject = get_subject(db, job.subject_id)
        job.status, job.stage, job.message = "running", "parsing", "Reading your files"
        db.commit()
        sid, sname, trace_id = subject.id, subject.name, job.trace_id
        doc_rows = [(d.id, d.filename, d.storage_path) for d in db.scalars(
            select(m.SourceDocument).where(m.SourceDocument.subject_id == sid).order_by(m.SourceDocument.created_at))]
    s = get_settings()
    log.info("studio_job_started", job_id=job_id, subject_id=sid, documents=len(doc_rows), trace_id=trace_id)
    try:
        parsed = []
        for i, (doc_id, fname, path) in enumerate(doc_rows):
            progress("parsing", 0.05 * i / max(1, len(doc_rows)), f"Reading {fname}")
            try:
                pd = parse_file(Path(path or ""), doc_id, fname, s.studio_max_pages, s.studio_min_image_px)
                parsed.append(pd)
                _update_doc(doc_id, status="parsed", page_count=pd.page_count, parse_stats=pd.stats, error=None)
            except (ParseError, OSError) as exc:
                _update_doc(doc_id, status="failed", error=str(exc)[:500])
        if not parsed:
            raise PipelineError("none of the uploaded files could be read")

        draft = build_subject(parsed, sid, sname, trace_id, progress)

        progress("saving", 0.97, "Saving the draft for your review")
        for pd in parsed:
            text = "\n\n".join(p.markdown for p in pd.pages)
            _update_doc(pd.doc_id, parsed_text=text[:2_000_000])
        with SessionLocal() as db:
            persist_draft(db, sid, draft)
            job = db.get(m.StudioJob, job_id)
            subject = get_subject(db, sid)
            job.status, job.stage, job.progress = "done", "done", 1.0
            job.message = (f"Generated {draft.stats['concepts']} concepts, {draft.stats['questions']} quiz questions "
                           f"and {draft.stats['flashcards']} flashcards. Review, then publish.")
            job.stats = {**draft.stats, "warnings": draft.warnings}
            job.finished_at = job.updated_at = m.utcnow()
            subject.status = "review"
            db.commit()
        log.info("studio_job_done", job_id=job_id, subject_id=sid, trace_id=trace_id,
                 concepts=draft.stats["concepts"], questions=draft.stats["questions"],
                 tokens_used=draft.stats.get("tokens_used"))
        return True
    except Exception as exc:
        log.warning("studio_job_failed", job_id=job_id, subject_id=sid, error=f"{type(exc).__name__}: {exc}")
        with SessionLocal() as db:
            job = db.get(m.StudioJob, job_id)
            subject = db.get(m.Subject, sid)
            if job is not None:
                job.status, job.stage = "failed", "failed"
                job.error = str(exc)[:500] if isinstance(exc, PipelineError) else f"{type(exc).__name__}: {exc}"[:500]
                job.message = "Generation failed"
                job.finished_at = job.updated_at = m.utcnow()
            if subject is not None:
                subject.status = "failed"
            db.commit()
        return False


def _update_doc(doc_id: str, **fields) -> None:
    with SessionLocal() as db:
        d = db.get(m.SourceDocument, doc_id)
        if d is not None:
            for k, v in fields.items():
                setattr(d, k, v)
            db.commit()


def recover_interrupted_jobs(db: Session) -> int:
    """Jobs run in-process; after a restart, mark unfinished ones failed so the teacher can regenerate."""
    jobs = db.scalars(select(m.StudioJob).where(m.StudioJob.status.in_(["queued", "running"]))).all()
    for j in jobs:
        j.status, j.stage, j.message = "failed", "failed", "Generation failed"
        j.error = "The server restarted during generation. Click Regenerate to try again."
        j.finished_at = m.utcnow()
        s = db.get(m.Subject, j.subject_id)
        if s is not None and s.status == "processing":
            s.status = "failed"
    db.commit()
    return len(jobs)


# ------------------------------------------------------------------ persistence
def _delete_subject_content(db: Session, subject_id: str) -> None:
    cids = [c for c in db.scalars(_concept_ids(subject_id))]
    if cids:
        qids = select(m.Question.id).where(m.Question.concept_id.in_(cids))
        db.execute(delete(m.Option).where(m.Option.question_id.in_(qids)))
        db.execute(delete(m.Question).where(m.Question.concept_id.in_(cids)))
        db.execute(delete(m.Misconception).where(m.Misconception.concept_id.in_(cids)))
        db.execute(delete(m.Prerequisite).where(m.Prerequisite.concept_id.in_(cids)))
        db.execute(delete(m.Prerequisite).where(m.Prerequisite.prerequisite_id.in_(cids)))
        db.execute(delete(m.MasteryState).where(m.MasteryState.concept_id.in_(cids)))
        db.execute(delete(m.LevelRun).where(m.LevelRun.concept_id.in_(cids)))
    db.execute(delete(m.Flashcard).where(m.Flashcard.subject_id == subject_id))
    db.execute(delete(m.Concept).where(m.Concept.subject_id == subject_id))
    db.flush()


def persist_draft(db: Session, subject_id: str, draft) -> None:
    subject = get_subject(db, subject_id)
    _delete_subject_content(db, subject_id)
    for i, dc in enumerate(draft.concepts):
        db.add(m.Concept(id=dc.id, subject_id=subject_id, position=i, name=dc.name, description=dc.description or dc.name,
                         notes_md=dc.notes_md, key_points=dc.key_points, bloom_levels=list(BLOOM_ORDER),
                         status="draft"))
    db.flush()
    ids = {dc.id for dc in draft.concepts}
    for dc in draft.concepts:
        for p in dc.prerequisites:
            if p in ids:
                db.add(m.Prerequisite(concept_id=dc.id, prerequisite_id=p))
        for mc in dc.misconceptions:
            db.add(m.Misconception(id=mc["id"], concept_id=dc.id, description=mc["description"],
                                   correct_belief=mc["correct_belief"], analogy=mc["analogy"], socratic=mc["socratic"]))
    db.flush()
    seen_q: set[str] = set()
    for dc in draft.concepts:
        for q in dc.questions:
            if q["id"] in seen_q:
                continue
            seen_q.add(q["id"])
            row = m.Question(id=q["id"], concept_id=dc.id, bloom_level=q["bloom_level"], type="mcq", stem=q["stem"],
                             explanation=q["explanation"], difficulty_b=max(-3.0, min(3.0, float(q["difficulty_b"]))),
                             hints=[], status="draft", source="generated", verifier_report=q.get("verifier_report"))
            row.options = [m.Option(id=o["id"], position=i, text=o["text"], is_correct=o["is_correct"],
                                    misconception_id=None if o["is_correct"] else o.get("misconception_id"))
                           for i, o in enumerate(q["options"])]
            db.add(row)
        for i, fc in enumerate(dc.flashcards):
            db.add(m.Flashcard(subject_id=subject_id, concept_id=dc.id, position=i, front=fc["front"], back=fc["back"],
                               status="draft", source="generated"))
    subject.worlds = draft.units
    _refresh_derived(db, subject)
    db.flush()


def _prereq_map(db: Session, subject_id: str) -> dict[str, list[str]]:
    cids = list(db.scalars(_concept_ids(subject_id).order_by(m.Concept.position, m.Concept.id)))
    out: dict[str, list[str]] = {c: [] for c in cids}
    for r in db.scalars(select(m.Prerequisite).where(m.Prerequisite.concept_id.in_(cids))):
        if r.prerequisite_id in out:
            out[r.concept_id].append(r.prerequisite_id)
    return out


def _question_counts(db: Session, subject_id: str) -> Counter:
    rows = db.execute(select(m.Question.concept_id, func.count(m.Question.id))
                      .where(m.Question.concept_id.in_(_concept_ids(subject_id)))
                      .group_by(m.Question.concept_id)).all()
    return Counter({cid: int(n) for cid, n in rows})


def _refresh_derived(db: Session, subject: m.Subject) -> None:
    """Keep worlds and diagnostic picks consistent with the current concepts."""
    prereqs = _prereq_map(db, subject.id)
    order = topo_sort(prereqs)
    worlds = []
    placed: set[str] = set()
    for w in subject.worlds or []:
        cs = [c for c in w.get("concepts", []) if c in prereqs and c not in placed]
        placed.update(cs)
        if cs:
            worlds.append({**w, "concepts": cs})
    rest = [c for c in order if c not in placed]
    if rest:
        worlds.append({"id": f"u{len(worlds) + 1}", "name": "More to explore", "tagline": "Everything else.",
                       "emoji": "🧭", "color": "rose", "concepts": rest})
    subject.worlds = worlds
    has_q = {c for c, n in _question_counts(db, subject.id).items() if n > 0}
    subject.diagnostic_concepts = pick_diagnostic(order, has_q)


# ------------------------------------------------------------------ review edits
def update_concept(db: Session, concept_id: str, patch: ConceptPatch) -> m.Concept:
    c, subject = _concept_in_editable_subject(db, concept_id)
    if patch.name is not None:
        c.name = patch.name.strip()
    if patch.description is not None:
        c.description = patch.description.strip()
    if patch.notes_md is not None:
        c.notes_md = patch.notes_md
    if patch.key_points is not None:
        kps = [k.strip()[:300] for k in patch.key_points if k.strip()]
        if not kps:
            raise StudioError("a concept needs at least one key point")
        c.key_points = kps[:8]
    if patch.prerequisites is not None:
        prereqs = _prereq_map(db, subject.id)
        new = list(dict.fromkeys(patch.prerequisites))
        for p in new:
            if p not in prereqs:
                raise StudioError(f"{p} is not a concept in this subject")
            if p == concept_id:
                raise StudioError("a concept can't be its own prerequisite")
        prereqs[concept_id] = new
        cycle = find_cycle(prereqs)
        if cycle:
            names = {x.id: x.name for x in db.scalars(select(m.Concept).where(m.Concept.id.in_(cycle)))}
            raise StudioError("that would create a loop: " + " → ".join(names.get(x, x) for x in cycle))
        db.execute(delete(m.Prerequisite).where(m.Prerequisite.concept_id == concept_id))
        for p in new:
            db.add(m.Prerequisite(concept_id=concept_id, prerequisite_id=p))
        db.flush()
        _refresh_derived(db, subject)
    db.flush()
    return c


def delete_concept(db: Session, concept_id: str) -> None:
    c, subject = _concept_in_editable_subject(db, concept_id)
    if _has_attempts(db, [concept_id]):
        raise StudioConflict("students have answered questions on this concept")
    rewired = rewire_without(_prereq_map(db, subject.id), concept_id)
    qids = select(m.Question.id).where(m.Question.concept_id == concept_id)
    db.execute(delete(m.Option).where(m.Option.question_id.in_(qids)))
    db.execute(delete(m.Question).where(m.Question.concept_id == concept_id))
    db.execute(delete(m.Misconception).where(m.Misconception.concept_id == concept_id))
    db.execute(delete(m.Flashcard).where(m.Flashcard.concept_id == concept_id))
    db.execute(delete(m.MasteryState).where(m.MasteryState.concept_id == concept_id))
    db.execute(delete(m.Prerequisite).where(m.Prerequisite.concept_id.in_(list(rewired) + [concept_id])))
    db.execute(delete(m.Prerequisite).where(m.Prerequisite.prerequisite_id == concept_id))
    db.delete(c)
    db.flush()
    for cid, ps in rewired.items():
        for p in ps:
            db.add(m.Prerequisite(concept_id=cid, prerequisite_id=p))
    db.flush()
    _refresh_derived(db, subject)


def _question_in_editable_subject(db: Session, question_id: str) -> m.Question:
    q = db.scalars(select(m.Question).where(m.Question.id == question_id).options(selectinload(m.Question.options))).first()
    if q is None:
        raise StudioNotFound(f"unknown question {question_id}")
    _concept_in_editable_subject(db, q.concept_id)
    return q


def update_question(db: Session, question_id: str, patch: QuestionPatch) -> m.Question:
    q = _question_in_editable_subject(db, question_id)
    if patch.stem is not None:
        q.stem = patch.stem.strip()
    if patch.explanation is not None:
        q.explanation = patch.explanation.strip()
    if patch.options:
        by_id = {o.id: o for o in q.options}
        for op in patch.options:
            if op.id not in by_id:
                raise StudioError(f"unknown option {op.id}")
            by_id[op.id].text = op.text.strip()
    known = set(db.scalars(select(m.Misconception.id).where(m.Misconception.concept_id == q.concept_id)))
    issues = deterministic_check({
        "stem": q.stem, "bloom_level": q.bloom_level, "explanation": q.explanation, "type": q.type,
        "options": [{"id": o.id, "text": o.text, "is_correct": o.is_correct, "misconception_id": o.misconception_id}
                    for o in q.options],
    }, known)
    if issues:
        raise StudioError("; ".join(issues))
    q.verifier_report = {**(q.verifier_report or {}), "edited_by_teacher": True}
    db.flush()
    return q


def delete_question(db: Session, question_id: str) -> None:
    q = _question_in_editable_subject(db, question_id)
    if db.scalar(select(m.Attempt.id).where(m.Attempt.question_id == question_id).limit(1)):
        raise StudioConflict("students have answered this question")
    subject = get_subject(db, db.get(m.Concept, q.concept_id).subject_id)
    db.delete(q)
    db.flush()
    _refresh_derived(db, subject)


def _flashcard_in_editable_subject(db: Session, card_id: str) -> m.Flashcard:
    fc = db.get(m.Flashcard, card_id)
    if fc is None:
        raise StudioNotFound(f"unknown flashcard {card_id}")
    _require_editable(get_subject(db, fc.subject_id))
    return fc


def update_flashcard(db: Session, card_id: str, body: FlashcardIn) -> m.Flashcard:
    fc = _flashcard_in_editable_subject(db, card_id)
    fc.front, fc.back = body.front.strip(), body.back.strip()
    db.flush()
    return fc


def delete_flashcard(db: Session, card_id: str) -> None:
    db.delete(_flashcard_in_editable_subject(db, card_id))
    db.flush()


def create_flashcard(db: Session, concept_id: str, body: FlashcardIn) -> m.Flashcard:
    c, subject = _concept_in_editable_subject(db, concept_id)
    n = db.scalar(select(func.count(m.Flashcard.id)).where(m.Flashcard.concept_id == concept_id)) or 0
    fc = m.Flashcard(subject_id=subject.id, concept_id=c.id, position=n, front=body.front.strip(),
                     back=body.back.strip(), status="draft", source="teacher")
    db.add(fc)
    db.flush()
    return fc


# ------------------------------------------------------------------ publish
def publish_blockers(db: Session, subject_id: str) -> list[str]:
    concepts = db.scalars(select(m.Concept).where(m.Concept.subject_id == subject_id).order_by(m.Concept.id)).all()
    if not concepts:
        return ["there are no concepts yet"]
    counts = _question_counts(db, subject_id)
    out = [f"'{c.name}' has no quiz questions (delete it or add material and regenerate)"
           for c in concepts if counts.get(c.id, 0) == 0]
    if find_cycle(_prereq_map(db, subject_id)):
        out.append("the prerequisite graph has a loop")
    return out


def publish(db: Session, subject_id: str) -> m.Subject:
    subject = get_subject(db, subject_id)
    if subject.is_default:
        raise StudioConflict("the built-in subject is always published")
    if subject.status == "published":
        raise StudioConflict("already published")
    if subject.status == "processing":
        raise StudioConflict("generation is still running")
    blockers = publish_blockers(db, subject_id)
    if blockers:
        raise StudioError("can't publish yet: " + "; ".join(blockers))
    cids = list(db.scalars(_concept_ids(subject_id)))
    for c in db.scalars(select(m.Concept).where(m.Concept.id.in_(cids))):
        c.status = "approved"
    for q in db.scalars(select(m.Question).where(m.Question.concept_id.in_(cids))):
        q.status = "approved"
    for fc in db.scalars(select(m.Flashcard).where(m.Flashcard.subject_id == subject_id)):
        fc.status = "approved"
    _refresh_derived(db, subject)
    subject.status = "published"
    subject.published_at = m.utcnow()
    subject.content_version = (subject.content_version or 1) + 1
    db.commit()
    graph_mod.invalidate(subject_id)
    return subject


def unpublish(db: Session, subject_id: str) -> m.Subject:
    subject = get_subject(db, subject_id)
    if subject.is_default:
        raise StudioConflict("the built-in subject can't be unpublished")
    if subject.status != "published":
        raise StudioConflict("subject is not published")
    subject.status = "review"
    db.commit()
    graph_mod.invalidate(subject_id)
    return subject


def delete_subject(db: Session, subject_id: str) -> None:
    subject = get_subject(db, subject_id)
    if subject.is_default:
        raise StudioConflict("the built-in subject can't be deleted")
    if subject.status == "processing":
        raise StudioConflict("generation is still running")
    if _has_attempts(db, _concept_ids(subject_id)):
        raise StudioConflict("students have practised this subject; unpublish it instead")
    _delete_subject_content(db, subject_id)
    db.execute(delete(m.Enrollment).where(m.Enrollment.subject_id == subject_id))
    db.execute(delete(m.StudioJob).where(m.StudioJob.subject_id == subject_id))
    db.execute(delete(m.SourceDocument).where(m.SourceDocument.subject_id == subject_id))
    db.delete(subject)
    db.commit()
    shutil.rmtree(UPLOADS_DIR / subject_id, ignore_errors=True)
    graph_mod.invalidate(subject_id)


# ------------------------------------------------------------------ enrollment
def enrollment_list(db: Session, subject_id: str, trace_id: str) -> EnrollmentList:
    subject = get_subject(db, subject_id)
    enrolled = set(db.scalars(select(m.Enrollment.student_id).where(m.Enrollment.subject_id == subject_id)))
    students = db.scalars(select(m.Student).order_by(m.Student.is_simulated, m.Student.id)).all()
    out = [EnrollmentStudent(id=s.id, display_name=s.display_name, is_simulated=s.is_simulated,
                             enrolled=subject.is_default or s.id in enrolled)
           for s in students if not s.is_simulated or s.id in enrolled]
    return EnrollmentList(trace_id=trace_id, subject_id=subject_id, students=out)


def set_enrollment(db: Session, subject_id: str, student_ids: list[str]) -> None:
    subject = get_subject(db, subject_id)
    if subject.is_default:
        raise StudioConflict("every student is enrolled in the built-in subject")
    wanted = list(dict.fromkeys(s.strip() for s in student_ids if s.strip()))
    bad = [s for s in wanted if not STUDENT_ID.match(s)]
    if bad:
        raise StudioError(f"invalid student ids: {', '.join(bad[:5])}")
    for sid in wanted:
        get_or_create_student(db, sid)
    db.execute(delete(m.Enrollment).where(m.Enrollment.subject_id == subject_id,
                                          m.Enrollment.student_id.not_in(wanted)))
    have = set(db.scalars(select(m.Enrollment.student_id).where(m.Enrollment.subject_id == subject_id)))
    for sid in wanted:
        if sid not in have:
            db.add(m.Enrollment(student_id=sid, subject_id=subject_id))
    db.commit()


def student_subjects(db: Session, student_id: str, trace_id: str) -> StudentSubjects:
    enrolled = select(m.Enrollment.subject_id).where(m.Enrollment.student_id == student_id)
    rows = db.scalars(select(m.Subject).where(
        (m.Subject.id == DEFAULT_SUBJECT_ID) | ((m.Subject.status == "published") & m.Subject.id.in_(enrolled))
    ).order_by(m.Subject.is_default.desc(), m.Subject.name)).all()
    counts = dict(db.execute(select(m.Concept.subject_id, func.count(m.Concept.id))
                             .group_by(m.Concept.subject_id)).all())
    return StudentSubjects(trace_id=trace_id, student_id=student_id, subjects=[
        StudentSubject(id=s.id, name=s.name, description=s.description, is_default=s.is_default,
                       n_concepts=int(counts.get(s.id, 0)))
        for s in rows
    ])


# ------------------------------------------------------------------ read models
def _job_out(job: m.StudioJob | None) -> StudioJobOut | None:
    if job is None:
        return None
    return StudioJobOut(id=job.id, status=job.status, stage=job.stage, progress=job.progress, message=job.message,  # type: ignore[arg-type]
                        error=job.error, stats=job.stats or {}, created_at=job.created_at, finished_at=job.finished_at)


def _latest_job(db: Session, subject_id: str) -> m.StudioJob | None:
    return db.scalars(select(m.StudioJob).where(m.StudioJob.subject_id == subject_id)
                      .order_by(m.StudioJob.created_at.desc())).first()


def subject_summary(db: Session, s: m.Subject) -> SubjectSummary:
    cids = _concept_ids(s.id)
    n_students = (db.scalar(select(func.count(m.Student.id)).where(m.Student.is_simulated.is_(False))) if s.is_default
                  else db.scalar(select(func.count()).select_from(m.Enrollment).where(m.Enrollment.subject_id == s.id)))
    return SubjectSummary(
        id=s.id, name=s.name, description=s.description, status=s.status, is_default=s.is_default,  # type: ignore[arg-type]
        n_concepts=db.scalar(select(func.count()).select_from(m.Concept).where(m.Concept.subject_id == s.id)) or 0,
        n_questions=db.scalar(select(func.count()).select_from(m.Question).where(m.Question.concept_id.in_(cids))) or 0,
        n_flashcards=db.scalar(select(func.count()).select_from(m.Flashcard).where(m.Flashcard.subject_id == s.id)) or 0,
        n_documents=db.scalar(select(func.count()).select_from(m.SourceDocument)
                              .where(m.SourceDocument.subject_id == s.id)) or 0,
        n_students=int(n_students or 0), created_at=s.created_at, published_at=s.published_at,
        job=_job_out(_latest_job(db, s.id)),
    )


def list_subjects(db: Session) -> list[SubjectSummary]:
    rows = db.scalars(select(m.Subject).order_by(m.Subject.is_default.desc(), m.Subject.created_at.desc())).all()
    return [subject_summary(db, s) for s in rows]


def subject_detail(db: Session, subject_id: str, trace_id: str) -> SubjectDetail:
    s = get_subject(db, subject_id)
    docs = db.scalars(select(m.SourceDocument).where(m.SourceDocument.subject_id == subject_id)
                      .order_by(m.SourceDocument.created_at)).all()
    job = _latest_job(db, subject_id)
    editable = not s.is_default and s.status in EDITABLE
    worlds = s.worlds
    if s.is_default:
        worlds = graph_mod.get_graph(db, subject_id).worlds
    return SubjectDetail(
        trace_id=trace_id, subject=subject_summary(db, s),
        documents=[SourceDocumentOut(id=d.id, filename=d.filename, size_bytes=d.size_bytes, page_count=d.page_count,
                                     status=d.status, error=d.error, parse_stats=d.parse_stats) for d in docs],
        worlds=[StudioWorld(**{k: w.get(k, "") for k in ("id", "name", "tagline", "emoji", "color")},
                            concepts=list(w.get("concepts", []))) for w in worlds or []],
        diagnostic_concepts=list(s.diagnostic_concepts or []),
        warnings=list((job.stats or {}).get("warnings", [])) if job else [],
        publish_blockers=publish_blockers(db, subject_id) if editable and s.status != "failed" else [],
        editable=editable,
    )


def _studio_concepts(db: Session, subject: m.Subject, only: str | None = None) -> list[StudioConcept]:
    prereqs = _prereq_map(db, subject.id)
    order = topo_sort(prereqs)
    depth: dict[str, int] = {}
    for c in order:
        depth[c] = 0 if not prereqs[c] else 1 + max(depth[p] for p in prereqs[c])
    rows = {c.id: c for c in db.scalars(select(m.Concept).where(m.Concept.subject_id == subject.id))}
    qn = _question_counts(db, subject.id)
    fn = Counter(dict(db.execute(select(m.Flashcard.concept_id, func.count(m.Flashcard.id))
                                 .where(m.Flashcard.subject_id == subject.id).group_by(m.Flashcard.concept_id)).all()))
    mn = Counter(dict(db.execute(select(m.Misconception.concept_id, func.count(m.Misconception.id))
                                 .where(m.Misconception.concept_id.in_(list(rows))).group_by(m.Misconception.concept_id)).all()))
    world_of = {c: w.get("id") for w in subject.worlds or [] for c in w.get("concepts", [])}
    if subject.is_default:
        world_of = {c: w["id"] for w in graph_mod.get_graph(db, subject.id).worlds for c in w["concepts"]}
    return [
        StudioConcept(id=c, name=rows[c].name, description=rows[c].description, prerequisites=sorted(prereqs[c]),
                      depth=depth[c], notes_md=rows[c].notes_md, key_points=list(rows[c].key_points or []),
                      n_questions=qn.get(c, 0), n_flashcards=int(fn.get(c, 0)), n_misconceptions=int(mn.get(c, 0)),
                      world_id=world_of.get(c))
        for c in order if only is None or c == only
    ]


def studio_graph(db: Session, subject_id: str, trace_id: str) -> StudioGraph:
    s = get_subject(db, subject_id)
    return StudioGraph(trace_id=trace_id, subject_id=subject_id, concepts=_studio_concepts(db, s))


def concept_content(db: Session, concept_id: str, trace_id: str) -> StudioConceptContent:
    c = db.get(m.Concept, concept_id)
    if c is None:
        raise StudioNotFound(f"unknown concept {concept_id}")
    subject = get_subject(db, c.subject_id)
    concept = _studio_concepts(db, subject, only=concept_id)[0]
    mis = db.scalars(select(m.Misconception).where(m.Misconception.concept_id == concept_id)
                     .order_by(m.Misconception.id)).all()
    mdesc = {x.id: x.description for x in mis}
    qs = db.scalars(select(m.Question).where(m.Question.concept_id == concept_id)
                    .options(selectinload(m.Question.options)).order_by(m.Question.id)).all()
    cards = db.scalars(select(m.Flashcard).where(m.Flashcard.concept_id == concept_id)
                       .order_by(m.Flashcard.position, m.Flashcard.created_at)).all()
    return StudioConceptContent(
        trace_id=trace_id, concept=concept,
        misconceptions=[StudioMisconception(id=x.id, description=x.description, correct_belief=x.correct_belief)
                        for x in mis],
        questions=[
            StudioQuestion(
                id=q.id, concept_id=q.concept_id, bloom_level=q.bloom_level, stem=q.stem,  # type: ignore[arg-type]
                explanation=q.explanation, difficulty_b=q.difficulty_b, status=q.status,
                options=[StudioOption(id=o.id, text=o.text, is_correct=o.is_correct, misconception_id=o.misconception_id,
                                      misconception=mdesc.get(o.misconception_id or "")) for o in q.options],
                verifier_passed=(q.verifier_report or {}).get("pass"),
                verifier_issues=list((q.verifier_report or {}).get("issues", [])),
            )
            for q in qs
        ],
        flashcards=[StudioFlashcard(id=f.id, concept_id=f.concept_id, front=f.front, back=f.back, status=f.status,
                                    source=f.source) for f in cards],
    )
