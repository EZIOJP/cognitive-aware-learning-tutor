"""Shared local LLM client — Ollama, LM Studio native v1, or OpenAI-compatible APIs."""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any

import httpx

log = logging.getLogger(__name__)

_LLM_REACHABLE_CACHE: dict[str, tuple[float, bool]] = {}
_LLM_REACHABLE_LOCK = threading.Lock()
# Short TTL for successes; failures cached longer so dead LM Studio doesn't add ~8s per call.
_LLM_REACHABLE_TTL_OK_SEC = 55.0
_LLM_REACHABLE_TTL_FAIL_SEC = 120.0
_LLM_REACHABLE_TIMEOUT_SEC = 2.0


class LlmTransportError(str, Enum):
    NONE = "none"
    RATE_LIMIT = "rate_limit"
    AUTH = "auth"
    QUOTA = "quota"
    TIMEOUT = "timeout"
    CONTEXT_TOO_LONG = "context_too_long"
    EMPTY = "empty"
    CONNECTION = "connection"
    SERVER = "server"
    UNKNOWN = "unknown"


@dataclass
class TransportResult:
    text: str | None = None
    error: LlmTransportError = LlmTransportError.NONE
    latency_ms: int = 0
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    generation_id: str | None = None
    upstream_provider: str | None = None
    estimated_cost: float | None = None
    resolved_model: str | None = None
    finish_reason: str | None = None
    openrouter_metadata: dict[str, Any] | None = None
    zero_completion_insurance: bool = False


@dataclass(frozen=True)
class LlmOptions:
    provider: str | None = None
    base_url: str | None = None
    model: str | None = None
    max_tokens: int | None = None
    api_key: str | None = None


GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"


def _gemini_auth_headers(api_key: str) -> dict[str, str]:
    """Google accepts key as query param or x-goog-api-key header (required for some key types)."""
    return {
        "Content-Type": "application/json",
        "x-goog-api-key": api_key.strip(),
    }


def _normalize_provider(raw: str) -> str:
    value = raw.strip().lower()
    if value in ("lmstudio", "lm-studio", "lm_studio"):
        return "lmstudio"
    if value in ("openai", "vllm"):
        return "openai"
    from backend.core.llm_providers import OPENAI_COMPAT_ALIASES

    if value in OPENAI_COMPAT_ALIASES or value in ("openrouter", "or"):
        return "openai"
    if value in ("gemini", "google", "google-ai", "google_ai"):
        return "gemini"
    return "ollama"


def _settings():
    from backend.config import get_settings

    return get_settings()


def resolve_llm_options(override: LlmOptions | None = None) -> LlmOptions:
    s = _settings()
    raw_provider = s.llm_provider.strip().lower()
    provider = _normalize_provider(s.llm_provider)
    if raw_provider in ("openrouter", "or"):
        default_base = "https://openrouter.ai/api/v1"
    elif provider == "gemini":
        default_base = GEMINI_API_BASE
    else:
        default_base = s.ollama_url.strip().rstrip("/")
    base = LlmOptions(
        provider=provider,
        base_url=default_base,
        model=s.ollama_model.strip(),
        max_tokens=max(256, s.llm_max_tokens),
        api_key=s.llm_api_key.strip(),
    )
    if not override:
        return base
    resolved_provider = _normalize_provider(override.provider) if override.provider else base.provider
    resolved_base = (override.base_url or base.base_url).strip().rstrip("/")
    if resolved_provider == "gemini" and not override.base_url:
        resolved_base = GEMINI_API_BASE
    return LlmOptions(
        provider=resolved_provider,
        base_url=resolved_base,
        model=(override.model or base.model).strip(),
        max_tokens=override.max_tokens or base.max_tokens,
        api_key=(override.api_key if override.api_key is not None else base.api_key).strip(),
    )


def get_llm_config() -> dict:
    opts = resolve_llm_options()
    return {
        "enabled": _settings().ollama_enabled,
        "provider": opts.provider,
        "base_url": opts.base_url,
        "model": opts.model,
        "max_tokens": opts.max_tokens,
    }


def _classify_http_error(exc: Exception) -> LlmTransportError:
    if isinstance(exc, httpx.TimeoutException):
        return LlmTransportError.TIMEOUT
    if isinstance(exc, httpx.ConnectError):
        return LlmTransportError.CONNECTION
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        body = ""
        try:
            body = exc.response.text.lower()
        except Exception:  # noqa: BLE001
            pass
        if code == 429:
            return LlmTransportError.RATE_LIMIT
        if code in (401, 403):
            return LlmTransportError.AUTH
        if code in (402, 413) or "quota" in body or "billing" in body:
            return LlmTransportError.QUOTA if code != 413 else LlmTransportError.CONTEXT_TOO_LONG
        if code == 413 or "context" in body and "length" in body:
            return LlmTransportError.CONTEXT_TOO_LONG
        if code >= 500:
            return LlmTransportError.SERVER
    return LlmTransportError.UNKNOWN


