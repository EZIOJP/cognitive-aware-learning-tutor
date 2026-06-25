"""Shared local LLM client — Ollama, LM Studio native v1, or OpenAI-compatible APIs."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class LlmOptions:
    provider: str | None = None
    base_url: str | None = None
    model: str | None = None
    max_tokens: int | None = None
    api_key: str | None = None


GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"


def _normalize_provider(raw: str) -> str:
    value = raw.strip().lower()
    if value in ("lmstudio", "lm-studio", "lm_studio"):
        return "lmstudio"
    if value in ("openai", "vllm"):
        return "openai"
    if value in ("gemini", "google", "google-ai", "google_ai"):
        return "gemini"
    return "ollama"


def _settings():
    from backend.config import get_settings

    return get_settings()


def resolve_llm_options(override: LlmOptions | None = None) -> LlmOptions:
    s = _settings()
    provider = _normalize_provider(s.llm_provider)
    default_base = GEMINI_API_BASE if provider == "gemini" else s.ollama_url.strip().rstrip("/")
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


def _auth_headers(api_key: str) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def llm_reachable(override: LlmOptions | None = None) -> bool:
    if not _settings().ollama_enabled and not _has_llm_override(override):
        return False
    opts = resolve_llm_options(override)
    try:
        with httpx.Client(timeout=8.0) as client:
            if opts.provider == "gemini":
                if not opts.api_key:
                    return False
                url = f"{GEMINI_API_BASE}/models"
                res = client.get(url, params={"key": opts.api_key})
                res.raise_for_status()
                return True
            if opts.provider == "lmstudio":
                url = f"{opts.base_url}/api/v1/models"
            elif opts.provider == "openai":
                url = f"{_openai_api_base(opts.base_url)}/models"
            else:
                url = f"{opts.base_url}/api/tags"
            res = client.get(url, headers=_auth_headers(opts.api_key or ""))
            res.raise_for_status()
        return True
    except Exception:
        return False


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
    opts = resolve_llm_options(override)
    if opts.provider == "gemini":
        return GEMINI_API_BASE if opts.api_key else None
    if _has_llm_override(override):
        return (override.base_url or "").strip().rstrip("/")
    if not _settings().ollama_enabled:
        return None
    return opts.base_url or None


def _openai_api_base(base: str) -> str:
    if base.endswith("/v1"):
        return base
    return f"{base}/v1"


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
) -> str | None:
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

    try:
        with httpx.Client(timeout=timeout) as client:
            res = client.post(url, headers=_auth_headers(opts.api_key or ""), json=payload)
            if res.status_code == 400 and payload.get("reasoning") is not None:
                payload.pop("reasoning", None)
                res = client.post(url, headers=_auth_headers(opts.api_key or ""), json=payload)
            res.raise_for_status()
            data = res.json()
        raw = _parse_lmstudio_output(data)
        return raw or None
    except Exception as exc:
        log.warning("LM Studio native API request failed: %s", exc)
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


def _gemini_generate(
    prompt: str,
    *,
    opts: LlmOptions,
    timeout: float,
    system_prompt: str | None = None,
) -> str | None:
    if not opts.api_key:
        log.warning("Gemini API key missing — set LLM_API_KEY in .env")
        return None

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

    try:
        with httpx.Client(timeout=timeout) as client:
            res = client.post(url, params={"key": opts.api_key}, json=payload)
            res.raise_for_status()
            data = res.json()
        raw = _parse_gemini_output(data)
        return raw or None
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 429:
            log.warning("Gemini rate limit (429) — use LM Studio locally or retry later")
        else:
            log.warning("Gemini API request failed: %s", exc)
        return None
    except Exception as exc:
        log.warning("Gemini API request failed: %s", exc)
        return None


def _openai_generate(
    prompt: str,
    *,
    opts: LlmOptions,
    timeout: float,
) -> str | None:
    payload = {
        "model": opts.model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.4,
        "max_tokens": opts.max_tokens or 8192,
        "stream": False,
    }
    url = f"{_openai_api_base(opts.base_url)}/chat/completions"

    try:
        with httpx.Client(timeout=timeout) as client:
            res = client.post(url, headers=_auth_headers(opts.api_key or ""), json=payload)
            res.raise_for_status()
            data = res.json()
        choices = data.get("choices") or []
        if not choices:
            return None
        msg = choices[0].get("message") or {}
        raw = (msg.get("content") or "").strip()
        return raw or None
    except Exception as exc:
        log.warning("OpenAI-compatible LLM request failed: %s", exc)
        return None


def _ollama_native_generate(
    prompt: str,
    *,
    opts: LlmOptions,
    timeout: float,
    json_schema: dict | None,
) -> str | None:
    payload: dict = {
        "model": opts.model,
        "prompt": prompt,
        "stream": False,
        "keep_alive": -1,
    }
    if json_schema:
        payload["format"] = json_schema

    try:
        with httpx.Client(timeout=timeout) as client:
            res = client.post(f"{opts.base_url}/api/generate", json=payload)
            res.raise_for_status()
            data = res.json()
        raw = data.get("response") or ""
        return raw.strip() or None
    except Exception as exc:
        log.warning("Ollama request failed: %s", exc)
        return None


def ollama_generate(
    prompt: str,
    *,
    model: str | None = None,
    timeout: float = 120.0,
    json_schema: dict | None = None,
    llm: LlmOptions | None = None,
    system_prompt: str | None = None,
) -> str | None:
    if not _settings().ollama_enabled and not _has_llm_override(llm):
        return None

    opts = resolve_llm_options(llm)
    if model:
        opts = LlmOptions(
            provider=opts.provider,
            base_url=opts.base_url,
            model=model.strip(),
            max_tokens=opts.max_tokens,
            api_key=opts.api_key,
        )

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
        return _openai_generate(prompt, opts=opts, timeout=timeout)
    return _ollama_native_generate(prompt, opts=opts, timeout=timeout, json_schema=json_schema)
