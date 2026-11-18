"""Content generators (PROJECT_CONTEXT §10.5): micro-lesson, analogy, socratic, boss flavour, hints.

Each generator calls llm_client with a deterministic, notes-grounded fallback so offline mode still
produces good content.
"""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor

from app.ai.llm_client import call
from app.core.graph import ContentGraph
from app.guardrails.output import content_words, fix_tone, grounding_ratio, leaks_answer
from app.schemas.ai import AnalogyOut, BossFlavor, HintContent, LessonBody, SocraticOut

MAX_LESSON_WORDS = 200


# ------------------------------------------------------------------ notes helpers
def note_paragraphs(notes_md: str) -> tuple[list[str], str]:
    """Split notes into body paragraphs and the Example paragraph."""
    paras = [p.strip() for p in re.split(r"\n\s*\n", notes_md) if p.strip() and not p.strip().startswith("#")]
    example = ""
    body = []
    for p in paras:
        if p.startswith("**Example"):
            example = re.sub(r"^\*\*Example\.?\*\*\s*", "", p)
        else:
            body.append(p)
    return body, example


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+(?=[A-Z`(])", text) if s.strip()]


def _relevance(par: str, query: str) -> float:
    q = content_words(query)
    if not q:
        return 0.0
    p = content_words(par)
    pstems = {w[:5] for w in p}
    return sum(1 for w in q if w in p or w[:5] in pstems) / len(q)


def _trim_words(text: str, limit: int) -> str:
    out, n = [], 0
    for s in _sentences(text):
        w = len(s.split())
        if n + w > limit and out:
            break
        out.append(s)
        n += w
    return " ".join(out)


# ------------------------------------------------------------------ micro-lesson
def fallback_lesson(graph: ContentGraph, concept_id: str, misconception_id: str | None) -> LessonBody:
    c = graph.concepts[concept_id]
    body, example = note_paragraphs(c.notes_md)
    mc = graph.misconceptions.get(misconception_id or "")
    query = " ".join([mc.description, mc.correct_belief] if mc else c.key_points)
    ranked = sorted(body, key=lambda p: _relevance(p, query), reverse=True)
    chosen = ranked[:2] if ranked else []
    parts: list[str] = []
    budget = MAX_LESSON_WORDS
    if mc:
        intro = f"**A common belief:** \"{mc.description}\"\n\n**What's actually true:** {mc.correct_belief}"
        parts.append(intro)
        budget -= len(intro.split())
    for p in chosen:
        if budget <= 25:
            break
        t = _trim_words(p, budget)
        parts.append(t)
        budget -= len(t.split())
    citations = [_sentences(p)[0] for p in chosen if _sentences(p)]
    return LessonBody(lesson_md="\n\n".join(parts), worked_example=example, citations=citations[:3])


def fallback_analogy(graph: ContentGraph, concept_id: str, misconception_id: str | None) -> AnalogyOut:
    mc = graph.misconceptions.get(misconception_id or "")
    if mc and mc.analogy:
        return AnalogyOut(analogy=mc.analogy)
    for m in graph.misconceptions.values():
        if m.concept_id == concept_id and m.analogy:
            return AnalogyOut(analogy=m.analogy)
    return AnalogyOut(analogy=f"Think of {graph.name(concept_id)} as a set of rules you can check by hand on a tiny example.")


def fallback_socratic(graph: ContentGraph, concept_id: str, misconception_id: str | None) -> SocraticOut:
    mc = graph.misconceptions.get(misconception_id or "")
    if mc and mc.socratic:
        return SocraticOut(questions=mc.socratic[:2])
    for m in graph.misconceptions.values():
        if m.concept_id == concept_id and m.socratic:
            return SocraticOut(questions=m.socratic[:2])
    return SocraticOut(questions=[f"Can you test your idea about {graph.name(concept_id)} on a three-element example?"])


def lesson_validator(notes: str, do_not_reveal: list[str]):
    def check(out: LessonBody) -> list[str]:
        issues = []
        if len(out.lesson_md.split()) > MAX_LESSON_WORDS + 30:
            issues.append("lesson_too_long")
        if grounding_ratio(out.lesson_md, notes) < 0.45:
            issues.append("grounding_failure")
        if leaks_answer(out.lesson_md + " " + out.worked_example, do_not_reveal):
            issues.append("answer_leakage")
        return issues

    return check


def micro_lesson(
    graph: ContentGraph,
    concept_id: str,
    misconception_id: str | None,
    do_not_reveal: list[str],
    trace_id: str,
    student_id: str | None,
) -> tuple[LessonBody, AnalogyOut, SocraticOut, str]:
    """Lesson + analogy + socratic prompts, generated in parallel. Returns (..., source)."""
    c = graph.concepts[concept_id]
    mc = graph.misconceptions.get(misconception_id or "")
    base = {
        "concept": {"id": c.id, "name": c.name, "key_points": c.key_points},
        "misconception": {"description": mc.description, "correct_belief": mc.correct_belief} if mc else None,
    }
    grounding_source = c.notes_md + "\n" + (mc.correct_belief + " " + mc.description if mc else "")

    def run_lesson():
        return call(
            feature="lesson", prompt_name="lesson",
            inputs={**base, "notes": c.notes_md, "do_not_reveal": do_not_reveal},
            output_schema=LessonBody, model_tier="smart", trace_id=trace_id, student_id=student_id,
            fallback=lambda: fallback_lesson(graph, concept_id, misconception_id),
            validator=lesson_validator(grounding_source, do_not_reveal),
        )

    def run_analogy():
        return call(
            feature="analogy", prompt_name="analogy", inputs={**base, "notes": c.notes_md},
            output_schema=AnalogyOut, model_tier="fast", trace_id=trace_id, student_id=student_id,
            fallback=lambda: fallback_analogy(graph, concept_id, misconception_id),
        )

    def run_socratic():
        return call(
            feature="socratic", prompt_name="socratic", inputs={**base, "notes": c.notes_md},
            output_schema=SocraticOut, model_tier="fast", trace_id=trace_id, student_id=student_id,
            fallback=lambda: fallback_socratic(graph, concept_id, misconception_id),
            validator=lambda o: [] if 1 <= len(o.questions) <= 3 else ["socratic_count"],
        )

    with ThreadPoolExecutor(max_workers=3) as ex:
        f1, f2, f3 = ex.submit(run_lesson), ex.submit(run_analogy), ex.submit(run_socratic)
        r1, r2, r3 = f1.result(), f2.result(), f3.result()
    lesson: LessonBody = r1.output
    lesson.lesson_md, _ = fix_tone(lesson.lesson_md)
    source = "fallback" if r1.fallback_used else ("cache" if r1.cache_hit else "llm")
    return lesson, r2.output, r3.output, source


# ------------------------------------------------------------------ boss flavour
_BOSS_NAMES = {
    "recursion_base": "The Infinite Echo",
    "call_stack": "The Frame Thief",
    "bst_property": "The Shallow Sorter",
    "bst_ops": "The Lost Searcher",
    "bst_delete": "The Orphan Maker",
    "traversals": "The Scrambler",
    "queues": "The Line Cutter",
    "stacks": "The Bottom Feeder",
    "hash_tables": "The Bucket Hoarder",
    "hashing": "The Fickle Hasher",
    "heaps": "The False Sorter",
    "big_o": "The Constant Bloater",
    "arrays": "The Off-By-One",
    "linked_lists": "The Broken Chain",
    "memory_basics": "The Copycat",
}


def boss_flavor(graph: ContentGraph, misconception_ids: list[str], trace_id: str, student_id: str) -> BossFlavor:
    mcs = [graph.misconceptions[m] for m in misconception_ids if m in graph.misconceptions]

    def fallback() -> BossFlavor:
        if not mcs:
            return BossFlavor(name="The Root Golem", taunt="Your weakest roots are mine. Prove they're strong!")
        first = mcs[0]
        name = _BOSS_NAMES.get(first.concept_id, "The Root Golem")
        return BossFlavor(name=name, taunt=f"\"{first.description}\" ...or so I've convinced you. Prove me wrong!")

    res = call(
        feature="boss", prompt_name="boss_gen",
        inputs={"misconceptions": [m.description for m in mcs]},
        output_schema=BossFlavor, model_tier="fast", trace_id=trace_id, student_id=student_id, fallback=fallback,
        validator=lambda o: [] if len(o.name) <= 40 and len(o.taunt) <= 200 else ["boss_too_long"],
    )
    return res.output


# ------------------------------------------------------------------ hints (stretch)
def hint(graph: ContentGraph, question_id: str, level: int, trace_id: str, student_id: str | None) -> str:
    q = graph.questions[question_id]
    c = graph.concepts[q.concept_id]
    correct = q.correct_option
    wrong = [o for o in q.options if not o.is_correct]

    def fallback() -> HintContent:
        if level <= 1:
            kp = max(c.key_points, key=lambda k: _relevance(k, q.stem)) if c.key_points else c.description
            return HintContent(hint=f"Think about this key idea: {kp}.")
        mc = graph.misconceptions.get(wrong[0].misconception_id or "") if wrong else None
        if level == 2 and mc:
            return HintContent(hint=f"Watch out for a tempting idea: \"{mc.description}\" It isn't true.")
        if wrong:
            return HintContent(hint=f"You can rule out: \"{wrong[-1].text}\".")
        return HintContent(hint="Try the idea on a tiny example by hand.")

    res = call(
        feature="hint", prompt_name="hint",
        inputs={"stem": q.stem, "level": level, "notes": c.notes_md, "options": [o.text for o in q.options]},
        output_schema=HintContent, model_tier="fast", trace_id=trace_id, student_id=student_id, fallback=fallback,
        validator=lambda o: ["answer_leakage"] if correct and leaks_answer(o.hint, [correct.text]) else [],
    )
    return res.output.hint
