"""Tier-based LLM gateway — ordered provider chains, capability filter, budget guard."""

from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from backend.config import get_settings
from backend.core.llm_budget import heavy_budget_allows, record_heavy_cloud_call
from backend.core.llm_capabilities import (
    LlmRequirements,
    capability_filter,
    entry_is_configured,
    entry_to_options,
    filter_configured_entries,
    is_cloud_provider,
)
from backend.core.llm_job_context import get_job_context
from backend.core.llm_routes import get_active_route_profile, get_chain_for_tier
from backend.core.llm_tiers import ChainEntry, chain_to_dicts
from backend.core.ollama_client import (
    LlmOptions,
    LlmTransportError,
    TransportResult,
    _has_llm_override,
    _normalize_provider,
    _settings,
    llm_reachable,
    ollama_generate_transport,
    resolve_llm_options,
)

log = logging.getLogger(__name__)

_LAST_CALLS: deque[dict[str, Any]] = deque(maxlen=20)

TASK_DEFAULTS: dict[str, tuple[str, LlmRequirements]] = {
    "quiz_gen": ("medium", LlmRequirements(needs_json_schema=True)),
    "concept_extract": ("light", LlmRequirements(needs_json_schema=True)),
    "gap_analysis": ("medium", LlmRequirements(needs_json_schema=True)),
    "drill_gen": ("medium", LlmRequirements(needs_json_schema=True)),
    "notes_chunk": ("medium", LlmRequirements(needs_system_prompt=True)),
    "notes_refine": ("medium", LlmRequirements(needs_system_prompt=True)),
    "notes_job": ("medium", LlmRequirements(needs_system_prompt=True)),
    "corpus_grounded": ("heavy", LlmRequirements(needs_system_prompt=True)),
    "coach": ("light", LlmRequirements(needs_system_prompt=True)),
    "classify": ("light", LlmRequirements(needs_system_prompt=True)),
    "block_regen": ("medium", LlmRequirements(needs_system_prompt=True)),
    "note_enrich": ("medium", LlmRequirements(needs_system_prompt=True)),
    "folder_summarize": ("medium", LlmRequirements(needs_system_prompt=True)),
    "kg_anchor": ("light", LlmRequirements(needs_json_schema=True)),
    "memory_extract": ("light", LlmRequirements(needs_json_schema=True)),
    "vocab_enrich": ("medium", LlmRequirements(needs_json_schema=True)),
    "project_agent": ("medium", LlmRequirements(needs_system_prompt=True)),
    "hub_router": ("light", LlmRequirements(needs_system_prompt=True)),
    "corpus_qa": ("medium", LlmRequirements(needs_system_prompt=True)),
    "web_search": ("light", LlmRequirements()),
    "math_hint": ("light", LlmRequirements()),
    "planner_propose": ("medium", LlmRequirements(needs_json_schema=True)),
    "daily_review": ("heavy", LlmRequirements()),
    "voice_agent": ("medium", LlmRequirements(needs_system_prompt=True)),
    "generic": ("medium", LlmRequirements()),
}

FALLBACK_ERRORS = {
    LlmTransportError.RATE_LIMIT,
    LlmTransportError.AUTH,
    LlmTransportError.QUOTA,
    LlmTransportError.TIMEOUT,
    LlmTransportError.EMPTY,
    LlmTransportError.CONNECTION,
    LlmTransportError.SERVER,
    LlmTransportError.UNKNOWN,
}

# Short skip after 429/5xx — retry soon.
_RATE_LIMIT_COOLDOWN_SEC = 180.0
# Long skip after billing/auth death — do not re-hit OpenRouter every coach message.
_BILLING_COOLDOWN_SEC = 6 * 3600.0
_cloud_cooldown_until: dict[str, float] = {}
_cloud_cooldown_reason: dict[str, str] = {}


def clear_cloud_cooldowns() -> None:
    """Test helper / admin reset."""
    _cloud_cooldown_until.clear()
    _cloud_cooldown_reason.clear()


def _cooldown_seconds_for(reason: str) -> float:
    if reason in ("quota", "auth", "billing"):
        return _BILLING_COOLDOWN_SEC
    return _RATE_LIMIT_COOLDOWN_SEC


