"""Studio bridge to the repo AI handler (backend/core/llm_gateway.py)."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.core.ollama_client import LlmOptions as BackendLlmOptions
    from transcript_studio.config import AppConfig
    from transcript_studio.llm_client import LlmOptions

_GATEWAY_PROVIDERS = frozenset({"auto", "gateway", ""})
_CLOUD_PROVIDERS = frozenset({"gemini", "openai", "google", "openrouter", "or"})


def uses_gateway(cfg: AppConfig) -> bool:
    provider = cfg.llm_provider.strip().lower()
    if provider in _CLOUD_PROVIDERS:
        return True
    if getattr(cfg, "llm_use_gateway", True) is False and provider in ("lmstudio", "ollama"):
        return False
    return provider in _GATEWAY_PROVIDERS or getattr(cfg, "llm_use_gateway", True)


def default_llm_tier(cfg: AppConfig) -> str:
    tier = getattr(cfg, "llm_tier", "").strip().lower()
    if tier in ("light", "medium", "heavy"):
        return tier
    try:
        from backend.config import get_settings

        return (get_settings().llm_default_tier or "medium").strip().lower()
    except Exception:
        return "medium"


def to_backend_llm(opts: LlmOptions | None) -> BackendLlmOptions | None:
    from backend.core.ollama_client import LlmOptions as BackendLlmOptions

    if opts is None:
        return None
    return BackendLlmOptions(
        provider=opts.provider,
        base_url=opts.base_url,
        model=opts.model,
        max_tokens=opts.max_tokens,
        api_key=opts.api_key or None,
    )


def resolve_for_generate(
    cfg: AppConfig,
    opts: LlmOptions | None = None,
) -> tuple[BackendLlmOptions | None, str]:
    """Return (llm_override_or_none, llm_tier) for generate calls."""
    tier = default_llm_tier(cfg)
    if uses_gateway(cfg) and opts is None:
        return None, tier
    from transcript_studio.llm_client import options_from_config

    llm_opts = opts or options_from_config(cfg)
    return to_backend_llm(llm_opts), tier


def gateway_reachable() -> bool:
    try:
        from backend.core.llm_gateway import gateway_available

        return bool(gateway_available())
    except Exception:
        return False


def llm_generate_available(cfg: AppConfig) -> bool:
    if not cfg.llm_enabled:
        return False
    if gateway_reachable():
        return True
    if not uses_gateway(cfg):
        from transcript_studio.llm_client import llm_available

        return llm_available(cfg)
    return False


def llm_generate_reachable(cfg: AppConfig) -> bool:
    if gateway_reachable():
        return True
    if not uses_gateway(cfg):
        from transcript_studio.llm_client import llm_reachable, options_from_config

        return llm_reachable(options_from_config(cfg))
    return False


def llm_preflight_error(cfg: AppConfig) -> str | None:
    if llm_generate_reachable(cfg):
        return None
    try:
        from transcript_studio.paths import repo_root

        env_path = repo_root() / ".env"
    except Exception:
        env_path = Path(".env")
    provider = cfg.llm_provider.strip().lower()
    if provider in _CLOUD_PROVIDERS or uses_gateway(cfg):
        return (
            f"No LLM provider reachable. For Gemini cloud, add your API key once to:\n"
            f"  {env_path}\n"
            f"  LLM_CLOUD_API_KEY=your-key-from-aistudio.google.com\n"
            f"Or start LM Studio locally (tier chain falls back to lmstudio).\n"
            f"Studio provider should be 'auto' or 'gemini' — not manual URL with lm-studio key."
        )
    return (
        "LLM not reachable. Start LM Studio/Ollama, or switch Provider to auto/gemini "
        "and set LLM_CLOUD_API_KEY in repo .env."
    )


def gateway_status_line(cfg: AppConfig) -> str:
    tier = default_llm_tier(cfg)
    ok = gateway_reachable()
    provider_hint = ""
    try:
        from backend.core.llm_capabilities import entry_to_options, effective_cloud_api_key
        from backend.core.llm_routes import get_chain_for_tier
        from backend.core.ollama_client import llm_reachable

        for entry in get_chain_for_tier(tier):
            if llm_reachable(entry_to_options(entry)):
                provider_hint = f"{entry.provider}:{entry.model}"
                break
        if not provider_hint and not effective_cloud_api_key():
            provider_hint = "gemini: (add LLM_CLOUD_API_KEY to repo .env)"
    except Exception:
        provider_hint = ""
    state = "reachable" if ok else "offline"
    if provider_hint:
        return f"AI handler ({tier}): {state} — {provider_hint}"
    return f"AI handler ({tier}): {state}"


def make_gateway_generate_fn(
    *,
    llm: BackendLlmOptions | None,
    llm_tier: str,
    task: str = "notes_chunk",
    timeout: float = 300.0,
):
    from backend.core.ollama_client import ollama_generate

    def _generate(prompt: str) -> str | None:
        return ollama_generate(
            prompt,
            timeout=timeout,
            llm=llm,
            tier=llm_tier,
            task=task,
        )

    return _generate
