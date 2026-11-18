"""Teach the bot — Feynman mode (PROJECT_CONTEXT §10.6).

`reply()` = curious, slightly confused classmate. `score()` = separate grading call vs key points.
`coverage()` = deterministic live "explanation completeness" meter. Scores only ever feed XP/badges.
"""

from __future__ import annotations

import re

from app.ai.llm_client import call
from app.core.graph import ContentGraph
from app.guardrails.input import detect_injection
from app.guardrails.output import STOP, content_words
from app.schemas.ai import TeachBotReply, TeachScore

_SYN = {
    "smaller": "less", "lower": "less", "lesser": "less", "bigger": "greater", "larger": "greater",
    "higher": "greater", "more": "greater", "values": "key", "value": "key", "keys": "key", "number": "key",
    "numbers": "key", "subtrees": "subtree", "children": "child", "kids": "child", "nodes": "node",
    "root": "node", "pointer": "reference", "pointers": "reference", "references": "reference", "link": "reference",
    "links": "reference", "address": "reference", "fifo": "first", "lifo": "last", "copies": "copy",
    "copied": "copy", "stops": "stop", "stopping": "stop", "ends": "stop", "terminate": "stop", "calls": "call",
    "calling": "call", "frames": "frame", "variables": "variable", "locals": "local", "collide": "collision",
    "collisions": "collision", "buckets": "bucket", "slots": "bucket", "slot": "bucket", "indexes": "index",
    "indices": "index", "constant": "o(1)", "everything": "entire", "whole": "entire", "all": "entire",
}
_WORD = re.compile(r"[a-z0-9()^+]+")
_GENERIC = {"must", "requires", "require", "says", "gives", "give", "means", "uses", "using", "every", "each",
            "only", "just", "thing", "things", "way", "known", "actually", "always", "never", "rather"}


def _stem(w: str) -> str:
    for suf in ("ing", "ed", "es", "s", "ly", "er"):
        if len(w) > 4 and w.endswith(suf):
            return w[: -len(suf)]
    return w


def _norm_words(text: str) -> set[str]:
    out = set()
    for w in _WORD.findall(text.lower()):
        w = _SYN.get(w, w)
        if w in STOP or w in _GENERIC or (len(w) < 3 and w not in {"o(1)", "n"}):
            continue
        out.add(_stem(w))
    return out


def point_covered(point: str, student_text: str, threshold: float = 0.6) -> bool:
    pw = _norm_words(point)
    if not pw:
        return False
    sw = _norm_words(student_text)
    prefixes = {w[:4] for w in sw if len(w) >= 4}
    hit = sum(1 for w in pw if w in sw or (len(w) >= 4 and w[:4] in prefixes))
    return hit / len(pw) >= threshold and (hit >= 2 or len(pw) == 1)


def coverage(key_points: list[str], student_turns: list[str]) -> tuple[list[str], list[str]]:
    text = " ".join(student_turns)
    covered = [p for p in key_points if point_covered(p, text)]
    missing = [p for p in key_points if p not in covered]
    return covered, missing


def on_topic(message: str, notes_md: str, concept_name: str) -> bool:
    words = content_words(message)
    if len(words) <= 2:
        return True  # short replies ("yes", "ok so...") are fine
    vocab = content_words(notes_md + " " + concept_name)
    stems = {w[:5] for w in vocab}
    hits = sum(1 for w in words if w in vocab or w[:5] in stems)
    return hits / len(words) >= 0.2