def _mark_cloud_cooldown(provider: str, *, reason: str = "rate_limit") -> None:
    name = _normalize_provider(provider)
    if not is_cloud_provider(name):
        return
    sec = _cooldown_seconds_for(reason)
    until = time.monotonic() + sec
    prev = _cloud_cooldown_until.get(name, 0.0)
    # Never shorten an existing longer cooldown (e.g. quota already active).
    if until <= prev:
        return
    _cloud_cooldown_until[name] = until
    _cloud_cooldown_reason[name] = reason
    log.warning(
        "LLM auto-skip %s for ~%dm after %s — next providers will be used without retrying it",
        name,
        int(sec // 60) or 1,
        reason,
    )


def _filter_cloud_cooldown(chain: list[ChainEntry]) -> list[ChainEntry]:
    now = time.monotonic()
    skipped: list[str] = []
    out: list[ChainEntry] = []
    for e in chain:
        name = _normalize_provider(e.provider)
        if is_cloud_provider(e.provider) and now < _cloud_cooldown_until.get(name, 0.0):
            if name not in skipped:
                skipped.append(name)
            continue
        out.append(e)
    if skipped:
        detail = ", ".join(
            f"{n}({_cloud_cooldown_reason.get(n, 'cooldown')})" for n in skipped
        )
        log.info("LLM chain auto-skipped cooled providers: %s", detail)
    return out


def _cooldown_reason_for_error(error: LlmTransportError) -> str | None:
    if error == LlmTransportError.QUOTA:
        return "quota"
    if error == LlmTransportError.AUTH:
        return "auth"
    if error in (LlmTransportError.RATE_LIMIT, LlmTransportError.SERVER):
        return "rate_limit"
    return None


@dataclass
class LlmResult:
    text: str | None
    tier: str
    provider: str | None = None
    model: str | None = None
    route_profile: str | None = None
    fallback_used: bool = False
    latency_ms: int = 0
    error: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    generation_id: str | None = None
    upstream_provider: str | None = None
    estimated_cost: float | None = None
    attempts: list[dict[str, Any]] | None = None


def _record_call(meta: dict[str, Any]) -> None:
    _LAST_CALLS.append(meta)
    log.info(
        "llm_call task=%s tier=%s provider=%s model=%s fallback=%s latency_ms=%s error=%s",
        meta.get("task"),
        meta.get("tier"),
        meta.get("provider"),
        meta.get("model"),
        meta.get("fallback"),
        meta.get("latency_ms"),
        meta.get("error"),
    )
    for attempt in reversed(meta.get("attempts") or []):
        or_meta = attempt.get("openrouter_metadata")
        if or_meta:
            log.info(
                "OpenRouter metadata strategy=%s attempt=%s details=%s",
                or_meta.get("strategy"),
                or_meta.get("attempt"),
                or_meta,
            )
            break
        if attempt.get("zero_completion_insurance"):
            log.info(
                "OpenRouter zero-completion (not billed) finish_reason=%s model=%s",
                attempt.get("finish_reason"),
                attempt.get("resolved_model"),
            )
            break


_PREVIEW_CHARS = 300


def _preview_text(text: str | None, limit: int = _PREVIEW_CHARS) -> str | None:
    if not text or not str(text).strip():
        return None
    collapsed = " ".join(str(text).split())
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[:limit] + "…"


def _call_record(
    *,
    prompt: str,
    task: str,
    tier: str,
    route_profile: str | None,
    provider: str | None,
    model: str | None,
    fallback: bool,
    latency_ms: int,
    error: str | None,
    attempts: list[dict[str, Any]] | None = None,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    total_tokens: int | None = None,
    generation_id: str | None = None,
    upstream_provider: str | None = None,
    estimated_cost: float | None = None,
    response_preview: str | None = None,
) -> dict[str, Any]:
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "task": task,
        "tier": tier,
        "route_profile": route_profile,
        "provider": provider,
        "model": model,
        "fallback": fallback,
        "latency_ms": latency_ms,
        "error": error,
        "prompt_preview": _preview_text(prompt),
        "response_preview": _preview_text(response_preview),
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "generation_id": generation_id,
        "upstream_provider": upstream_provider,
        "estimated_cost": estimated_cost,
        "attempts": attempts or [],
    }