def _auth_headers(api_key: str) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def _is_openrouter_base(base_url: str | None) -> bool:
    if not base_url:
        return False
    return "openrouter.ai" in base_url.lower()


def _auth_headers_for_options(opts: LlmOptions) -> dict[str, str]:
    headers = _auth_headers(opts.api_key or "")
    if _is_openrouter_base(opts.base_url):
        s = _settings()
        referer = s.llm_openrouter_site_url.strip()
        app_name = s.llm_openrouter_app_name.strip()
        if referer:
            headers["HTTP-Referer"] = referer
        if app_name:
            headers["X-Title"] = app_name
    return headers


def llm_reachable(override: LlmOptions | None = None) -> bool:
    if not _settings().ollama_enabled and not _has_llm_override(override):
        return False
    opts = resolve_llm_options(override)
    cache_key = f"{opts.provider}|{opts.base_url}"
    now = time.monotonic()
    with _LLM_REACHABLE_LOCK:
        cached = _LLM_REACHABLE_CACHE.get(cache_key)
        if cached:
            age = now - cached[0]
            ttl = _LLM_REACHABLE_TTL_OK_SEC if cached[1] else _LLM_REACHABLE_TTL_FAIL_SEC
            if age < ttl:
                return cached[1]
        try:
            with httpx.Client(timeout=_LLM_REACHABLE_TIMEOUT_SEC) as client:
                if opts.provider == "gemini":
                    if not opts.api_key:
                        return False
                    url = f"{GEMINI_API_BASE}/models"
                    res = client.get(url, headers=_gemini_auth_headers(opts.api_key))
                    res.raise_for_status()
                    ok = True
                elif opts.provider == "lmstudio":
                    url = f"{opts.base_url}/api/v1/models"
                    res = client.get(url, headers=_auth_headers_for_options(opts))
                    res.raise_for_status()
                    ok = True
                elif opts.provider == "openai":
                    url = f"{_openai_api_base(opts.base_url)}/models"
                    if opts.base_url.rstrip("/").endswith("/inference"):
                        url = f"{opts.base_url.rstrip('/')}/models"
                    res = client.get(url, headers=_auth_headers_for_options(opts))
                    res.raise_for_status()
                    ok = True
                else:
                    url = f"{opts.base_url}/api/tags"
                    res = client.get(url, headers=_auth_headers_for_options(opts))
                    res.raise_for_status()
                    ok = True
        except Exception:
            ok = False
        _LLM_REACHABLE_CACHE[cache_key] = (now, ok)
        return ok


def _has_llm_override(override: LlmOptions | None) -> bool:
    if not override:
        return False
    provider = _normalize_provider(override.provider) if override.provider else None
    if provider == "gemini":
        opts = resolve_llm_options(override)
        return bool(opts.api_key and opts.model)
    return bool(
        (override.base_url or "").strip()
        and (override.model or "").strip()
    )


def ollama_available(override: LlmOptions | None = None) -> str | None:
    from backend.core.llm_gateway import gateway_available

    return gateway_available(override)


def _openai_api_base(base: str) -> str:
    b = base.rstrip("/")
    if b.endswith("/v1") or b.endswith("/inference"):
        return b
    return f"{b}/v1"


def _openai_chat_url(base_url: str) -> str:
    from backend.core.llm_providers import chat_completions_url

    base = base_url.rstrip("/")
    if base.endswith("/inference"):
        return chat_completions_url(base, uses_v1_prefix=False)
    return f"{_openai_api_base(base)}/chat/completions"


def _parse_lmstudio_output(data: dict) -> str | None:
    output = data.get("output") or []
    parts: list[str] = []
    for item in output:
        if isinstance(item, dict) and item.get("type") == "message":
            content = item.get("content")
            if isinstance(content, str) and content.strip():
                parts.append(content.strip())
    if parts:
        return "\n".join(parts)
    # Fallback for older/alternate response shapes
    for key in ("response", "content", "text"):
        val = data.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return None


