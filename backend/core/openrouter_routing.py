"""OpenRouter-native routing: models[] fallbacks + provider preferences."""

from __future__ import annotations

import logging
from typing import Any, Iterator

from backend.core.llm_capabilities import LlmRequirements
from backend.core.llm_tiers import ChainEntry

log = logging.getLogger(__name__)

OPENROUTER_BASE = "https://openrouter.ai/api/v1"

# Batch / background — cheaper flex tier; interactive — priority.
_BATCH_TASKS = frozenset(
    {
        "notes_chunk",
        "notes_refine",
        "notes_job",
        "corpus_grounded",
        "quiz_gen",
        "gap_analysis",
        "drill_gen",
        "block_regen",
        "note_enrich",
        "folder_summarize",
        "kg_anchor",
        "memory_extract",
        "vocab_enrich",
        "classify",
        "daily_review",
        "generic",
    }
)
_INTERACTIVE_TASKS = frozenset(
    {
        "coach",
        "hub_router",
        "corpus_qa",
        "math_hint",
        "project_agent",
        "web_search",
    }
)
_CACHE_ELIGIBLE_TASKS = frozenset(
    {
        "quiz_gen",
        "gap_analysis",
        "drill_gen",
        "classify",
        "kg_anchor",
        "memory_extract",
        "vocab_enrich",
    }
)


def is_openrouter_entry(entry: ChainEntry) -> bool:
    raw = entry.provider.strip().lower()
    base = (entry.base_url or "").lower()
    return raw == "openrouter" or "openrouter.ai" in base


def iter_chain_segments(
    chain: list[ChainEntry],
) -> Iterator[tuple[str, ChainEntry | list[ChainEntry]]]:
    """Group consecutive OpenRouter entries for a single API call with models[]."""
    batch: list[ChainEntry] = []
    for entry in chain:
        if is_openrouter_entry(entry):
            batch.append(entry)
            continue
        if batch:
            yield ("openrouter_batch", batch)
            batch = []
        yield ("single", entry)
    if batch:
        yield ("openrouter_batch", batch)


def openrouter_models_from_entries(entries: list[ChainEntry]) -> list[str]:
    """Model slugs or dashboard presets (e.g. @preset/calt-medium) pass through unchanged."""
    seen: set[str] = set()
    models: list[str] = []
    for entry in entries:
        slug = entry.model.strip()
        if slug and slug not in seen:
            seen.add(slug)
            models.append(slug)
    return models


def service_tier_for_task(task: str) -> str | None:
    key = task.strip().lower()
    if key in _INTERACTIVE_TASKS:
        return "priority"
    if key in _BATCH_TASKS:
        return "flex"
    return None


def response_cache_enabled_for_task(task: str) -> bool:
    from backend.config import get_settings

    s = get_settings()
    if not getattr(s, "llm_openrouter_response_cache", True):
        return False
    return task.strip().lower() in _CACHE_ELIGIBLE_TASKS


def provider_prefs_for_request(
    *,
    tier: str,
    task: str = "generic",
    requirements: LlmRequirements | None = None,
) -> dict[str, Any]:
    from backend.config import get_settings

    s = get_settings()
    prefs: dict[str, Any] = {"allow_fallbacks": True}
    tier_key = tier.strip().lower()

    sort = (getattr(s, "llm_openrouter_provider_sort", "") or "").strip().lower()
    if not sort:
        sort = {"light": "latency", "medium": "price", "heavy": "throughput"}.get(tier_key, "price")
    if sort in ("latency", "throughput", "price"):
        prefs["sort"] = sort

    # SLA thresholds per tier (OpenRouter preferred_max_latency).
    latency_caps = {
        "light": getattr(s, "llm_openrouter_max_latency_light", 2.0),
        "medium": getattr(s, "llm_openrouter_max_latency_medium", 8.0),
        "heavy": getattr(s, "llm_openrouter_max_latency_heavy", 0.0),
    }
    cap = latency_caps.get(tier_key, 0.0)
    if isinstance(cap, (int, float)) and cap > 0:
        prefs["preferred_max_latency"] = float(cap)

    throughput_floor = getattr(s, "llm_openrouter_min_throughput_heavy", 0.0)
    if tier_key == "heavy" and isinstance(throughput_floor, (int, float)) and throughput_floor > 0:
        prefs["preferred_min_throughput"] = float(throughput_floor)

    data_policy = (getattr(s, "llm_openrouter_data_collection", "") or "").strip().lower()
    if data_policy in ("allow", "deny"):
        prefs["data_collection"] = data_policy

    if getattr(s, "llm_openrouter_zdr", False):
        prefs["zdr"] = True

    if requirements and requirements.needs_json_schema:
        prefs["require_parameters"] = True

    # Cost guardrail on heavy tier (USD per million tokens).
    if tier_key == "heavy":
        prompt_cap = getattr(s, "llm_openrouter_max_price_prompt", 0.0)
        completion_cap = getattr(s, "llm_openrouter_max_price_completion", 0.0)
        max_price: dict[str, float] = {}
        if isinstance(prompt_cap, (int, float)) and prompt_cap > 0:
            max_price["prompt"] = float(prompt_cap)
        if isinstance(completion_cap, (int, float)) and completion_cap > 0:
            max_price["completion"] = float(completion_cap)
        if max_price:
            prefs["max_price"] = max_price

    return prefs