def get_last_calls() -> list[dict[str, Any]]:
    return list(_LAST_CALLS)


def _resolve_tier(task: str, tier: str | None) -> str:
    job = get_job_context()
    if job and job.locked and job.tier:
        return job.tier.strip().lower()
    if tier:
        return tier.strip().lower()
    default_tier, _ = TASK_DEFAULTS.get(task, TASK_DEFAULTS["generic"])
    return get_settings().llm_default_tier.strip().lower() or default_tier


def _resolve_requirements(task: str, requirements: LlmRequirements | None) -> LlmRequirements:
    if requirements is not None:
        return requirements
    _, req = TASK_DEFAULTS.get(task, TASK_DEFAULTS["generic"])
    return req


def _custom_chain_from_llm(llm: LlmOptions) -> list[ChainEntry]:
    opts = resolve_llm_options(llm)
    return [
        ChainEntry(
            provider=opts.provider or "lmstudio",
            model=opts.model,
            base_url=opts.base_url,
            api_key=opts.api_key,
        )
    ]


def _context_limit(entry: ChainEntry, requirements: LlmRequirements) -> int:
    if entry.max_context_chars:
        return entry.max_context_chars
    if requirements.max_prompt_chars:
        return requirements.max_prompt_chars
    return get_settings().llm_context_char_limit


def _should_fallback(error: LlmTransportError) -> bool:
    return error in FALLBACK_ERRORS


def _try_openrouter_batch(
    prompt: str,
    entries: list[ChainEntry],
    *,
    requirements: LlmRequirements,
    timeout: float,
    json_schema: dict | None,
    system_prompt: str | None,
    tier: str,
    task: str,
) -> TransportResult:
    from backend.core.ollama_client import openrouter_batch_generate

    for entry in entries:
        limit = _context_limit(entry, requirements)
        if len(prompt) > limit:
            return TransportResult(error=LlmTransportError.CONTEXT_TOO_LONG)
    return openrouter_batch_generate(
        prompt,
        entries=entries,
        timeout=timeout,
        system_prompt=system_prompt,
        json_schema=json_schema,
        tier=tier,
        task=task,
        requirements=requirements,
    )


def _segment_success_result(
    *,
    transport: TransportResult,
    entry: ChainEntry,
    resolved_tier: str,
    active_route_profile: str,
    fallback_used: bool,
    started: float,
    attempts: list[dict],
) -> LlmResult:
    model = transport.resolved_model or entry.model
    latency = int((time.perf_counter() - started) * 1000)
    return LlmResult(
        text=transport.text,
        tier=resolved_tier,
        provider=entry.provider,
        model=model,
        route_profile=active_route_profile,
        fallback_used=fallback_used,
        latency_ms=latency,
        error=None,
        prompt_tokens=transport.prompt_tokens,
        completion_tokens=transport.completion_tokens,
        total_tokens=transport.total_tokens,
        generation_id=transport.generation_id,
        upstream_provider=transport.upstream_provider,
        estimated_cost=transport.estimated_cost,
        attempts=attempts,
    )


def _try_entry(
    prompt: str,
    entry: ChainEntry,
    *,
    requirements: LlmRequirements,
    timeout: float,
    json_schema: dict | None,
    system_prompt: str | None,
    keep_alive: int | None = None,
) -> TransportResult:
    limit = _context_limit(entry, requirements)
    if len(prompt) > limit:
        return TransportResult(error=LlmTransportError.CONTEXT_TOO_LONG)

    opts = entry_to_options(entry)
    result = ollama_generate_transport(
        prompt,
        opts=opts,
        timeout=timeout,
        json_schema=json_schema,
        system_prompt=system_prompt,
        keep_alive=keep_alive,
    )
    if result.error == LlmTransportError.EMPTY and result.text:
        return TransportResult(text=result.text, latency_ms=result.latency_ms)
    # Cloud providers: fail fast on rate limit / server errors — retry hammers the API.
    if result.error in (LlmTransportError.RATE_LIMIT, LlmTransportError.SERVER, LlmTransportError.QUOTA):
        if is_cloud_provider(entry.provider):
            return result
    if result.error in (LlmTransportError.RATE_LIMIT, LlmTransportError.EMPTY):
        retry = ollama_generate_transport(
            prompt,
            opts=opts,
            timeout=timeout,
            json_schema=json_schema,
            system_prompt=system_prompt,
            keep_alive=keep_alive,
        )
        if retry.text and retry.error == LlmTransportError.NONE:
            return retry
        return result
    return result