def _lmstudio_generate(
    prompt: str,
    *,
    opts: LlmOptions,
    timeout: float,
    system_prompt: str | None = None,
) -> TransportResult:
    payload: dict = {
        "model": opts.model,
        "input": prompt,
        "reasoning": "off",
    }
    if system_prompt:
        payload["system_prompt"] = system_prompt
    if opts.max_tokens:
        payload["max_output_tokens"] = opts.max_tokens

    url = f"{opts.base_url}/api/v1/chat"
    started = time.perf_counter()

    try:
        with httpx.Client(timeout=timeout) as client:
            res = client.post(url, headers=_auth_headers(opts.api_key or ""), json=payload)
            if res.status_code == 400 and payload.get("reasoning") is not None:
                payload.pop("reasoning", None)
                res = client.post(url, headers=_auth_headers(opts.api_key or ""), json=payload)
            res.raise_for_status()
            data = res.json()
        raw = _parse_lmstudio_output(data)
        latency = int((time.perf_counter() - started) * 1000)
        if not raw:
            return TransportResult(text=None, error=LlmTransportError.EMPTY, latency_ms=latency)
        return TransportResult(text=raw, latency_ms=latency)
    except Exception as exc:
        log.warning("LM Studio native API request failed: %s", exc)
        return TransportResult(
            error=_classify_http_error(exc),
            latency_ms=int((time.perf_counter() - started) * 1000),
        )


def _parse_gemini_output(data: dict) -> str | None:
    candidates = data.get("candidates") or []
    if not candidates:
        return None
    content = candidates[0].get("content") or {}
    parts = content.get("parts") or []
    texts: list[str] = []
    for part in parts:
        if isinstance(part, dict):
            text = part.get("text")
            if isinstance(text, str) and text.strip():
                texts.append(text.strip())
    return "\n".join(texts) if texts else None


def _gemini_generate(
    prompt: str,
    *,
    opts: LlmOptions,
    timeout: float,
    system_prompt: str | None = None,
) -> TransportResult:
    if not opts.api_key:
        log.warning("Gemini API key missing — set LLM_CLOUD_API_KEY or LLM_API_KEY in .env")
        return TransportResult(error=LlmTransportError.AUTH)

    model = opts.model.strip()
    if model.startswith("models/"):
        model = model[7:]

    payload: dict = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.35,
            "maxOutputTokens": opts.max_tokens or 8192,
        },
    }
    if system_prompt:
        payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}

    url = f"{GEMINI_API_BASE}/models/{model}:generateContent"
    started = time.perf_counter()

    try:
        with httpx.Client(timeout=timeout) as client:
            res = client.post(
                url,
                headers=_gemini_auth_headers(opts.api_key),
                json=payload,
            )
            res.raise_for_status()
            data = res.json()
        raw = _parse_gemini_output(data)
        latency = int((time.perf_counter() - started) * 1000)
        if not raw:
            return TransportResult(error=LlmTransportError.EMPTY, latency_ms=latency)
        return TransportResult(text=raw, latency_ms=latency)
    except httpx.HTTPStatusError as exc:
        err = _classify_http_error(exc)
        if err == LlmTransportError.RATE_LIMIT:
            log.info("Gemini rate limit (429) — gateway will try next provider")
        elif err == LlmTransportError.SERVER:
            log.info("Gemini temporarily unavailable (503) — gateway will try next provider")
        else:
            log.warning("Gemini API request failed: %s", exc)
        return TransportResult(
            error=err,
            latency_ms=int((time.perf_counter() - started) * 1000),
        )
    except Exception as exc:
        log.warning("Gemini API request failed: %s", exc)
        return TransportResult(
            error=_classify_http_error(exc),
            latency_ms=int((time.perf_counter() - started) * 1000),
        )


