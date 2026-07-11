"""LLM provider reachability probes for test-connection UI."""

from __future__ import annotations

import time
from typing import Any

import httpx

from backend.core.llm_capabilities import entry_is_configured, entry_to_options
from backend.core.llm_gateway import gateway_chain_status
from backend.core.llm_tiers import ChainEntry, parse_chain_entry
from backend.core.ollama_client import (
    GEMINI_API_BASE,
    LlmOptions,
    _auth_headers_for_options,
    _normalize_provider,
    _openai_api_base,
)


def _probe_options(opts: LlmOptions) -> dict[str, Any]:
    """HTTP probe with latency; ignores OLLAMA_ENABLED gate."""
    started = time.perf_counter()
    provider = _normalize_provider(opts.provider or "ollama")
    base_url = (opts.base_url or "").strip().rstrip("/")
    error: str | None = None
    reachable = False
    try:
        with httpx.Client(timeout=8.0) as client:
            if provider == "gemini":
                if not (opts.api_key or "").strip():
                    error = "missing_api_key"
                else:
                    url = f"{GEMINI_API_BASE}/models"
                    res = client.get(
                        url,
                        headers={
                            "Content-Type": "application/json",
                            "x-goog-api-key": opts.api_key.strip(),
                        },
                    )
                    res.raise_for_status()
                    reachable = True
            elif provider == "lmstudio":
                url = f"{base_url}/api/v1/models"
                res = client.get(url, headers=_auth_headers_for_options(opts))
                res.raise_for_status()
                reachable = True
            elif provider == "openai":
                url = f"{_openai_api_base(base_url)}/models"
                res = client.get(url, headers=_auth_headers_for_options(opts))
                res.raise_for_status()
                reachable = True
            else:
                url = f"{base_url}/api/tags"
                res = client.get(url, headers=_auth_headers_for_options(opts))
                res.raise_for_status()
                reachable = True
    except httpx.HTTPStatusError as exc:
        error = f"http_{exc.response.status_code}"
    except Exception as exc:
        error = str(exc)[:200]

    latency_ms = int((time.perf_counter() - started) * 1000)
    return {
        "provider": provider,
        "model": opts.model,
        "base_url": base_url or None,
        "configured": bool((opts.api_key or "").strip()) if provider in ("gemini", "openai") else True,
        "reachable": reachable,
        "latency_ms": latency_ms,
        "error": error,
    }


def chain_entry_label(entry: ChainEntry) -> str:
    raw = entry.provider.strip().lower()
    base = (entry.base_url or "").lower()
    if raw == "openrouter" or "openrouter.ai" in base:
        return f"openrouter:{entry.model}"
    if raw == "groq" or "api.groq.com" in base:
        return f"groq:{entry.model}"
    if raw == "cerebras" or "api.cerebras.ai" in base:
        return f"cerebras:{entry.model}"
    if raw == "mistral" or "api.mistral.ai" in base:
        return f"mistral:{entry.model}"
    if raw == "github" or "models.github.ai" in base:
        return f"github:{entry.model}"
    if entry.base_url:
        return f"{entry.provider}:{entry.base_url}:{entry.model}"
    return f"{entry.provider}:{entry.model}"


def test_chain_entry(
    entry_raw: str,
    *,
    api_key_override: str | None = None,
) -> dict[str, Any]:
    entry = parse_chain_entry(entry_raw)
    if entry is None:
        return {"entry": entry_raw, "configured": False, "reachable": False, "error": "invalid_entry"}
    if api_key_override:
        entry = ChainEntry(
            provider=entry.provider,
            model=entry.model,
            base_url=entry.base_url,
            api_key=api_key_override,
        )
    opts = entry_to_options(entry)
    result = _probe_options(opts)
    result["entry"] = entry_raw
    result["configured"] = entry_is_configured(entry)
    return result


def test_chain_entry_from_parts(
    *,
    provider: str,
    model: str,
    base_url: str | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    entry = ChainEntry(
        provider=_normalize_provider(provider),
        model=model,
        base_url=base_url,
        api_key=api_key,
    )
    opts = entry_to_options(entry)
    if api_key:
        opts = LlmOptions(
            provider=opts.provider,
            base_url=opts.base_url,
            model=opts.model,
            max_tokens=opts.max_tokens,
            api_key=api_key,
        )
    result = _probe_options(opts)
    result["entry"] = chain_entry_label(entry)
    result["configured"] = entry_is_configured(entry)
    return result


def test_tier_chain(
    tier: str = "medium",
    *,
    route_profile: str | None = None,
    task: str = "generic",
) -> dict[str, Any]:
    status = gateway_chain_status(tier, task=task, route_profile=route_profile)
    results: list[dict[str, Any]] = []
    for item in status.get("chain") or []:
        entry = ChainEntry(
            provider=item["provider"],
            model=item["model"],
            base_url=item.get("base_url"),
        )
        opts = entry_to_options(entry)
        probe = _probe_options(opts)
        probe["entry"] = chain_entry_label(entry)
        probe["configured"] = item.get("configured", entry_is_configured(entry))
        results.append(probe)
    return {
        "tier": status.get("tier"),
        "route_profile": status.get("route_profile"),
        "task": status.get("task"),
        "reachable": any(r.get("reachable") for r in results),
        "entries": results,
    }