def llm_complete(
    prompt: str,
    *,
    task: str = "generic",
    tier: str | None = None,
    requirements: LlmRequirements | None = None,
    system_prompt: str | None = None,
    json_schema: dict | None = None,
    timeout: float = 120.0,
    llm: LlmOptions | None = None,
    model: str | None = None,
    confirm_heavy_budget: bool = False,
    route_profile: str | None = None,
) -> LlmResult:
    started = time.perf_counter()
    req = _resolve_requirements(task, requirements)
    resolved_tier = _resolve_tier(task, tier)
    active_route_profile = get_active_route_profile(route_profile)
    attempts: list[dict[str, Any]] = []

    if not _settings().ollama_enabled and not _has_llm_override(llm):
        result = LlmResult(
            text=None,
            tier=resolved_tier,
            route_profile=active_route_profile,
            error="all_failed",
            latency_ms=int((time.perf_counter() - started) * 1000),
            attempts=attempts,
        )
        _record_call(
            _call_record(
                prompt=prompt,
                task=task,
                tier=resolved_tier,
                route_profile=active_route_profile,
                provider=None,
                model=None,
                fallback=False,
                latency_ms=result.latency_ms,
                error=result.error,
                attempts=attempts,
            )
        )
        return result

    if resolved_tier == "heavy" and not heavy_budget_allows(confirm=confirm_heavy_budget):
        result = LlmResult(
            text=None,
            tier=resolved_tier,
            route_profile=active_route_profile,
            error="budget_exceeded",
            latency_ms=int((time.perf_counter() - started) * 1000),
            attempts=attempts,
        )
        _record_call(
            _call_record(
                prompt=prompt,
                task=task,
                tier=resolved_tier,
                route_profile=active_route_profile,
                provider=None,
                model=None,
                fallback=False,
                latency_ms=result.latency_ms,
                error=result.error,
                attempts=attempts,
            )
        )
        return result

    if llm and _has_llm_override(llm):
        chain = _custom_chain_from_llm(llm)
        resolved_tier = "custom"
    else:
        chain = get_chain_for_tier(resolved_tier, route_profile=active_route_profile)

    filtered = capability_filter(chain, req)
    if not filtered:
        filtered = chain
    filtered = filter_configured_entries(filtered)
    filtered = _filter_cloud_cooldown(filtered)

    from backend.core.openrouter_routing import iter_chain_segments, openrouter_models_from_entries

    fallback_used = False
    last_error = LlmTransportError.UNKNOWN
    segment_idx = 0
    # Voice sessions must not pin Ollama weights after the turn (VRAM / gaming).
    ollama_keep_alive: int | None = 0 if task == "voice_agent" else None

    for kind, segment in iter_chain_segments(filtered):
        if kind == "openrouter_batch":
            entries = segment
            primary = entries[0]
            transport = _try_openrouter_batch(
                prompt,
                entries,
                requirements=req,
                timeout=timeout,
                json_schema=json_schema,
                system_prompt=system_prompt,
                tier=resolved_tier,
                task=task,
            )
            entry = primary
            attempt_model = ",".join(openrouter_models_from_entries(entries))
            attempt_provider = "openrouter"
        else:
            entry = segment
            transport = _try_entry(
                prompt,
                entry,
                requirements=req,
                timeout=timeout,
                json_schema=json_schema,
                system_prompt=system_prompt,
                keep_alive=ollama_keep_alive,
            )
            attempt_model = entry.model
            attempt_provider = entry.provider

        last_error = transport.error
        attempts.append(
            {
                "provider": attempt_provider,
                "model": attempt_model,
                "resolved_model": transport.resolved_model,
                "base_url": entry.base_url,
                "error": transport.error.value,
                "latency_ms": transport.latency_ms,
                "finish_reason": transport.finish_reason,
                "openrouter_metadata": transport.openrouter_metadata,
                "zero_completion_insurance": transport.zero_completion_insurance,
            }
        )

        if transport.error == LlmTransportError.CONTEXT_TOO_LONG:
            latency = int((time.perf_counter() - started) * 1000)
            result = LlmResult(
                text=None,
                tier=resolved_tier,
                provider=entry.provider,
                model=transport.resolved_model or entry.model,
                route_profile=active_route_profile,
                fallback_used=fallback_used,
                latency_ms=latency,
                error="context_too_long",
                attempts=attempts,
            )
            _record_call(
                _call_record(
                    prompt=prompt,
                    task=task,
                    tier=resolved_tier,
                    route_profile=active_route_profile,
                    provider=entry.provider,
                    model=entry.model,
                    fallback=fallback_used,
                    latency_ms=latency,
                    error=result.error,
                    attempts=attempts,
                )
            )
            return result

        if transport.text and transport.error == LlmTransportError.NONE:
            if segment_idx > 0:
                log.info(
                    "LLM fallback succeeded: %s:%s (tier=%s task=%s)",
                    entry.provider,
                    transport.resolved_model or entry.model,
                    resolved_tier,
                    task,
                )
            if resolved_tier == "heavy" and is_cloud_provider(entry.provider) and segment_idx == 0:
                record_heavy_cloud_call()
            result = _segment_success_result(
                transport=transport,
                entry=entry,
                resolved_tier=resolved_tier,
                active_route_profile=active_route_profile,
                fallback_used=segment_idx > 0,
                started=started,
                attempts=attempts,
            )
            _record_call(
                _call_record(
                    prompt=prompt,
                    task=task,
                    tier=resolved_tier,
                    route_profile=active_route_profile,
                    provider=result.provider,
                    model=result.model,
                    fallback=segment_idx > 0,
                    latency_ms=result.latency_ms,
                    error="none",
                    attempts=attempts,
                    prompt_tokens=transport.prompt_tokens,
                    completion_tokens=transport.completion_tokens,
                    total_tokens=transport.total_tokens,
                    generation_id=transport.generation_id,
                    upstream_provider=transport.upstream_provider,
                    estimated_cost=transport.estimated_cost,
                    response_preview=transport.text,
                )
            )
            return result

        if is_cloud_provider(entry.provider):
            cool_reason = _cooldown_reason_for_error(transport.error)
            if cool_reason:
                _mark_cloud_cooldown(entry.provider, reason=cool_reason)

        if not _should_fallback(transport.error):
            break
        segment_idx += 1

    latency = int((time.perf_counter() - started) * 1000)
    error_name = (
        "context_too_long"
        if last_error == LlmTransportError.CONTEXT_TOO_LONG
        else "all_failed"
    )
    result = LlmResult(
        text=None,
        tier=resolved_tier,
        provider=filtered[-1].provider if filtered else None,
        model=filtered[-1].model if filtered else None,
        route_profile=active_route_profile,
        fallback_used=fallback_used,
        latency_ms=latency,
        error=error_name,
        attempts=attempts,
    )
    _record_call(
        _call_record(
            prompt=prompt,
            task=task,
            tier=resolved_tier,
            route_profile=active_route_profile,
            provider=result.provider,
            model=result.model,
            fallback=fallback_used,
            latency_ms=latency,
            error=result.error,
            attempts=attempts,
        )
    )
    return result


