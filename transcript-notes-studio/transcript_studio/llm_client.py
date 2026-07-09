"""Local LLM client — Ollama, LM Studio, or OpenAI-compatible APIs."""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass

import httpx

from transcript_studio.config import AppConfig, load_config

log = logging.getLogger(__name__)

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"


def _gemini_auth_headers(api_key: str) -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "x-goog-api-key": api_key.strip(),
    }

_LLM_REACHABLE_CACHE: dict[str, tuple[float, bool]] = {}
_LLM_REACHABLE_LOCK = threading.Lock()
# Studio polls RAG/LLM status every 30s — TTL must exceed that to avoid hammering /api/v1/models.
_LLM_REACHABLE_TTL_SEC = 55.0


def _agent_llm_log(cache_hit: bool, caller: str) -> None:
    try:
        from backend.transcripts._debug_agent_log import agent_log

        agent_log(
            location="llm_client.py:llm_reachable",
            message="llm_ping",
            data={"cache_hit": cache_hit, "caller_hint": caller},
            hypothesis_id="H4",
        )
    except Exception:
        pass


@dataclass(frozen=True)
class LlmOptions:
    provider: str
    base_url: str
    model: str
    max_tokens: int = 8192
    temperature: float = 0.3
    api_key: str = ""


def _normalize_provider(raw: str) -> str:
    value = raw.strip().lower()
    if value in ("lmstudio", "lm-studio", "lm_studio"):
        return "lmstudio"
    if value in ("openai", "vllm", "openrouter", "or"):
        return "openai"
    if value in ("gemini", "google", "google-ai", "google_ai"):
        return "gemini"
    return "ollama"


def options_from_config(cfg: AppConfig | None = None) -> LlmOptions:
    cfg = cfg or load_config()
    provider = _normalize_provider(cfg.llm_provider)
    base_url = cfg.llm_base_url.strip().rstrip("/")
    model = cfg.llm_model.strip()
    api_key = cfg.llm_api_key.strip()

    if provider == "gemini":
        base_url = GEMINI_API_BASE
        if not model or "gemma" in model.lower():
            model = "gemini-2.0-flash"
        try:
            from backend.core.llm_capabilities import effective_cloud_api_key

            cloud_key = effective_cloud_api_key()
            if cloud_key:
                api_key = cloud_key
        except Exception:
            pass
    elif provider == "openai" and (not base_url or base_url.startswith("http://127.0.0.1")):
        base_url = "https://openrouter.ai/api/v1"

    return LlmOptions(
        provider=provider,
        base_url=base_url,
        model=model,
        max_tokens=max(256, cfg.llm_max_tokens),
        temperature=max(0.0, min(2.0, float(cfg.llm_temperature))),
        api_key=api_key,
    )


def _auth_headers(api_key: str) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def _openai_api_base(base: str) -> str:
    if base.endswith("/v1"):
        return base
    return f"{base}/v1"


def llm_reachable(opts: LlmOptions | None = None) -> bool:
    cfg = load_config()
    if not cfg.llm_enabled:
        return False
    opts = opts or options_from_config(cfg)
    cache_key = f"{opts.provider}|{opts.base_url}"
    now = time.monotonic()
    with _LLM_REACHABLE_LOCK:
        cached = _LLM_REACHABLE_CACHE.get(cache_key)
        if cached and now - cached[0] < _LLM_REACHABLE_TTL_SEC:
            _agent_llm_log(True, "cache")
            return cached[1]
        _agent_llm_log(False, "network")
        try:
            with httpx.Client(timeout=4.0) as client:
                if opts.provider == "lmstudio":
                    url = f"{opts.base_url}/api/v1/models"
                elif opts.provider == "openai":
                    url = f"{_openai_api_base(opts.base_url)}/models"
                elif opts.provider == "gemini":
                    url = f"{GEMINI_API_BASE}/models"
                    res = client.get(url, headers=_gemini_auth_headers(opts.api_key))
                    res.raise_for_status()
                    ok = True
                    _LLM_REACHABLE_CACHE[cache_key] = (now, ok)
                    return ok
                else:
                    url = f"{opts.base_url}/api/tags"
                res = client.get(url, headers=_auth_headers(opts.api_key))
                res.raise_for_status()
            ok = True
        except Exception:
            ok = False
        _LLM_REACHABLE_CACHE[cache_key] = (now, ok)
        return ok


def llm_available(cfg: AppConfig | None = None) -> bool:
    cfg = cfg or load_config()
    if not cfg.llm_enabled:
        return False
    try:
        from transcript_studio.gateway_llm import gateway_reachable, uses_gateway

        if uses_gateway(cfg) and gateway_reachable():
            return True
    except Exception:
        pass
    opts = options_from_config(cfg)
    if opts.provider == "gemini":
        try:
            from backend.core.llm_capabilities import effective_cloud_api_key

            return bool(effective_cloud_api_key())
        except Exception:
            return bool(opts.api_key and opts.api_key.lower() not in ("lm-studio", "lm_studio"))
    return bool(opts.base_url.strip())


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
    for key in ("response", "content", "text"):
        val = data.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return None