def _openai_generate(
    prompt: str,
    *,
    opts: LlmOptions,
    timeout: float,
    system_prompt: str | None = None,
    models: list[str] | None = None,
    provider_prefs: dict | None = None,
    json_schema: dict | None = None,
    session_id: str | None = None,
) -> TransportResult:
    messages: list[dict[str, str]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    model_list = models or ([opts.model] if opts.model else [])
    payload: dict = {
        "messages": messages,
        "temperature": 0.4,
        "max_tokens": opts.max_tokens or 8192,
        "stream": False,
    }
    if len(model_list) > 1:
        payload["models"] = model_list
    else:
        payload["model"] = model_list[0] if model_list else opts.model
    if provider_prefs:
        payload["provider"] = provider_prefs
    if json_schema is not None:
        payload["response_format"] = {"type": "json_object"}
    if session_id:
        payload["session_id"] = session_id

    if "127.0.0.1:1234" in (opts.base_url or "") or "localhost:1234" in (opts.base_url or ""):
        payload["reasoning"] = "off"
    url = _openai_chat_url(opts.base_url)
    started = time.perf_counter()

    try:
        with httpx.Client(timeout=timeout) as client:
            res = client.post(url, headers=_auth_headers_for_options(opts), json=payload)
            if res.status_code == 400 and payload.get("reasoning") is not None:
                payload.pop("reasoning", None)
                res = client.post(url, headers=_auth_headers_for_options(opts), json=payload)
            res.raise_for_status()
            data = res.json()
        choices = data.get("choices") or []
        latency = int((time.perf_counter() - started) * 1000)
        if not choices:
            return TransportResult(error=LlmTransportError.EMPTY, latency_ms=latency)
        msg = choices[0].get("message") or {}
        raw = (msg.get("content") or "").strip()
        if not raw:
            return TransportResult(error=LlmTransportError.EMPTY, latency_ms=latency)
        usage = data.get("usage") if isinstance(data, dict) else {}
        prompt_tokens = usage.get("prompt_tokens") if isinstance(usage, dict) else None
        completion_tokens = usage.get("completion_tokens") if isinstance(usage, dict) else None
        total_tokens = usage.get("total_tokens") if isinstance(usage, dict) else None
        cost = None
        if isinstance(usage, dict):
            maybe_cost = usage.get("cost")
            if isinstance(maybe_cost, (int, float)):
                cost = float(maybe_cost)
        if cost is None:
            maybe_cost = data.get("cost") if isinstance(data, dict) else None
            if isinstance(maybe_cost, (int, float)):
                cost = float(maybe_cost)
        upstream_provider = data.get("provider") if isinstance(data, dict) else None
        resolved_model = data.get("model") if isinstance(data, dict) else None
        return TransportResult(
            text=raw,
            latency_ms=latency,
            prompt_tokens=prompt_tokens if isinstance(prompt_tokens, int) else None,
            completion_tokens=completion_tokens if isinstance(completion_tokens, int) else None,
            total_tokens=total_tokens if isinstance(total_tokens, int) else None,
            generation_id=str(data.get("id")) if isinstance(data, dict) and data.get("id") else None,
            upstream_provider=str(upstream_provider) if isinstance(upstream_provider, str) else None,
            estimated_cost=cost,
            resolved_model=str(resolved_model) if isinstance(resolved_model, str) else None,
        )
    except Exception as exc:
        log.warning("OpenAI-compatible LLM request failed: %s", exc)
        return TransportResult(
            error=_classify_http_error(exc),
            latency_ms=int((time.perf_counter() - started) * 1000),
        )


def openrouter_batch_generate(
    prompt: str,
    *,
    entries: list,
    timeout: float = 120.0,
    system_prompt: str | None = None,
    json_schema: dict | None = None,
    tier: str = "medium",
    task: str = "generic",
    requirements=None,
) -> TransportResult:
    """One OpenRouter call with models[] fallback chain (native OR routing)."""
    from backend.core.llm_capabilities import LlmRequirements, entry_to_options
    from backend.core.openrouter_routing import (
        build_openrouter_payload,
        log_openrouter_metadata,
        openrouter_models_from_entries,
        openrouter_request_headers,
        openrouter_session_id,
        parse_openrouter_response,
        provider_prefs_for_request,
        service_tier_for_task,
    )

    if not entries:
        return TransportResult(error=LlmTransportError.UNKNOWN)
    opts = entry_to_options(entries[0])
    models = openrouter_models_from_entries(entries)
    req = requirements if isinstance(requirements, LlmRequirements) else LlmRequirements()
    provider_prefs = provider_prefs_for_request(tier=tier, task=task, requirements=req)
    session_id = openrouter_session_id(task=task, tier=tier)
    service_tier = service_tier_for_task(task)
    messages: list[dict[str, str]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    payload = build_openrouter_payload(
        models=models,
        messages=messages,
        max_tokens=opts.max_tokens or 8192,
        provider=provider_prefs,
        json_schema=json_schema,
        session_id=session_id,
        service_tier=service_tier,
    )
    url = _openai_chat_url(opts.base_url)
    started = time.perf_counter()
    try:
        with httpx.Client(timeout=timeout) as client:
            res = client.post(
                url,
                headers=openrouter_request_headers(opts, session_id=session_id, task=task),
                json=payload,
            )
            res.raise_for_status()
            data = res.json()
        parsed = parse_openrouter_response(data)
        latency = int((time.perf_counter() - started) * 1000)
        log_openrouter_metadata(
            task=task,
            tier=tier,
            models=models,
            parsed=parsed,
            session_id=session_id,
        )
        if not parsed.get("text"):
            return TransportResult(
                error=LlmTransportError.EMPTY,
                latency_ms=latency,
                finish_reason=parsed.get("finish_reason"),
                openrouter_metadata=parsed.get("openrouter_metadata"),
                zero_completion_insurance=bool(parsed.get("zero_completion_insurance")),
                resolved_model=parsed.get("resolved_model"),
            )
        return TransportResult(
            text=parsed["text"],
            latency_ms=latency,
            prompt_tokens=parsed.get("prompt_tokens"),
            completion_tokens=parsed.get("completion_tokens"),
            total_tokens=parsed.get("total_tokens"),
            generation_id=parsed.get("generation_id"),
            upstream_provider=parsed.get("upstream_provider") or "openrouter",
            estimated_cost=parsed.get("estimated_cost"),
            resolved_model=parsed.get("resolved_model"),
            finish_reason=parsed.get("finish_reason"),
            openrouter_metadata=parsed.get("openrouter_metadata"),
            zero_completion_insurance=bool(parsed.get("zero_completion_insurance")),
        )
    except Exception as exc:
        log.warning("OpenRouter batch request failed: %s", exc)
        return TransportResult(
            error=_classify_http_error(exc),
            latency_ms=int((time.perf_counter() - started) * 1000),
        )


def _ollama_native_generate(
    prompt: str,
    *,
    opts: LlmOptions,
    timeout: float,
    json_schema: dict | None,
    system_prompt: str | None = None,
    keep_alive: int = -1,
) -> TransportResult:
    full_prompt = prompt
    if system_prompt:
        full_prompt = f"{system_prompt}\n\n{prompt}"
    payload: dict = {
        "model": opts.model,
        "prompt": full_prompt,
        "stream": False,
        # -1 = pin (default for app tasks); 0 = unload after reply (voice sessions)
        "keep_alive": keep_alive,
    }
    if json_schema:
        payload["format"] = json_schema

    started = time.perf_counter()
    try:
        with httpx.Client(timeout=timeout) as client:
            res = client.post(f"{opts.base_url}/api/generate", json=payload)
            res.raise_for_status()
            data = res.json()
        raw = (data.get("response") or "").strip()
        latency = int((time.perf_counter() - started) * 1000)
        if not raw:
            return TransportResult(error=LlmTransportError.EMPTY, latency_ms=latency)
        return TransportResult(text=raw, latency_ms=latency)
    except Exception as exc:
        log.warning("Ollama request failed: %s", exc)
        return TransportResult(
            error=_classify_http_error(exc),
            latency_ms=int((time.perf_counter() - started) * 1000),
        )


def ollama_generate_transport(
    prompt: str,
    *,
    opts: LlmOptions,
    timeout: float = 120.0,
    json_schema: dict | None = None,
    system_prompt: str | None = None,
    keep_alive: int | None = None,
) -> TransportResult:
    if opts.provider == "gemini":
        if json_schema:
            log.warning("JSON schema is ignored for Gemini API.")
        return _gemini_generate(prompt, opts=opts, timeout=timeout, system_prompt=system_prompt)
    if opts.provider == "lmstudio":
        if json_schema:
            log.warning("JSON schema is ignored for LM Studio native API.")
        log.info("LM Studio generate model=%s url=%s", opts.model, opts.base_url)
        return _lmstudio_generate(prompt, opts=opts, timeout=timeout, system_prompt=system_prompt)
    if opts.provider == "openai":
        if json_schema:
            log.warning("JSON schema is ignored for OpenAI-compatible LLM provider.")
        return _openai_generate(prompt, opts=opts, timeout=timeout, system_prompt=system_prompt)
    return _ollama_native_generate(
        prompt,
        opts=opts,
        timeout=timeout,
        json_schema=json_schema,
        system_prompt=system_prompt,
        keep_alive=-1 if keep_alive is None else keep_alive,
    )


def ollama_generate(
    prompt: str,
    *,
    model: str | None = None,
    timeout: float = 120.0,
    json_schema: dict | None = None,
    llm: LlmOptions | None = None,
    system_prompt: str | None = None,
    task: str = "generic",
    tier: str | None = None,
    confirm_heavy_budget: bool = False,
) -> str | None:
    from backend.core.llm_gateway import llm_complete

    result = llm_complete(
        prompt,
        task=task,
        tier=tier,
        json_schema=json_schema,
        timeout=timeout,
        llm=llm,
        system_prompt=system_prompt,
        model=model,
        confirm_heavy_budget=confirm_heavy_budget,
    )
    if result.error:
        log.debug("ollama_generate task=%s error=%s", task, result.error)
    return result.text
