"""Provider capability flags for tier-chain routing."""

from __future__ import annotations

from dataclasses import dataclass

from backend.core.ollama_client import LlmOptions, _normalize_provider
from backend.core.llm_tiers import ChainEntry

PROVIDER_CAPS: dict[str, dict[str, bool]] = {
    "ollama": {"supports_json_schema": True, "supports_system_prompt": False},
    "lmstudio": {"supports_json_schema": False, "supports_system_prompt": True},
    "gemini": {"supports_json_schema": False, "supports_system_prompt": True},
    "openai": {"supports_json_schema": False, "supports_system_prompt": True},
}


@dataclass(frozen=True)
class LlmRequirements:
    needs_json_schema: bool = False
    needs_system_prompt: bool = False
    max_prompt_chars: int | None = None


def provider_supports(provider: str, key: str) -> bool:
    caps = PROVIDER_CAPS.get(_normalize_provider(provider), {})
    return bool(caps.get(key, False))


def capability_filter(
    chain: list[ChainEntry],
    requirements: LlmRequirements | None,
) -> list[ChainEntry]:
    if not requirements:
        return chain
    filtered: list[ChainEntry] = []
    for entry in chain:
        provider = _normalize_provider(entry.provider)
        if requirements.needs_json_schema and not provider_supports(provider, "supports_json_schema"):
            continue
        if requirements.needs_system_prompt and not provider_supports(provider, "supports_system_prompt"):
            continue
        filtered.append(entry)
    return filtered


_LOCAL_API_KEY_PLACEHOLDERS = frozenset(
    {"lm-studio", "lm_studio", "changeme", "change-me", "your-key-here", "your-key-from-aistudio.google.com"}
)


def effective_cloud_api_key() -> str:
    """Real cloud key only — never LM Studio placeholder from LLM_API_KEY."""
    import os

    from backend.config import get_settings

    s = get_settings()
    for candidate in (
        s.llm_cloud_api_key,
        os.environ.get("GEMINI_API_KEY", ""),
        os.environ.get("LLM_CLOUD_API_KEY", ""),
    ):
        key = (candidate or "").strip()
        if key and key.lower() not in _LOCAL_API_KEY_PLACEHOLDERS:
            return key
    return ""


def entry_to_options(entry: ChainEntry) -> LlmOptions:
    from backend.config import get_settings

    s = get_settings()
    provider = _normalize_provider(entry.provider)
    if provider == "gemini":
        from backend.core.ollama_client import GEMINI_API_BASE

        base = entry.base_url or GEMINI_API_BASE
        api_key = (entry.api_key or effective_cloud_api_key()).strip()
    elif provider == "openai":
        base = (entry.base_url or s.ollama_url).strip().rstrip("/")
        if "openrouter.ai" in base.lower():
            api_key = (
                entry.api_key
                or s.llm_openrouter_api_key.strip()
                or effective_cloud_api_key()
            ).strip()
        else:
            api_key = (
                entry.api_key
                or s.llm_anthropic_api_key.strip()
                or effective_cloud_api_key()
            ).strip()
    elif provider == "lmstudio":
        base = (entry.base_url or s.ollama_url).strip().rstrip("/")
        api_key = entry.api_key or s.llm_api_key.strip()
    else:
        base = (entry.base_url or s.ollama_url).strip().rstrip("/")
        if provider == "ollama" and s.llm_provider == "ollama":
            base = s.ollama_url.strip().rstrip("/")
        api_key = entry.api_key or s.llm_api_key.strip()

    return LlmOptions(
        provider=provider,
        base_url=base,
        model=entry.model,
        max_tokens=max(256, s.llm_max_tokens),
        api_key=api_key,
    )


def is_cloud_provider(provider: str) -> bool:
    return _normalize_provider(provider) in ("gemini", "openai")
