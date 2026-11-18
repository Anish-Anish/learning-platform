"""The ONLY way to call an LLM (CLAUDE.md rule 3, PROJECT_CONTEXT §10.1).

call():  input guardrails -> budget -> cache -> OpenAI structured output (timeout, token cap)
         -> schema validation (+ optional output validator) -> one retry -> fallback
         -> llm_calls row (tokens, latency, cost, schema_ok, retries, fallback, flags, cache_hit).
call_agent(): same contract for a bounded tool-calling loop (diagnosis agent); one llm_calls row per turn.

With no OPENAI_API_KEY / model env vars the client runs in *offline mode*: every call goes straight to
its deterministic fallback and is still logged, so the demo never shows an error.
"""

from __future__ import annotations

import base64
import hashlib
import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ValidationError

from app.ai import cache
from app.ai.prompts import load as load_prompt
from app.config import get_settings
from app.db import models as m
from app.guardrails import budget
from app.guardrails.input import check_document_text, check_free_text
from app.observability import writer
from app.observability.logging import get_logger
from app.observability.tracing import ensure_trace_id, export_span

flush_logs = writer.flush

log = get_logger(__name__)

_client: Any = None
_client_override: Any = None


def get_client() -> Any:
    """Lazily build the OpenAI client. Tests inject a fake via `set_client`."""
    global _client
    if _client_override is not None:
        return _client_override
    s = get_settings()
    if not s.llm_enabled:
        return None
    if _client is None:
        from openai import OpenAI

        _client = OpenAI(api_key=s.openai_api_key, timeout=s.llm_timeout_s, max_retries=0)
    return _client


def set_client(client: Any) -> None:
    global _client_override
    _client_override = client


def llm_mode() -> str:
    return "online" if (_client_override is not None or get_settings().llm_enabled) else "offline"


@dataclass
class LLMResult:
    output: Any
    fallback_used: bool = False
    cache_hit: bool = False
    flags: list[str] = field(default_factory=list)
    retries: int = 0
    latency_ms: int = 0
    prompt_version: str = ""
    blocked: bool = False


def _cost(tier: str, tin: int, tout: int) -> float:
    s = get_settings()
    if tier == "smart":
        return (tin * s.price_smart_in + tout * s.price_smart_out) / 1_000_000
    return (tin * s.price_fast_in + tout * s.price_fast_out) / 1_000_000


def _log_call(
    *,
    trace_id: str,
    student_id: str | None,
    feature: str,
    prompt_name: str,
    prompt_version: str,
    model: str,
    tier: str,
    tin: int,
    tout: int,
    latency_ms: int,
    schema_ok: bool,
    retries: int,
    fallback_used: bool,
    flags: list[str],
    cache_hit: bool,
    error: str | None = None,
) -> None:
    row = m.LLMCall(
        trace_id=trace_id,
        student_id=student_id,
        feature=feature,
        prompt_name=prompt_name,
        prompt_version=prompt_version,
        model=model,
        input_tokens=tin,
        output_tokens=tout,
        latency_ms=latency_ms,
        cost_usd=round(_cost(tier, tin, tout), 6),
        schema_ok=schema_ok,
        retries=retries,
        fallback_used=fallback_used,
        guardrail_flags=sorted(set(flags)),
        cache_hit=cache_hit,
        error=error,
    )
    writer.submit(lambda db: db.add(row))  # async: the caller may hold the SQLite write lock
    log.info(
        "llm_call",
        trace_id=trace_id,
        feature=feature,
        prompt=prompt_name,
        prompt_version=prompt_version,
        model=model,
        latency_ms=latency_ms,
        fallback=fallback_used,
        cache_hit=cache_hit,
        flags=sorted(set(flags)),
    )
    export_span(f"llm.{feature}", {"trace_id": trace_id, "model": model, "latency_ms": latency_ms})