def gateway_available(override: LlmOptions | None = None) -> str | None:
    if override and _has_llm_override(override):
        opts = resolve_llm_options(override)
        if llm_reachable(opts):
            return opts.base_url
        return (override.base_url or "").strip().rstrip("/") or None

    for tier_name in ("medium", "light", "heavy"):
        chain = filter_configured_entries(get_chain_for_tier(tier_name))
        for entry in chain:
            opts = entry_to_options(entry)
            if llm_reachable(opts):
                return opts.base_url

    if not _settings().ollama_enabled:
        return None
    opts = resolve_llm_options()
    return opts.base_url if llm_reachable(opts) else None


def gateway_chain_available(
    tier: str | None = None,
    *,
    task: str = "generic",
    requirements: LlmRequirements | None = None,
    llm: LlmOptions | None = None,
    route_profile: str | None = None,
) -> str | None:
    """True when at least one provider in the task's tier chain is reachable."""
    if llm and _has_llm_override(llm):
        opts = resolve_llm_options(llm)
        return opts.base_url if llm_reachable(opts) else None

    if not _settings().ollama_enabled:
        return None

    resolved_tier = _resolve_tier(task, tier)
    req = _resolve_requirements(task, requirements)
    chain = get_chain_for_tier(resolved_tier, route_profile=route_profile)
    filtered = capability_filter(chain, req) or chain
    filtered = filter_configured_entries(filtered)
    for entry in filtered:
        opts = entry_to_options(entry)
        if llm_reachable(opts):
            return opts.base_url
    return None


