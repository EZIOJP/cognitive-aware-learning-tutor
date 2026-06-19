"""Local LLM client — Ollama, LM Studio, or OpenAI-compatible APIs."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

from transcript_studio.config import AppConfig, load_config

log = logging.getLogger(__name__)


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
    if value in ("openai", "vllm"):
        return "openai"
    return "ollama"


def options_from_config(cfg: AppConfig | None = None) -> LlmOptions:
    cfg = cfg or load_config()
    return LlmOptions(
        provider=_normalize_provider(cfg.llm_provider),
        base_url=cfg.llm_base_url.strip().rstrip("/"),
        model=cfg.llm_model.strip(),
        max_tokens=max(256, cfg.llm_max_tokens),
        temperature=max(0.0, min(2.0, float(cfg.llm_temperature))),
        api_key=cfg.llm_api_key.strip(),
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
    try:
        with httpx.Client(timeout=4.0) as client:
            if opts.provider == "lmstudio":
                url = f"{opts.base_url}/api/v1/models"
            elif opts.provider == "openai":
                url = f"{_openai_api_base(opts.base_url)}/models"
            else:
                url = f"{opts.base_url}/api/tags"
            res = client.get(url, headers=_auth_headers(opts.api_key))
            res.raise_for_status()
        return True
    except Exception:
        return False


def llm_available(cfg: AppConfig | None = None) -> bool:
    cfg = cfg or load_config()
    return bool(cfg.llm_enabled and cfg.llm_base_url.strip())


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


def generate(prompt: str, *, opts: LlmOptions | None = None, timeout: float = 180.0) -> str | None:
    if not llm_available():
        return None
    opts = opts or options_from_config()

    # --- Semantic cache lookup ---
    cfg = load_config()
    if cfg.semantic_cache_enabled:
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
    else:
        result = _ollama_generate(prompt, opts=opts, timeout=timeout)

    # --- Store in cache ---
    if result and cfg.semantic_cache_enabled:
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
