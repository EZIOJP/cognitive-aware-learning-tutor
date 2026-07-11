"""Provider capability flags for tier-chain routing."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from backend.core.ollama_client import LlmOptions, _normalize_provider
from backend.core.llm_tiers import ChainEntry

log = logging.getLogger(__name__)

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


def _lmstudio_base_url() -> str:
    from backend.config import get_settings

    s = get_settings()
    explicit = (getattr(s, "lmstudio_url", "") or "").strip().rstrip("/")
    if explicit:
        return explicit
    if s.llm_provider.strip().lower() in ("lmstudio", "lm-studio", "lm_studio"):
        return s.ollama_url.strip().rstrip("/")
    return "http://127.0.0.1:1234"


def _ollama_native_base_url(entry_base: str | None) -> str:
    if entry_base:
        return entry_base.strip().rstrip("/")
    from backend.config import get_settings

    s = get_settings()
    native = (getattr(s, "ollama_native_url", "") or "").strip().rstrip("/")
    return native or "http://127.0.0.1:11434"


def _settings_api_key(name: str) -> str:
    from backend.config import get_settings

    s = get_settings()
    mapping = {
        "GROQ_API_KEY": getattr(s, "groq_api_key", ""),
        "CEREBRAS_API_KEY": getattr(s, "cerebras_api_key", ""),
        "MISTRAL_API_KEY": getattr(s, "mistral_api_key", ""),
        "GITHUB_TOKEN": getattr(s, "github_token", ""),
        "LLM_OPENROUTER_API_KEY": s.llm_openrouter_api_key,
        "NIM_API_KEY": s.nim_api_key,
        "LLM_ANTHROPIC_API_KEY": s.llm_anthropic_api_key,
    }
    return (mapping.get(name) or "").strip()


def entry_to_options(entry: ChainEntry) -> LlmOptions:
    from backend.config import get_settings
    from backend.core.llm_providers import resolve_openai_compat

    s = get_settings()
    raw_provider = entry.provider.strip().lower()
    provider = _normalize_provider(entry.provider)
    compat = resolve_openai_compat(raw_provider)

    if provider == "gemini":
        from backend.core.ollama_client import GEMINI_API_BASE

        base = entry.base_url or GEMINI_API_BASE
        api_key = (entry.api_key or effective_cloud_api_key()).strip()
    elif provider == "lmstudio":
        base = entry.base_url or _lmstudio_base_url()
        api_key = entry.api_key or s.llm_api_key.strip()
    elif provider == "ollama":
        base = _ollama_native_base_url(entry.base_url)
        api_key = entry.api_key or s.llm_api_key.strip() or "ollama"
    elif compat is not None:
        base = entry.base_url or compat.base_url
        api_key = (entry.api_key or "").strip()
        if not api_key:
            for env_key in compat.env_keys:
                api_key = _settings_api_key(env_key)
                if api_key:
                    break
    elif provider == "openai":
        base = (entry.base_url or s.ollama_url).strip().rstrip("/")
        if "integrate.api.nvidia.com" in base.lower():
            api_key = (entry.api_key or s.nim_api_key or "").strip()
        elif "openrouter.ai" in base.lower():
            api_key = (entry.api_key or s.llm_openrouter_api_key.strip()).strip()
        else:
            api_key = (
                entry.api_key
                or s.llm_anthropic_api_key.strip()
                or effective_cloud_api_key()
            ).strip()
    else:
        base = _ollama_native_base_url(entry.base_url)
        api_key = entry.api_key or s.llm_api_key.strip()

    return LlmOptions(
        provider=provider,
        base_url=base,
        model=entry.model,
        max_tokens=max(256, s.llm_max_tokens),
        api_key=api_key,
    )


def entry_is_configured(entry: ChainEntry) -> bool:
    """Skip cloud providers that cannot authenticate — avoids 401 spam in fallback chains."""
    from backend.config import get_settings
    from backend.core.llm_providers import resolve_openai_compat

    s = get_settings()
    raw_provider = entry.provider.strip().lower()
    provider = _normalize_provider(entry.provider)
    base = (entry.base_url or "").lower()
    compat = resolve_openai_compat(raw_provider)

    if provider == "gemini":
        return bool(effective_cloud_api_key())
    if compat is not None:
        if entry.api_key and entry.api_key.strip():
            return True
        for env_key in compat.env_keys:
            if _settings_api_key(env_key):
                return True
        return False
    if provider == "openai":
        if "openrouter.ai" in base:
            return bool((entry.api_key or s.llm_openrouter_api_key or "").strip())
        if "integrate.api.nvidia.com" in base:
            return bool((entry.api_key or s.nim_api_key or "").strip())
        if "anthropic.com" in base:
            return bool((entry.api_key or s.llm_anthropic_api_key or "").strip())
        if "127.0.0.1" in base or "localhost" in base:
            return True
        return bool(
            (entry.api_key or s.llm_anthropic_api_key or effective_cloud_api_key() or "").strip()
        )
    return True


def filter_configured_entries(chain: list[ChainEntry]) -> list[ChainEntry]:
    kept: list[ChainEntry] = []
    skipped: list[str] = []
    for entry in chain:
        if entry_is_configured(entry):
            kept.append(entry)
        else:
            skipped.append(f"{entry.provider}:{entry.model}")
    if skipped:
        # Debug only — this ran on every LLM call and flooded logs.
        log.debug("Skipping unconfigured LLM chain entries: %s", ", ".join(skipped))
    return kept


def is_cloud_provider(provider: str) -> bool:
    from backend.core.llm_providers import OPENAI_COMPAT_ALIASES

    name = _normalize_provider(provider)
    raw = provider.strip().lower()
    return name in ("gemini", "openai") or raw in OPENAI_COMPAT_ALIASES