def gateway_chain_status(
    tier: str | None = None,
    *,
    task: str = "generic",
    requirements: LlmRequirements | None = None,
    route_profile: str | None = None,
) -> dict[str, Any]:
    """Diagnostic summary for error messages and the AI Control Center."""
    resolved_tier = _resolve_tier(task, tier)
    active_profile = get_active_route_profile(route_profile)
    req = _resolve_requirements(task, requirements)
    chain = get_chain_for_tier(resolved_tier, route_profile=route_profile)
    filtered = filter_configured_entries(capability_filter(chain, req) or chain)
    entries = []
    any_reachable = False
    for entry in filtered:
        opts = entry_to_options(entry)
        reachable = llm_reachable(opts)
        any_reachable = any_reachable or reachable
        entries.append(
            {
                "provider": entry.provider,
                "model": entry.model,
                "base_url": opts.base_url,
                "configured": entry_is_configured(entry),
                "reachable": reachable,
            }
        )
    return {
        "tier": resolved_tier,
        "route_profile": active_profile,
        "task": task,
        "reachable": any_reachable,
        "chain": entries,
    }


def require_gateway_chain(
    tier: str | None = None,
    *,
    task: str = "generic",
    llm: LlmOptions | None = None,
    route_profile: str | None = None,
) -> None:
    """Raise RuntimeError with actionable detail when no provider in the tier chain works."""
    if gateway_chain_available(
        tier,
        task=task,
        llm=llm,
        route_profile=route_profile,
    ):
        return
    status = gateway_chain_status(tier, task=task, route_profile=route_profile)
    if not status["chain"]:
        chain_desc = "no configured providers in chain"
    else:
        chain_desc = ", ".join(
            f"{e['provider']} ({'reachable' if e['reachable'] else 'unreachable'})"
            for e in status["chain"]
        )
    raise RuntimeError(
        f"No reachable LLM for task={status['task']} tier={status['tier']} "
        f"profile={status['route_profile']}. Checked: {chain_desc}. "
        "Fix: start LM Studio (server on port 1234), set LLM_ROUTE_PROFILE=local in .env, "
        "or add the API keys required by your active route profile."
    )


def get_gateway_config() -> dict[str, Any]:
    from backend.core.llm_budget import heavy_budget_status

    cfg = get_settings()
    tiers_meta: dict[str, Any] = {}
    chains = {name: get_chain_for_tier(name) for name in ("light", "medium", "heavy")}
    for name, chain in chains.items():
        reachable = False
        for entry in chain:
            if llm_reachable(entry_to_options(entry)):
                reachable = True
                break
        tier_info: dict[str, Any] = {
            "chain": chain_to_dicts(chain),
            "reachable": reachable,
        }
        if name == "heavy":
            tier_info["budget"] = heavy_budget_status()
        tiers_meta[name] = tier_info

    base = resolve_llm_options()
    return {
        "enabled": cfg.ollama_enabled,
        "default_tier": cfg.llm_default_tier or "medium",
        "route_profile": get_active_route_profile(),
        "provider": base.provider,
        "base_url": base.base_url,
        "model": base.model,
        "max_tokens": base.max_tokens,
        "tiers": tiers_meta,
        "last_call": _LAST_CALLS[-1] if _LAST_CALLS else None,
        "last_calls": get_last_calls(),
        "task_defaults": {task: tier for task, (tier, _req) in TASK_DEFAULTS.items()},
    }