def _lmstudio_generate(prompt: str, *, opts: LlmOptions, timeout: float) -> str | None:
    payload: dict = {
        "model": opts.model,
        "input": prompt,
        "temperature": opts.temperature,
    }
    if opts.max_tokens:
        payload["max_output_tokens"] = opts.max_tokens
    url = f"{opts.base_url}/api/v1/chat"
    try:
        with httpx.Client(timeout=timeout) as client:
            res = client.post(url, headers=_auth_headers(opts.api_key), json=payload)
            res.raise_for_status()
            return _parse_lmstudio_output(res.json())
    except Exception as exc:
        log.warning("LM Studio request failed: %s", exc)
        return None


def _openai_generate(prompt: str, *, opts: LlmOptions, timeout: float) -> str | None:
    payload = {
        "model": opts.model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": opts.temperature,
        "max_tokens": opts.max_tokens,
        "stream": False,
    }
    url = f"{_openai_api_base(opts.base_url)}/chat/completions"
    try:
        with httpx.Client(timeout=timeout) as client:
            res = client.post(url, headers=_auth_headers(opts.api_key), json=payload)
            res.raise_for_status()
            data = res.json()
        choices = data.get("choices") or []
        if not choices:
            return None
        return (choices[0].get("message") or {}).get("content", "").strip() or None
    except Exception as exc:
        log.warning("OpenAI-compatible request failed: %s", exc)
        return None


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


def _gemini_generate(prompt: str, *, opts: LlmOptions, timeout: float) -> str | None:
    if not opts.api_key:
        log.warning("Gemini API key missing — set LLM_CLOUD_API_KEY in repo .env or LLM_API_KEY override")
        return None
    model = opts.model.strip() or "gemini-2.0-flash"
    if model.startswith("models/"):
        model = model[7:]
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": opts.temperature,
            "maxOutputTokens": opts.max_tokens or 8192,
        },
    }
    url = f"{GEMINI_API_BASE}/models/{model}:generateContent"
    try:
        with httpx.Client(timeout=timeout) as client:
            res = client.post(url, headers=_gemini_auth_headers(opts.api_key), json=payload)
            res.raise_for_status()
            return _parse_gemini_output(res.json())
    except Exception as exc:
        log.warning("Gemini API request failed: %s", exc)
        return None


def _ollama_generate(prompt: str, *, opts: LlmOptions, timeout: float) -> str | None:
    payload = {
        "model": opts.model,
        "prompt": prompt,
        "stream": False,
        "keep_alive": -1,
        "options": {"temperature": opts.temperature, "num_predict": opts.max_tokens},
    }
    try:
        with httpx.Client(timeout=timeout) as client:
            res = client.post(f"{opts.base_url}/api/generate", json=payload)
            res.raise_for_status()
            return (res.json().get("response") or "").strip() or None
    except Exception as exc:
        log.warning("Ollama request failed: %s", exc)
        return None


def generate(
    prompt: str,
    *,
    opts: LlmOptions | None = None,
    timeout: float = 180.0,
    use_cache: bool = True,
) -> str | None:
    if not llm_available():
        return None
    opts = opts or options_from_config()

    # --- Semantic cache lookup ---
    cfg = load_config()
    if use_cache and cfg.semantic_cache_enabled:
        try:
            from transcript_studio.semantic_cache import cache_lookup, cache_store  # noqa: PLC0415

            cached = cache_lookup(
                prompt,
                model=opts.model,
                temperature=opts.temperature,
                threshold=cfg.semantic_cache_threshold,
                max_age_days=cfg.semantic_cache_max_age_days,
            )
            if cached is not None:
                return cached
        except Exception:  # noqa: BLE001
            pass

    if opts.provider == "lmstudio":
        result = _lmstudio_generate(prompt, opts=opts, timeout=timeout)
    elif opts.provider == "openai":
        result = _openai_generate(prompt, opts=opts, timeout=timeout)
    elif opts.provider == "gemini":
        result = _gemini_generate(prompt, opts=opts, timeout=timeout)
    else:
        result = _ollama_generate(prompt, opts=opts, timeout=timeout)

    # --- Store in cache ---
    if use_cache and result and cfg.semantic_cache_enabled:
        try:
            cache_store(
                prompt,
                result,
                model=opts.model,
                temperature=opts.temperature,
            )
        except Exception:  # noqa: BLE001
            pass

    return result
