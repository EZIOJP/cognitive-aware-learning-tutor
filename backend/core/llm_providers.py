"""Known OpenAI-compatible cloud providers for tier chains (see docs/LLM_GATEWAY.md)."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class OpenAiCompatProvider:
    name: str
    base_url: str
    env_keys: tuple[str, ...]
    # False when chat URL is {base}/chat/completions (GitHub Models), not {base}/v1/...
    uses_v1_prefix: bool = True


OPENAI_COMPAT_PROVIDERS: dict[str, OpenAiCompatProvider] = {
    "groq": OpenAiCompatProvider(
        "groq",
        "https://api.groq.com/openai/v1",
        ("GROQ_API_KEY",),
    ),
    "cerebras": OpenAiCompatProvider(
        "cerebras",
        "https://api.cerebras.ai/v1",
        ("CEREBRAS_API_KEY",),
    ),
    "mistral": OpenAiCompatProvider(
        "mistral",
        "https://api.mistral.ai/v1",
        ("MISTRAL_API_KEY",),
    ),
    "github": OpenAiCompatProvider(
        "github",
        "https://models.github.ai/inference",
        ("GITHUB_TOKEN",),
        uses_v1_prefix=False,
    ),
    "openrouter": OpenAiCompatProvider(
        "openrouter",
        "https://openrouter.ai/api/v1",
        ("LLM_OPENROUTER_API_KEY", "OPENROUTER_API_KEY"),
    ),
    "deepseek": OpenAiCompatProvider(
        "deepseek",
        "https://api.deepseek.com/v1",
        ("DEEPSEEK_API_KEY",),
    ),
    "sambanova": OpenAiCompatProvider(
        "sambanova",
        "https://api.sambanova.ai/v1",
        ("SAMBANOVA_API_KEY",),
    ),
    "fireworks": OpenAiCompatProvider(
        "fireworks",
        "https://api.fireworks.ai/inference/v1",
        ("FIREWORKS_API_KEY",),
    ),
    "together": OpenAiCompatProvider(
        "together",
        "https://api.together.xyz/v1",
        ("TOGETHER_API_KEY",),
    ),
    "huggingface": OpenAiCompatProvider(
        "huggingface",
        "https://router.huggingface.co/v1",
        ("HF_TOKEN", "HUGGINGFACE_API_KEY"),
    ),
}

# Chain prefix aliases → openai transport + registry lookup
OPENAI_COMPAT_ALIASES = frozenset(OPENAI_COMPAT_PROVIDERS.keys()) | frozenset(
    {"or", "nvidia", "nim", "hf"}
)


def resolve_openai_compat(name: str) -> OpenAiCompatProvider | None:
    key = name.strip().lower()
    if key in ("or",):
        key = "openrouter"
    if key in ("nvidia", "nim"):
        return None
    return OPENAI_COMPAT_PROVIDERS.get(key)


def api_key_from_env(env_keys: tuple[str, ...]) -> str:
    for key in env_keys:
        val = (os.environ.get(key) or "").strip()
        if val:
            return val
    return ""


def chat_completions_url(base_url: str, *, uses_v1_prefix: bool = True) -> str:
    base = base_url.rstrip("/")
    if not uses_v1_prefix:
        return f"{base}/chat/completions"
    if base.endswith("/v1"):
        return f"{base}/chat/completions"
    return f"{base}/v1/chat/completions"
