"""API key editing and connection tests for Notes Studio (writes repo .env)."""

from __future__ import annotations

from typing import Any

KEY_FIELDS: list[tuple[str, str]] = [
    ("LLM_CLOUD_API_KEY", "Cloud / Gemini"),
    ("GEMINI_API_KEY", "Gemini alias"),
    ("LLM_OPENROUTER_API_KEY", "OpenRouter"),
    ("LLM_ANTHROPIC_API_KEY", "Anthropic"),
    ("NIM_API_KEY", "NVIDIA NIM"),
    ("LLM_API_KEY", "LM Studio placeholder"),
    ("TAVILY_API_KEY", "Tavily search"),
]


def save_env_keys(updates: dict[str, str]) -> list[str]:
    from backend.core.env_store import patch_env

    return patch_env(updates)


def get_env_key_status() -> dict[str, Any]:
    from backend.core.llm_env import get_llm_env_status

    return get_llm_env_status()


def test_all_tiers(route_profile: str | None = None) -> dict[str, Any]:
    from backend.core.llm_probe import test_tier_chain

    out: dict[str, Any] = {}
    for tier in ("light", "medium", "heavy"):
        out[tier] = test_tier_chain(tier, route_profile=route_profile)
    return out
