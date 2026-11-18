"""Diagnosis agent (PROJECT_CONTEXT §10.4).

Tools: get_prerequisites, get_attempt_history, get_misconception, request_probe.
Strategy: start at the failed concept; use the selected option's misconception + history; descend
prerequisites to the deepest concept with failing evidence, or request a probe when there is none.

`deterministic_diagnosis` is both the offline fallback and the eval baseline. With an API key the
LLM agent runs a bounded tool-calling loop via `llm_client.call_agent`. Either way the output is only a
*proposal*; `core/diagnosis.py` validates and applies it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, Field, create_model

from app.core.graph import ContentGraph
from app.schemas.ai import DiagnosisProposal

FAILING_STATES = {"gap", "misconception"}


@dataclass
class AttemptFact:
    question_id: str
    concept_id: str
    correct: bool
    confidence: str
    option_text: str | None
    misconception_id: str | None
    seq: int


@dataclass
class ConceptFact:
    concept_id: str
    mastery: float
    state: str
    n_attempts: int
    active_misconceptions: list[str]


@dataclass
class DiagnosisContext:
    student_ref: str  # pseudonymous id only — never display names (rule 5)
    failed_concept_id: str
    origin_concept_id: str  # where the chain started (probe chains), used for the path
    trigger: AttemptFact
    history: list[AttemptFact]
    concepts: dict[str, ConceptFact]
    probed_concepts: list[str] = field(default_factory=list)
    probe_requests: list[str] = field(default_factory=list)


# ------------------------------------------------------------------ tools (pure)
def tool_get_prerequisites(ctx: DiagnosisContext, graph: ContentGraph, concept_id: str) -> list[dict[str, Any]]:
    if concept_id not in graph.concepts:
        return []
    out = []
    for p in graph.concepts[concept_id].prerequisites:
        f = ctx.concepts.get(p)
        out.append(
            {
                "concept_id": p,
                "name": graph.name(p),
                "mastery": round(f.mastery, 2) if f else 0.5,
                "state": f.state if f else "not_started",
                "n_attempts": f.n_attempts if f else 0,
                "already_probed": p in ctx.probed_concepts,
            }
        )
    return out


def tool_get_attempt_history(ctx: DiagnosisContext, graph: ContentGraph, concept_ids: list[str]) -> list[dict[str, Any]]:
    wanted = set(concept_ids)
    out = []
    for a in ctx.history:
        if a.concept_id in wanted or (a.misconception_id and a.misconception_id.split(".")[0] in wanted):
            out.append(
                {
                    "question_id": a.question_id,
                    "concept_id": a.concept_id,
                    "correct": a.correct,
                    "confidence": a.confidence,
                    "chosen_option": a.option_text,
                    "option_misconception_id": a.misconception_id,
                }
            )
    return out[-20:]


def tool_get_misconception(graph: ContentGraph, misconception_id: str) -> dict[str, Any]:
    mc = graph.misconceptions.get(misconception_id)
    if not mc:
        return {"error": "unknown misconception"}
    return {"id": mc.id, "concept_id": mc.concept_id, "description": mc.description, "correct_belief": mc.correct_belief}


def tool_request_probe(ctx: DiagnosisContext, graph: ContentGraph, concept_id: str) -> dict[str, Any]:
    if concept_id not in graph.concepts:
        return {"accepted": False, "reason": "unknown concept"}
    if concept_id in ctx.probed_concepts:
        return {"accepted": False, "reason": "already probed in this chain; decide with the evidence you have"}
    ctx.probe_requests.append(concept_id)
    return {"accepted": True, "note": "the adaptive engine will schedule a probe question (core decides)"}


def run_tool(ctx: DiagnosisContext, graph: ContentGraph, name: str, args: dict[str, Any]) -> Any:
    if name == "get_prerequisites":
        return tool_get_prerequisites(ctx, graph, args.get("concept_id", ""))
    if name == "get_attempt_history":
        return tool_get_attempt_history(ctx, graph, list(args.get("concept_ids") or []))
    if name == "get_misconception":
        return tool_get_misconception(graph, args.get("misconception_id", ""))
    if name == "request_probe":
        return tool_request_probe(ctx, graph, args.get("concept_id", ""))
    return {"error": f"unknown tool {name}"}


TOOL_SPECS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_prerequisites",
            "description": "Direct prerequisites of a concept with this student's mastery/state for each.",
            "parameters": {
                "type": "object",
                "properties": {"concept_id": {"type": "string"}},
                "required": ["concept_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_attempt_history",
            "description": "This student's recent attempts on the given concepts (and misconceptions belonging to them).",
            "parameters": {
                "type": "object",
                "properties": {"concept_ids": {"type": "array", "items": {"type": "string"}}},
                "required": ["concept_ids"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_misconception",
            "description": "Look up a misconception's description and the correct belief.",
            "parameters": {
                "type": "object",
                "properties": {"misconception_id": {"type": "string"}},
                "required": ["misconception_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "request_probe",
            "description": "Ask the adaptive engine to test a prerequisite before concluding (when evidence is missing).",
            "parameters": {
                "type": "object",
                "properties": {"concept_id": {"type": "string"}},
                "required": ["concept_id"],
                "additionalProperties": False,
            },
        },
    },
]


def proposal_schema(graph: ContentGraph) -> type[BaseModel]:
    """DiagnosisProposal with concept/misconception IDs constrained to enums of real IDs (§13.2)."""
    concept_ids = tuple(graph.concepts.keys())
    mis_ids = tuple(graph.misconceptions.keys())
    ConceptId = Literal[concept_ids]  # type: ignore[valid-type]
    MisId = Literal[mis_ids]  # type: ignore[valid-type]
    return create_model(
        "DiagnosisProposalStrict",
        root_concept_id=(ConceptId, ...),
        misconception_id=(MisId | None, ...),
        evidence=(list[str], ...),
        path=(list[ConceptId], ...),
        confidence=(float, Field(ge=0, le=1)),
        needs_probe=(bool, ...),
        probe_concept_id=(ConceptId | None, ...),
        student_message=(str, ...),
    )


# ------------------------------------------------------------------ deterministic baseline / fallback
def _evidence_line(a: AttemptFact, graph: ContentGraph) -> str:
    verdict = "Correct" if a.correct else "Wrong"
    chosen = f" (chose '{a.option_text}')" if a.option_text and not a.correct else ""
    return f"{verdict} on {a.question_id} [{graph.name(a.concept_id)}], {a.confidence}{chosen}"


def _failing(cf: ConceptFact | None, history: list[AttemptFact], cid: str) -> bool:
    if cf is None:
        return False
    if cf.active_misconceptions:
        return True
    wrong = [a for a in history if a.concept_id == cid and not a.correct]
    return cf.n_attempts > 0 and (cf.state in FAILING_STATES or len(wrong) >= 2)


def deterministic_diagnosis(ctx: DiagnosisContext, graph: ContentGraph) -> DiagnosisProposal:
    failed = ctx.failed_concept_id
    trig = ctx.trigger
    evidence: list[str] = [_evidence_line(trig, graph)]
    sel_mis = trig.misconception_id if trig.misconception_id in graph.misconceptions else None
    ancestors = graph.ancestors(failed)
    scope = [failed, *ancestors]

    # Start from the misconception's own concept when it is the failed concept or one of its prerequisites.
    start = failed
    if sel_mis:
        mc = graph.misconceptions[sel_mis]
        evidence.append(f"That option reflects the misconception: \"{mc.description}\"")
        if mc.concept_id in scope:
            start = mc.concept_id
        for a in ctx.history:
            if a.misconception_id == sel_mis and a.seq != trig.seq:
                evidence.append(_evidence_line(a, graph) + " — same misconception")

    # Descend: deepest prerequisite (of `start`) with failing evidence. A confidently chosen, tagged
    # misconception is the strongest evidence and already names its home concept (cross-concept tags carry
    # the root link, e.g. a BST option tagged recursion_base.m1), so we only descend for gap-type errors.
    confident_mis = bool(sel_mis and trig.confidence == "sure")
    root = start
    best_depth = -1
    for cid in [] if confident_mis else [start, *graph.ancestors(start)]:
        cf = ctx.concepts.get(cid)
        if cid != start and _failing(cf, ctx.history, cid):
            d = len(graph.prereq_path(start, cid))
            if d > best_depth:
                best_depth, root = d, cid
    if root != start:
        cf = ctx.concepts[root]
        evidence.append(
            f"Prerequisite {graph.name(root)} is also failing: state '{cf.state}', mastery {cf.mastery:.0%}"
        )
        for a in ctx.history:
            if a.concept_id == root and not a.correct:
                evidence.append(_evidence_line(a, graph))

    misconception_id: str | None = sel_mis
    if root != start:
        # A deeper root: use its own active misconception, else the one it was most often wrong with.
        rcf = ctx.concepts.get(root)
        if rcf and rcf.active_misconceptions:
            misconception_id = rcf.active_misconceptions[0]
        else:
            seen = [a.misconception_id for a in ctx.history if a.concept_id == root and not a.correct and a.misconception_id]
            misconception_id = max(set(seen), key=seen.count) if seen else None

    # Probe when the suspected root (a prerequisite) has no evidence of its own yet.
    needs_probe = False
    probe: str | None = None
    if root != failed and root not in ctx.probed_concepts:
        rcf = ctx.concepts.get(root)
        if rcf is None or rcf.n_attempts == 0:
            needs_probe, probe = True, root
    if root == failed and not sel_mis and trig.confidence == "guess":
        untested = [
            p for p in graph.concepts[failed].prerequisites
            if p not in ctx.probed_concepts and (ctx.concepts.get(p) is None or ctx.concepts[p].n_attempts == 0)
        ]
        if untested:
            needs_probe, probe = True, sorted(untested, key=lambda c: graph.concepts[c].depth, reverse=True)[0]
            root = probe
            evidence.append(f"No evidence yet on prerequisite {graph.name(probe)}, so we'll check it.")

    origin = ctx.origin_concept_id if ctx.origin_concept_id in graph.concepts else failed
    path = graph.prereq_path(origin, root) or graph.prereq_path(failed, root) or [failed, root]
    path = list(dict.fromkeys(path))

    if needs_probe:
        confidence = 0.55
    elif sel_mis and trig.confidence == "sure":
        confidence = 0.85 if len(evidence) > 2 else 0.75
    else:
        confidence = 0.6

    name = graph.name(root)
    if needs_probe:
        msg = (
            f"Your answer hints that the real snag might be in {name}. Let's check one quick question "
            "there before deciding."
        )
    elif misconception_id:
        mc = graph.misconceptions[misconception_id]
        msg = f"Here's the gap: the root is in {name}. The idea to fix: {mc.correct_belief}"
    else:
        msg = f"Here's the gap: {name} needs another look. A short lesson will get you back on track."

    return DiagnosisProposal(
        root_concept_id=root,
        misconception_id=misconception_id,
        evidence=evidence[:8],
        path=path,
        confidence=confidence,
        needs_probe=needs_probe,
        probe_concept_id=probe,
        student_message=msg,
    )


# ------------------------------------------------------------------ entry point
def diagnose(ctx: DiagnosisContext, graph: ContentGraph, trace_id: str) -> tuple[DiagnosisProposal, str]:
    """Run the LLM agent (if enabled) with the deterministic baseline as fallback."""
    from app.ai.llm_client import call_agent

    schema = proposal_schema(graph)
    baseline = deterministic_diagnosis(ctx, graph)

    def fallback() -> DiagnosisProposal:
        return baseline

    inputs = {
        "failed_concept": {"id": ctx.failed_concept_id, "name": graph.name(ctx.failed_concept_id)},
        "origin_concept_id": ctx.origin_concept_id,
        "trigger_attempt": {
            "question_id": ctx.trigger.question_id,
            "stem": graph.questions[ctx.trigger.question_id].stem if ctx.trigger.question_id in graph.questions else "",
            "chosen_option": ctx.trigger.option_text,
            "option_misconception_id": ctx.trigger.misconception_id,
            "confidence": ctx.trigger.confidence,
        },
        "already_probed": ctx.probed_concepts,
        "concept_ids": list(graph.concepts.keys()),
    }

    def tool_runner(name: str, args: dict[str, Any]) -> str:
        return json.dumps(run_tool(ctx, graph, name, args))

    result = call_agent(
        feature="diagnosis",
        prompt_name="diagnosis",
        inputs=inputs,
        tools=TOOL_SPECS,
        tool_runner=tool_runner,
        output_schema=schema,
        model_tier="smart",
        trace_id=trace_id,
        fallback=fallback,
        student_id=ctx.student_ref,
    )
    out = result.output
    if isinstance(out, BaseModel) and not isinstance(out, DiagnosisProposal):
        out = DiagnosisProposal.model_validate(out.model_dump())
    source = "fallback" if result.fallback_used else "llm"
    # If the agent asked for a probe through the tool but forgot to set needs_probe, honour the request.
    if source == "llm" and ctx.probe_requests and not out.needs_probe:
        out.needs_probe, out.probe_concept_id = True, ctx.probe_requests[-1]
    return out, source