def _guard_documents(safe: dict[str, Any], document_keys: tuple[str, ...], flags: list[str]) -> None:
    limit = get_settings().studio_chunk_chars + 2000
    for k in document_keys:
        v = safe.get(k)
        if isinstance(v, str):
            g = check_document_text(v, limit)
            flags.extend(g.flags)
            safe[k] = g.text
        elif isinstance(v, list):
            out = []
            for item in v:
                if isinstance(item, str):
                    g = check_document_text(item, limit)
                    flags.extend(g.flags)
                    out.append(g.text)
                elif isinstance(item, dict) and isinstance(item.get("text"), str):
                    g = check_document_text(item["text"], limit)
                    flags.extend(g.flags)
                    out.append({**item, "text": g.text})
                else:
                    out.append(item)
            safe[k] = out


def _guard_inputs(inputs: dict[str, Any], free_text_keys: tuple[str, ...]) -> tuple[dict[str, Any], list[str], bool]:
    flags: list[str] = []
    blocked = False
    safe = dict(inputs)
    for k in free_text_keys:
        v = safe.get(k)
        if isinstance(v, str):
            g = check_free_text(v)
            flags.extend(g.flags)
            blocked = blocked or g.blocked
            safe[k] = g.wrapped
        elif isinstance(v, list):  # transcripts: list of {role, text}
            out = []
            for turn in v:
                if isinstance(turn, dict) and turn.get("role") == "student":
                    g = check_free_text(str(turn.get("text", "")))
                    flags.extend(g.flags)
                    blocked = blocked or g.blocked
                    out.append({**turn, "text": g.wrapped})
                else:
                    out.append(turn)
            safe[k] = out
    return safe, flags, blocked


def _data_url(img: bytes) -> str:
    mime = "image/png" if img[:8] == b"\x89PNG\r\n\x1a\n" else "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(img).decode()}"


def _usage(resp: Any) -> tuple[int, int]:
    u = getattr(resp, "usage", None)
    if u is None:
        return 0, 0
    return int(getattr(u, "prompt_tokens", 0) or 0), int(getattr(u, "completion_tokens", 0) or 0)


def _parse_call(client: Any, **kwargs: Any) -> Any:
    completions = client.chat.completions
    if hasattr(completions, "parse"):
        return completions.parse(**kwargs)
    return client.beta.chat.completions.parse(**kwargs)  # older SDKs


