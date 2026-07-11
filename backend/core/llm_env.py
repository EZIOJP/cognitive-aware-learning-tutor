"""LLM environment status for the AI Control Center UI."""

from __future__ import annotations

import os
import re
from typing import Any

from backend.config import get_settings
from backend.core.llm_gateway import TASK_DEFAULTS
from backend.core.llm_routes import load_route_profiles
from backend.core.env_store import ALLOWED_ENV_KEYS, ENV_PATH, read_env_lines

_ENV_LINE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$")
_LOCAL_PLACEHOLDERS = frozenset(
    {
        "lm-studio",
        "lm_studio",
        "changeme",
        "change-me",
        "your-key-here",
        "your-key-from-aistudio.google.com",
        '""',
        "''",
    }
)


def _unquote(raw: str) -> str:
    value = raw.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        value = value[1:-1]
    return value.strip()


def _parse_env_file_values() -> dict[str, str]:
    """Read key values from disk .env (source of truth for the Control Center)."""
    out: dict[str, str] = {}
    if not ENV_PATH.is_file():
        return out
    for line in read_env_lines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        m = _ENV_LINE.match(line)
        if not m:
            continue
        out[m.group(1)] = _unquote(m.group(2))
    return out


def _key_status(value: str) -> dict[str, Any]:
    trimmed = (value or "").strip()
    if not trimmed:
        return {"configured": False, "hint": None}
    lower = trimmed.lower()
    if lower in _LOCAL_PLACEHOLDERS and lower not in {"lm-studio", "lm_studio"}:
        return {"configured": False, "hint": None}
    hint = f"…{trimmed[-4:]}" if len(trimmed) > 4 else "****"
    return {"configured": True, "hint": hint}


def _resolve_key(*candidates: str) -> str:
    for c in candidates:
        if (c or "").strip():
            return c.strip()
    return ""


def get_llm_env_status() -> dict[str, Any]:
    s = get_settings()
    file_vals = _parse_env_file_values()

    def from_sources(*names: str, settings_attr: str | None = None) -> str:
        parts: list[str] = []
        if settings_attr:
            parts.append(str(getattr(s, settings_attr, "") or ""))
        for name in names:
            parts.append(file_vals.get(name, ""))
            parts.append(os.environ.get(name, "") or "")
        return _resolve_key(*parts)

    gemini = from_sources("LLM_CLOUD_API_KEY", "GEMINI_API_KEY", settings_attr="llm_cloud_api_key")
    return {
        "ollama_enabled": s.ollama_enabled,
        "route_profile": (
            file_vals.get("LLM_ROUTE_PROFILE")
            or os.environ.get("LLM_ROUTE_PROFILE")
            or s.llm_route_profile
            or "local"
        ),
        "route_profiles": sorted(load_route_profiles().keys()),
        "default_tier": s.llm_default_tier or "medium",
        "local": {
            "provider": s.llm_provider,
            "base_url": s.ollama_url,
            "model": s.ollama_model,
        },
        "keys": {
            "llm_cloud_api_key": _key_status(
                from_sources("LLM_CLOUD_API_KEY", settings_attr="llm_cloud_api_key")
            ),
            "gemini_api_key": _key_status(gemini),
            "groq_api_key": _key_status(
                from_sources("GROQ_API_KEY", settings_attr="groq_api_key")
            ),
            "cerebras_api_key": _key_status(
                from_sources("CEREBRAS_API_KEY", settings_attr="cerebras_api_key")
            ),
            "mistral_api_key": _key_status(
                from_sources("MISTRAL_API_KEY", settings_attr="mistral_api_key")
            ),
            "github_token": _key_status(
                from_sources("GITHUB_TOKEN", settings_attr="github_token")
            ),
            "llm_api_key": _key_status(
                from_sources("LLM_API_KEY", settings_attr="llm_api_key")
            ),
            "llm_anthropic_api_key": _key_status(
                from_sources("LLM_ANTHROPIC_API_KEY", settings_attr="llm_anthropic_api_key")
            ),
            "llm_openrouter_api_key": _key_status(
                from_sources("LLM_OPENROUTER_API_KEY", settings_attr="llm_openrouter_api_key")
            ),
            "nim_api_key": _key_status(
                from_sources("NIM_API_KEY", settings_attr="nim_api_key")
            ),
            "tavily_api_key": _key_status(
                from_sources("TAVILY_API_KEY", settings_attr="tavily_api_key")
            ),
        },
        "env_file": str(ENV_PATH),
        "env_file_exists": ENV_PATH.is_file(),
        "allowed_env_keys": sorted(ALLOWED_ENV_KEYS),
        "task_defaults": {task: tier for task, (tier, _req) in TASK_DEFAULTS.items()},
    }