def fallback_reply(graph: ContentGraph, concept_id: str, transcript: list[dict], message: str) -> TeachBotReply:
    c = graph.concepts[concept_id]
    student_turns = [t["text"] for t in transcript if t["role"] == "student"] + [message]
    bot_turns = [t["text"] for t in transcript if t["role"] == "bot"]
    if detect_injection(message):
        return TeachBotReply(
            reply=f"Ha, nice try! I can't change scores or rules. I'm just a confused classmate. "
            f"So... how does {c.name.lower()} actually work?",
            on_topic=False,
        )
    if not on_topic(message, c.notes_md, c.name):
        return TeachBotReply(
            reply=f"Ooh, fun tangent! But my exam is on {c.name.lower()} and I'm lost. Can you get me back on track?",
            on_topic=False,
        )
    covered, missing = coverage(c.key_points, student_turns)
    mcs = [m for m in graph.misconceptions.values() if m.concept_id == concept_id]
    asked = " ".join(bot_turns)
    for mc in mcs:
        if mc.description[:30] not in asked:
            return TeachBotReply(
                reply=f"Okay, I think I follow... but my friend told me: \"{mc.description}\" Is that true? Why or why not?",
                on_topic=True,
            )
    if missing:
        point = missing[0]
        topic = " ".join(point.split()[:4])
        return TeachBotReply(reply=f"Hmm, wait. What about \"{topic}...\"? I don't get that part yet. Can you explain it with an example?", on_topic=True)
    return TeachBotReply(
        reply="Ohhh, I think I finally get it! Can you give me one tiny example, just so I'm sure?",
        on_topic=True,
    )


def reply(
    graph: ContentGraph, concept_id: str, transcript: list[dict], message: str, trace_id: str, student_id: str
) -> tuple[TeachBotReply, list[str], bool]:
    """Returns (reply, guardrail flags, fallback_used)."""
    c = graph.concepts[concept_id]
    covered, missing = coverage(
        c.key_points, [t["text"] for t in transcript if t["role"] == "student"] + [message]
    )
    res = call(
        feature="teach_bot", prompt_name="teach_bot",
        inputs={
            "concept": {"name": c.name, "key_points": c.key_points},
            "points_not_yet_covered": missing,
            "transcript": transcript[-8:],
            "message": message,
        },
        free_text_keys=("message", "transcript"),
        output_schema=TeachBotReply, model_tier="fast", trace_id=trace_id, student_id=student_id,
        fallback=lambda: fallback_reply(graph, concept_id, transcript, message),
        validator=lambda o: [] if len(o.reply.split()) <= 90 else ["reply_too_long"],
        use_cache=False,
    )
    out: TeachBotReply = res.output
    if res.blocked:
        out = TeachBotReply(reply=f"Let's keep it friendly and stick to {c.name.lower()}. How would you explain it?",
                            on_topic=False)
    return out, res.flags, res.fallback_used


def fallback_score(graph: ContentGraph, concept_id: str, transcript: list[dict]) -> TeachScore:
    c = graph.concepts[concept_id]
    turns = [t["text"] for t in transcript if t["role"] == "student"]
    covered, missing = coverage(c.key_points, turns)
    detected = []
    text = " ".join(turns).lower()
    for mc in graph.misconceptions.values():
        if mc.concept_id == concept_id and mc.description.lower().rstrip(".") in text:
            detected.append(mc.description)
    score = round(100 * len(covered) / max(1, len(c.key_points))) - 15 * len(detected)
    score = max(0, min(100, score))
    if missing:
        fb = f"Nice work covering {len(covered)} of {len(c.key_points)} key ideas. Next time, add: {missing[0]}."
    else:
        fb = "Excellent! You covered every key idea clearly."
    return TeachScore(score=score, covered_points=covered, missing_points=missing,
                      misconceptions_detected=detected, feedback=fb)


def score(graph: ContentGraph, concept_id: str, transcript: list[dict], trace_id: str, student_id: str) -> tuple[TeachScore, str]:
    c = graph.concepts[concept_id]
    key_points = set(c.key_points)

    def validate(o: TeachScore) -> list[str]:
        bad = [p for p in o.covered_points + o.missing_points if p not in key_points]
        return ["unknown_key_point"] if bad else []

    res = call(
        feature="teach_score", prompt_name="teach_score",
        inputs={"concept": c.name, "key_points": c.key_points, "transcript": transcript},
        free_text_keys=("transcript",),
        output_schema=TeachScore, model_tier="fast", trace_id=trace_id, student_id=student_id,
        fallback=lambda: fallback_score(graph, concept_id, transcript), validator=validate,
    )
    return res.output, "fallback" if res.fallback_used else "llm"