def call(
    *,
    feature: str,
    prompt_name: str,
    inputs: dict[str, Any],
    output_schema: type[BaseModel],
    model_tier: str = "fast",
    trace_id: str | None = None,
    fallback: Callable[[], Any],
    student_id: str | None = None,
    free_text_keys: tuple[str, ...] = (),
    validator: Callable[[Any], list[str]] | None = None,
    use_cache: bool = True,
    max_tokens: int | None = None,
    document_keys: tuple[str, ...] = (),
    images: list[bytes] | None = None,
    image_detail: str = "auto",
    timeout_s: float | None = None,
) -> LLMResult:
    """`document_keys`: uploaded material, wrapped as data (rule 6). `images`: PNG/JPEG bytes for vision."""
    s = get_settings()
    trace_id = trace_id or ensure_trace_id()
    prompt = load_prompt(prompt_name)
    tier = "smart" if model_tier == "smart" else "fast"
    model = s.model_for(tier) or "offline"
    max_tokens = max_tokens or prompt.max_tokens
    timeout = timeout_s or s.llm_timeout_s
    images = images or []
    t0 = time.perf_counter()

    def finish_fallback(flags: list[str], retries: int = 0, schema_ok: bool = True, error: str | None = None,
                        tin: int = 0, tout: int = 0, blocked: bool = False) -> LLMResult:
        out = fallback()
        latency = int((time.perf_counter() - t0) * 1000)
        _log_call(trace_id=trace_id, student_id=student_id, feature=feature, prompt_name=prompt_name,
                  prompt_version=prompt.version, model=model, tier=tier, tin=tin, tout=tout, latency_ms=latency,
                  schema_ok=schema_ok, retries=retries, fallback_used=True, flags=flags, cache_hit=False, error=error)
        return LLMResult(output=out, fallback_used=True, flags=flags, retries=retries, latency_ms=latency,
                         prompt_version=prompt.version, blocked=blocked)

    safe_inputs, flags, blocked = _guard_inputs(inputs, free_text_keys)
    _guard_documents(safe_inputs, document_keys, flags)
    if blocked:
        return finish_fallback(flags, blocked=True)
    if budget.over_budget(student_id):
        return finish_fallback([*flags, "budget_exceeded"])

    key_inputs = {**safe_inputs, "_images": [hashlib.sha256(b).hexdigest() for b in images]} if images else safe_inputs
    key = cache.cache_key(prompt_name, prompt.version, model, key_inputs)
    if use_cache:
        hit = cache.get(key)
        if hit is not None:
            try:
                out = output_schema.model_validate(hit)
                latency = int((time.perf_counter() - t0) * 1000)
                _log_call(trace_id=trace_id, student_id=student_id, feature=feature, prompt_name=prompt_name,
                          prompt_version=prompt.version, model=model, tier=tier, tin=0, tout=0, latency_ms=latency,
                          schema_ok=True, retries=0, fallback_used=False, flags=flags, cache_hit=True)
                return LLMResult(output=out, cache_hit=True, flags=flags, latency_ms=latency,
                                 prompt_version=prompt.version)
            except ValidationError:
                pass

    client = get_client()
    if client is None:
        return finish_fallback([*flags, "offline"])

    system, user = prompt.render(safe_inputs)
    user_content: Any = user
    if images:
        user_content = [{"type": "text", "text": user}] + [
            {"type": "image_url", "image_url": {"url": _data_url(b), "detail": image_detail}} for b in images
        ]
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user_content}]
    tin_total = tout_total = 0
    last_error: str | None = None
    schema_ok = True
    for attempt in range(2):  # first try + one retry
        try:
            resp = _parse_call(
                client,
                model=model,
                messages=messages,
                response_format=output_schema,
                max_completion_tokens=max_tokens,
                timeout=timeout,
            )
            tin, tout = _usage(resp)
            tin_total += tin
            tout_total += tout
            msg = resp.choices[0].message
            parsed = getattr(msg, "parsed", None)
            if parsed is None:
                raw = getattr(msg, "content", None) or "{}"
                parsed = output_schema.model_validate_json(raw)
            elif not isinstance(parsed, output_schema):
                parsed = output_schema.model_validate(parsed)
            issues = validator(parsed) if validator else []
            if issues:
                flags.extend(issues)
                last_error = "; ".join(issues)
                schema_ok = True
                continue
            latency = int((time.perf_counter() - t0) * 1000)
            _log_call(trace_id=trace_id, student_id=student_id, feature=feature, prompt_name=prompt_name,
                      prompt_version=prompt.version, model=model, tier=tier, tin=tin_total, tout=tout_total,
                      latency_ms=latency, schema_ok=True, retries=attempt, fallback_used=False, flags=flags,
                      cache_hit=False)
            if use_cache:
                cache.put(key, feature, parsed.model_dump(by_alias=True))
            return LLMResult(output=parsed, flags=flags, retries=attempt, latency_ms=latency,
                             prompt_version=prompt.version)
        except ValidationError as exc:
            schema_ok = False
            last_error = f"schema: {exc.errors()[:2]}"
        except Exception as exc:  # timeouts, API errors, refusals
            last_error = f"{type(exc).__name__}: {exc}"[:300]
    return finish_fallback(flags, retries=1, schema_ok=schema_ok, error=last_error, tin=tin_total, tout=tout_total)