def build_openrouter_payload(
    *,
    models: list[str],
    messages: list[dict[str, str]],
    max_tokens: int,
    provider: dict[str, Any] | None = None,
    json_schema: dict | None = None,
    session_id: str | None = None,
    service_tier: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "messages": messages,
        "temperature": 0.4,
        "max_tokens": max_tokens,
        "stream": False,
    }
    if len(models) == 1:
        payload["model"] = models[0]
    else:
        payload["models"] = models
    if provider:
        payload["provider"] = provider
    if json_schema is not None:
        payload["response_format"] = {"type": "json_object"}
    if session_id:
        payload["session_id"] = normalize_session_id(session_id)
    if service_tier in ("flex", "priority"):
        payload["service_tier"] = service_tier
    return payload


def normalize_session_id(session_id: str | None) -> str | None:
    """OpenRouter max 256 chars for session_id (body or x-session-id header)."""
    if not session_id:
        return None
    trimmed = session_id.strip()
    return trimmed[:256] if trimmed else None


def openrouter_request_headers(
    opts,
    *,
    session_id: str | None = None,
    task: str = "generic",
) -> dict[str, str]:
    """Auth, sticky session, router metadata, optional response cache."""
    from backend.config import get_settings
    from backend.core.ollama_client import _auth_headers_for_options

    s = get_settings()
    headers = _auth_headers_for_options(opts)
    sid = normalize_session_id(session_id)
    if sid:
        headers["x-session-id"] = sid
    if getattr(s, "llm_openrouter_metadata", True):
        headers["X-OpenRouter-Metadata"] = "enabled"
    if response_cache_enabled_for_task(task):
        headers["X-OpenRouter-Cache"] = "enabled"
    return headers


def parse_openrouter_response(data: dict[str, Any]) -> dict[str, Any]:
    """Extract routing metadata, billing signals, and zero-completion insurance flags."""
    choices = data.get("choices") or []
    first = choices[0] if choices else {}
    msg = first.get("message") or {}
    usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
    finish_reason = first.get("finish_reason")
    completion_tokens = usage.get("completion_tokens")
    prompt_tokens = usage.get("prompt_tokens")
    total_tokens = usage.get("total_tokens")

    zero_insurance = False
    if finish_reason == "error":
        zero_insurance = True
    if isinstance(completion_tokens, int) and completion_tokens == 0:
        zero_insurance = True

    metadata = data.get("openrouter_metadata")
    if not isinstance(metadata, dict):
        metadata = None

    return {
        "text": (msg.get("content") or "").strip() or None,
        "resolved_model": data.get("model") if isinstance(data.get("model"), str) else None,
        "finish_reason": finish_reason,
        "prompt_tokens": prompt_tokens if isinstance(prompt_tokens, int) else None,
        "completion_tokens": completion_tokens if isinstance(completion_tokens, int) else None,
        "total_tokens": total_tokens if isinstance(total_tokens, int) else None,
        "generation_id": str(data.get("id")) if data.get("id") else None,
        "upstream_provider": str(data.get("provider")) if isinstance(data.get("provider"), str) else None,
        "estimated_cost": float(data["cost"]) if isinstance(data.get("cost"), (int, float)) else None,
        "openrouter_metadata": metadata,
        "zero_completion_insurance": zero_insurance,
    }


def log_openrouter_metadata(
    *,
    task: str,
    tier: str,
    models: list[str],
    parsed: dict[str, Any],
    session_id: str | None,
) -> None:
    meta = parsed.get("openrouter_metadata")
    if meta:
        log.info(
            "OpenRouter routing task=%s tier=%s models=%s resolved=%s strategy=%s attempt=%s session=%s meta=%s",
            task,
            tier,
            models,
            parsed.get("resolved_model"),
            meta.get("strategy"),
            meta.get("attempt"),
            session_id,
            meta,
        )
    elif parsed.get("zero_completion_insurance"):
        log.info(
            "OpenRouter zero-completion (not billed) task=%s tier=%s finish_reason=%s model=%s",
            task,
            tier,
            parsed.get("finish_reason"),
            parsed.get("resolved_model"),
        )
    else:
        log.info(
            "OpenRouter models=%s resolved_model=%s session=%s",
            models,
            parsed.get("resolved_model"),
            session_id,
        )


def openrouter_session_id(*, task: str, tier: str) -> str | None:
    """Sticky routing for multi-turn / multi-chunk jobs."""
    from backend.core.llm_job_context import get_job_context

    ctx = get_job_context()
    if ctx and ctx.task:
        return normalize_session_id(f"calt-{ctx.task}-{tier}")
    if task in ("notes_job", "notes_chunk", "coach", "hub_router", "corpus_qa"):
        return normalize_session_id(f"calt-{task}-{tier}")
    return None
