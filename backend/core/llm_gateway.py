"""Tier-based LLM gateway — ordered provider chains, capability filter, budget guard."""

from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass
from typing import Any

from backend.config import get_settings
from backend.core.llm_budget import heavy_budget_allows, record_heavy_cloud_call
from backend.core.llm_capabilities import (
    LlmRequirements,
    capability_filter,
    entry_to_options,
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
    "project_agent": ("medium", LlmRequirements(needs_system_prompt=True)),
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

# After 429/503 on Gemini, skip cloud for this many seconds (rest of notes job).
_CLOUD_COOLDOWN_SEC = 180.0
_cloud_cooldown_until: dict[str, float] = {}


def _mark_cloud_cooldown(provider: str) -> None:
    name = _normalize_provider(provider)
    if is_cloud_provider(name):
        _cloud_cooldown_until[name] = time.monotonic() + _CLOUD_COOLDOWN_SEC


def _filter_cloud_cooldown(chain: list[ChainEntry]) -> list[ChainEntry]:
    now = time.monotonic()
    skipped = [
        e for e in chain
        if is_cloud_provider(e.provider) and now < _cloud_cooldown_until.get(_normalize_provider(e.provider), 0)
    ]
    if skipped:
        log.info(
            "Cloud LLM busy (rate limit) — using local LM Studio for remaining chunks (%ds cooldown)",
            int(_CLOUD_COOLDOWN_SEC),
        )
    return [
        e for e in chain
        if not (is_cloud_provider(e.provider) and now < _cloud_cooldown_until.get(_normalize_provider(e.provider), 0))
    ]


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


def _try_entry(
    prompt: str,
    entry: ChainEntry,
    *,
    requirements: LlmRequirements,
    timeout: float,
    json_schema: dict | None,
    system_prompt: str | None,
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
            {
                "task": task,
                "tier": resolved_tier,
                "route_profile": active_route_profile,
                "provider": None,
                "model": None,
                "fallback": False,
                "latency_ms": result.latency_ms,
                "error": result.error,
                "attempts": attempts,
            }
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
            {
                "task": task,
                "tier": resolved_tier,
                "route_profile": active_route_profile,
                "provider": None,
                "model": None,
                "fallback": False,
                "latency_ms": result.latency_ms,
                "error": result.error,
                "attempts": attempts,
            }
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
    filtered = _filter_cloud_cooldown(filtered)

    fallback_used = False
    last_error = LlmTransportError.UNKNOWN

    for idx, entry in enumerate(filtered):
        transport = _try_entry(
            prompt,
            entry,
            requirements=req,
            timeout=timeout,
            json_schema=json_schema,
            system_prompt=system_prompt,
        )
        last_error = transport.error
        attempts.append(
            {
                "provider": entry.provider,
                "model": entry.model,
                "base_url": entry.base_url,
                "error": transport.error.value,
                "latency_ms": transport.latency_ms,
            }
        )

        if transport.error == LlmTransportError.CONTEXT_TOO_LONG:
            latency = int((time.perf_counter() - started) * 1000)
            result = LlmResult(
                text=None,
                tier=resolved_tier,
                provider=entry.provider,
                model=entry.model,
                route_profile=active_route_profile,
                fallback_used=fallback_used,
                latency_ms=latency,
                error="context_too_long",
                attempts=attempts,
            )
            _record_call(
                {
                    "task": task,
                    "tier": resolved_tier,
                    "route_profile": active_route_profile,
                    "provider": entry.provider,
                    "model": entry.model,
                    "fallback": fallback_used,
                    "latency_ms": latency,
                    "error": result.error,
                    "attempts": attempts,
                }
            )
            return result

        if transport.text and transport.error == LlmTransportError.NONE:
            if idx > 0:
                log.info(
                    "LLM fallback succeeded: %s:%s (tier=%s task=%s)",
                    entry.provider,
                    entry.model,
                    resolved_tier,
                    task,
                )
            if resolved_tier == "heavy" and is_cloud_provider(entry.provider) and idx == 0:
                record_heavy_cloud_call()
            latency = int((time.perf_counter() - started) * 1000)
            result = LlmResult(
                text=transport.text,
                tier=resolved_tier,
                provider=entry.provider,
                model=entry.model,
                route_profile=active_route_profile,
                fallback_used=idx > 0,
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
            _record_call(
                {
                    "task": task,
                    "tier": resolved_tier,
                    "route_profile": active_route_profile,
                    "provider": entry.provider,
                    "model": entry.model,
                    "fallback": idx > 0,
                    "latency_ms": latency,
                    "error": "none",
                    "prompt_tokens": transport.prompt_tokens,
                    "completion_tokens": transport.completion_tokens,
                    "total_tokens": transport.total_tokens,
                    "generation_id": transport.generation_id,
                    "upstream_provider": transport.upstream_provider,
                    "estimated_cost": transport.estimated_cost,
                    "attempts": attempts,
                }
            )
            return result

        if is_cloud_provider(entry.provider) and transport.error in (
            LlmTransportError.RATE_LIMIT,
            LlmTransportError.SERVER,
            LlmTransportError.QUOTA,
        ):
            _mark_cloud_cooldown(entry.provider)

        if not _should_fallback(transport.error):
            break

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
        {
            "task": task,
            "tier": resolved_tier,
            "route_profile": active_route_profile,
            "provider": result.provider,
            "model": result.model,
            "fallback": fallback_used,
            "latency_ms": latency,
            "error": result.error,
            "attempts": attempts,
        }
    )
    return result


def gateway_available(override: LlmOptions | None = None) -> str | None:
    if override and _has_llm_override(override):
        opts = resolve_llm_options(override)
        if llm_reachable(opts):
            return opts.base_url
        return (override.base_url or "").strip().rstrip("/") or None

    for tier_name in ("medium", "light", "heavy"):
        for entry in get_chain_for_tier(tier_name):
            opts = entry_to_options(entry)
            if llm_reachable(opts):
                return opts.base_url

    if not _settings().ollama_enabled:
        return None
    opts = resolve_llm_options()
    return opts.base_url if llm_reachable(opts) else None


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
    }