def call_agent(
    *,
    feature: str,
    prompt_name: str,
    inputs: dict[str, Any],
    tools: list[dict[str, Any]],
    tool_runner: Callable[[str, dict[str, Any]], str],
    output_schema: type[BaseModel],
    model_tier: str = "smart",
    trace_id: str | None = None,
    fallback: Callable[[], Any],
    student_id: str | None = None,
    max_steps: int = 6,
) -> LLMResult:
    """Bounded tool-calling loop ending in a structured output. Every turn is logged to llm_calls."""
    s = get_settings()
    trace_id = trace_id or ensure_trace_id()
    prompt = load_prompt(prompt_name)
    tier = "smart" if model_tier == "smart" else "fast"
    model = s.model_for(tier) or "offline"
    t0 = time.perf_counter()

    def finish_fallback(flags: list[str], error: str | None = None, retries: int = 0, schema_ok: bool = True) -> LLMResult:
        out = fallback()
        latency = int((time.perf_counter() - t0) * 1000)
        _log_call(trace_id=trace_id, student_id=student_id, feature=feature, prompt_name=prompt_name,
                  prompt_version=prompt.version, model=model, tier=tier, tin=0, tout=0, latency_ms=latency,
                  schema_ok=schema_ok, retries=retries, fallback_used=True, flags=flags, cache_hit=False, error=error)
        return LLMResult(output=out, fallback_used=True, flags=flags, latency_ms=latency, prompt_version=prompt.version)

    if budget.over_budget(student_id):
        return finish_fallback(["budget_exceeded"])
    client = get_client()
    if client is None:
        return finish_fallback(["offline"])

    strict_tools = [{**t, "function": {**t["function"], "strict": True}} for t in tools]
    system, user = prompt.render(inputs)
    messages: list[dict[str, Any]] = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    errors = 0
    last_error: str | None = None
    for step in range(max_steps):
        ts = time.perf_counter()
        try:
            resp = _parse_call(
                client,
                model=model,
                messages=messages,
                tools=strict_tools,
                response_format=output_schema,
                max_completion_tokens=prompt.max_tokens,
                timeout=s.llm_timeout_s,
            )
        except Exception as exc:
            errors += 1
            last_error = f"{type(exc).__name__}: {exc}"[:300]
            if errors > 1:
                return finish_fallback(["agent_error"], error=last_error, retries=errors - 1)
            continue
        tin, tout = _usage(resp)
        msg = resp.choices[0].message
        tool_calls = getattr(msg, "tool_calls", None) or []
        parsed = getattr(msg, "parsed", None)
        _log_call(trace_id=trace_id, student_id=student_id, feature=feature, prompt_name=prompt_name,
                  prompt_version=prompt.version, model=model, tier=tier, tin=tin, tout=tout,
                  latency_ms=int((time.perf_counter() - ts) * 1000), schema_ok=True, retries=0,
                  fallback_used=False, flags=[f"agent_step_{step}"], cache_hit=False)
        if tool_calls:
            messages.append(
                {
                    "role": "assistant",
                    "content": getattr(msg, "content", None),
                    "tool_calls": [
                        {"id": tc.id, "type": "function",
                         "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                        for tc in tool_calls
                    ],
                }
            )
            for tc in tool_calls:
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": tool_runner(tc.function.name, args)})
            continue
        try:
            if parsed is None:
                parsed = output_schema.model_validate_json(getattr(msg, "content", None) or "{}")
            elif not isinstance(parsed, output_schema):
                parsed = output_schema.model_validate(parsed)
            return LLMResult(output=parsed, latency_ms=int((time.perf_counter() - t0) * 1000),
                             prompt_version=prompt.version)
        except ValidationError as exc:
            errors += 1
            last_error = f"schema: {exc.errors()[:2]}"
            if errors > 1:
                return finish_fallback(["schema_failure"], error=last_error, retries=1, schema_ok=False)
            messages.append({"role": "user", "content": "Your last answer did not match the schema. Answer again."})
    return finish_fallback(["agent_max_steps"], error=last_error)
