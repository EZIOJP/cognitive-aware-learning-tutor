"""Tests for tier-based LLM gateway."""

from unittest.mock import MagicMock, patch

from backend.core.llm_capabilities import LlmRequirements, capability_filter, filter_configured_entries
from backend.core.llm_gateway import gateway_chain_status, llm_complete, require_gateway_chain
from backend.core.llm_job_context import get_job_context, llm_job
from backend.core.llm_tiers import ChainEntry, parse_chain_entry
from backend.core.ollama_client import LlmOptions, LlmTransportError, TransportResult


def test_parse_chain_entry_model_with_colon():
    entry = parse_chain_entry("ollama:llama3.2:3b")
    assert entry is not None
    assert entry.provider == "ollama"
    assert entry.model == "llama3.2:3b"


def test_parse_chain_entry_openai_url():
    entry = parse_chain_entry("openai:https://api.anthropic.com/v1:claude-3-5-sonnet")
    assert entry is not None
    assert entry.provider == "openai"
    assert entry.base_url == "https://api.anthropic.com/v1"
    assert entry.model == "claude-3-5-sonnet"


def test_parse_chain_entry_openrouter_alias():
    entry = parse_chain_entry("openrouter:https://openrouter.ai/api/v1:openai/gpt-4o-mini")
    assert entry is not None
    assert entry.provider == "openrouter"
    assert entry.base_url == "https://openrouter.ai/api/v1"
    assert entry.model == "openai/gpt-4o-mini"


def test_parse_chain_entry_groq_shorthand():
    entry = parse_chain_entry("groq:llama-3.1-8b-instant")
    assert entry is not None
    assert entry.provider == "groq"
    assert entry.model == "llama-3.1-8b-instant"


def test_capability_filter_json_schema():
    chain = [
        ChainEntry(provider="gemini", model="gemini-2.0-flash"),
        ChainEntry(provider="ollama", model="llama3.2:3b"),
    ]
    filtered = capability_filter(chain, LlmRequirements(needs_json_schema=True))
    assert len(filtered) == 1
    assert filtered[0].provider == "ollama"


@patch("backend.core.llm_gateway.get_settings")
@patch("backend.core.llm_gateway._settings")
@patch("backend.core.llm_gateway.get_chain_for_tier")
@patch("backend.core.llm_gateway.ollama_generate_transport")
def test_chain_fallback_on_rate_limit(mock_transport, mock_chain_for_tier, mock_settings, mock_get_settings):
    settings = MagicMock()
    settings.ollama_enabled = True
    settings.llm_default_tier = "medium"
    settings.llm_context_char_limit = 120_000
    settings.llm_max_tokens = 8192
    settings.llm_api_key = ""
    settings.llm_cloud_api_key = ""
    settings.llm_anthropic_api_key = ""
    settings.llm_route_profile = "hybrid"
    settings.ollama_url = "http://127.0.0.1:1234"
    mock_settings.return_value = settings
    mock_get_settings.return_value = settings

    mock_chain_for_tier.return_value = [
        ChainEntry(provider="gemini", model="gemini-2.0-flash"),
        ChainEntry(provider="lmstudio", model="google/gemma-4-e4b", base_url="http://127.0.0.1:1234"),
    ]

    mock_transport.side_effect = [
        TransportResult(error=LlmTransportError.RATE_LIMIT, latency_ms=10),
        TransportResult(error=LlmTransportError.RATE_LIMIT, latency_ms=11),
        TransportResult(text="local notes", latency_ms=20),
    ]

    result = llm_complete("prompt", task="generic", tier="medium")
    assert result.text == "local notes"
    assert result.fallback_used is True
    assert result.provider == "lmstudio"


@patch("backend.core.llm_gateway.get_settings")
@patch("backend.core.llm_gateway._settings")
@patch("backend.core.llm_gateway.get_chain_for_tier")
@patch("backend.core.llm_gateway.ollama_generate_transport")
def test_context_too_long_no_fallback(mock_transport, mock_chain_for_tier, mock_settings, mock_get_settings):
    settings = MagicMock()
    settings.ollama_enabled = True
    settings.llm_default_tier = "medium"
    settings.llm_context_char_limit = 10
    settings.llm_max_tokens = 8192
    settings.llm_api_key = ""
    settings.llm_cloud_api_key = ""
    settings.llm_anthropic_api_key = ""
    settings.llm_route_profile = "hybrid"
    settings.ollama_url = "http://127.0.0.1:1234"
    mock_settings.return_value = settings
    mock_get_settings.return_value = settings

    mock_chain_for_tier.return_value = [
        ChainEntry(provider="gemini", model="gemini-2.0-flash"),
        ChainEntry(provider="lmstudio", model="google/gemma-4-e4b"),
    ]

    result = llm_complete("x" * 50, task="generic", tier="medium")
    assert result.text is None
    assert result.error == "context_too_long"
    mock_transport.assert_not_called()


@patch("backend.core.llm_gateway._settings")
@patch("backend.core.llm_gateway.get_chain_for_tier")
def test_job_sticky_tier(mock_chain_for_tier, mock_settings):
    settings = MagicMock()
    settings.ollama_enabled = True
    settings.llm_default_tier = "medium"
    settings.llm_context_char_limit = 120_000
    mock_settings.return_value = settings
    mock_chain_for_tier.return_value = [ChainEntry(provider="lmstudio", model="m", base_url="http://127.0.0.1:1234")]

    with llm_job(tier="heavy", task="notes_job"):
        assert get_job_context() is not None
        assert get_job_context().tier == "heavy"


@patch("backend.core.llm_gateway._settings")
@patch("backend.core.llm_gateway.get_chain_for_tier")
@patch("backend.core.llm_gateway.ollama_generate_transport")
def test_legacy_llm_override_single_chain(mock_transport, mock_chain_for_tier, mock_settings):
    settings = MagicMock()
    settings.ollama_enabled = True
    mock_settings.return_value = settings

    mock_transport.return_value = TransportResult(text="override ok", latency_ms=5)
    override = LlmOptions(provider="lmstudio", base_url="http://127.0.0.1:1234", model="test-model")

    result = llm_complete("prompt", llm=override)
    assert result.text == "override ok"
    assert result.tier == "custom"
    mock_chain_for_tier.assert_not_called()


@patch("backend.core.llm_gateway.get_settings")
@patch("backend.core.llm_gateway._settings")
@patch("backend.core.llm_gateway.get_chain_for_tier")
@patch("backend.core.llm_gateway.ollama_generate_transport")
def test_usage_metadata_passthrough(mock_transport, mock_chain_for_tier, mock_settings, mock_get_settings):
    settings = MagicMock()
    settings.ollama_enabled = True
    settings.llm_default_tier = "medium"
    settings.llm_context_char_limit = 120_000
    settings.llm_max_tokens = 8192
    settings.llm_api_key = ""
    settings.llm_cloud_api_key = ""
    settings.llm_anthropic_api_key = ""
    settings.ollama_url = "http://127.0.0.1:1234"
    settings.llm_route_profile = "hybrid"
    mock_settings.return_value = settings
    mock_get_settings.return_value = settings
    mock_chain_for_tier.return_value = [ChainEntry(provider="openai", model="openai/gpt-4o-mini")]
    mock_transport.return_value = TransportResult(
        text="ok",
        latency_ms=42,
        prompt_tokens=100,
        completion_tokens=50,
        total_tokens=150,
        generation_id="gen_123",
        upstream_provider="openrouter/auto",
        estimated_cost=0.0015,
    )

    result = llm_complete("prompt", task="generic", tier="medium", route_profile="hybrid")
    assert result.text == "ok"
    assert result.route_profile == "hybrid"
    assert result.total_tokens == 150
    assert result.generation_id == "gen_123"
    assert result.upstream_provider == "openrouter/auto"
    assert result.estimated_cost == 0.0015


@patch("backend.config.get_settings")
def test_filter_configured_entries_skips_openrouter_without_key(mock_settings):
    settings = MagicMock()
    settings.llm_openrouter_api_key = ""
    settings.llm_anthropic_api_key = ""
    settings.nim_api_key = ""
    settings.llm_cloud_api_key = ""
    settings.llm_api_key = "lm-studio"
    settings.ollama_url = "http://127.0.0.1:1234"
    settings.llm_max_tokens = 8192
    mock_settings.return_value = settings

    chain = [
        ChainEntry(
            provider="openai",
            model="openai/gpt-4o-mini",
            base_url="https://openrouter.ai/api/v1",
        ),
        ChainEntry(provider="lmstudio", model="google/gemma-4-e4b", base_url="http://127.0.0.1:1234"),
    ]
    filtered = filter_configured_entries(chain)
    assert len(filtered) == 1
    assert filtered[0].provider == "lmstudio"


@patch("backend.core.llm_gateway.llm_reachable")
@patch("backend.core.llm_gateway.get_chain_for_tier")
@patch("backend.core.llm_gateway._settings")
def test_require_gateway_chain_fails_with_actionable_message(
    mock_settings,
    mock_chain_for_tier,
    mock_reachable,
):
    settings = MagicMock()
    settings.ollama_enabled = True
    settings.llm_default_tier = "medium"
    mock_settings.return_value = settings
    mock_chain_for_tier.return_value = [
        ChainEntry(provider="lmstudio", model="google/gemma-4-e4b", base_url="http://127.0.0.1:1234"),
    ]
    mock_reachable.return_value = False

    try:
        require_gateway_chain("medium", task="notes_job")
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        msg = str(exc)
        assert "notes_job" in msg
        assert "LM Studio" in msg
        assert gateway_chain_status("medium", task="notes_job")["reachable"] is False


@patch("backend.core.llm_gateway.get_settings")
@patch("backend.core.llm_gateway._settings")
@patch("backend.core.llm_gateway.get_chain_for_tier")
@patch("backend.core.llm_gateway.ollama_generate_transport")
def test_quota_cooldown_skips_dead_provider_on_next_call(
    mock_transport, mock_chain_for_tier, mock_settings, mock_get_settings
):
    """402/quota must not re-hit the dead provider every request — long auto-skip."""
    from backend.core.llm_gateway import clear_cloud_cooldowns

    clear_cloud_cooldowns()
    settings = MagicMock()
    settings.ollama_enabled = True
    settings.llm_default_tier = "medium"
    settings.llm_context_char_limit = 120_000
    settings.llm_max_tokens = 8192
    settings.llm_api_key = ""
    settings.llm_cloud_api_key = ""
    settings.llm_anthropic_api_key = ""
    settings.llm_route_profile = "hybrid-free"
    settings.ollama_url = "http://127.0.0.1:1234"
    mock_settings.return_value = settings
    mock_get_settings.return_value = settings

    mock_chain_for_tier.return_value = [
        ChainEntry(provider="gemini", model="gemini-3.1-flash-lite"),
        ChainEntry(provider="lmstudio", model="google/gemma-4-e4b", base_url="http://127.0.0.1:1234"),
    ]

    mock_transport.side_effect = [
        TransportResult(error=LlmTransportError.QUOTA, latency_ms=10),
        TransportResult(text="local ok", latency_ms=20),
        TransportResult(text="local again", latency_ms=15),
    ]

    first = llm_complete("prompt", task="generic", tier="medium")
    assert first.text == "local ok"
    assert first.fallback_used is True
    assert first.provider == "lmstudio"

    second = llm_complete("prompt", task="generic", tier="medium")
    assert second.text == "local again"
    assert second.provider == "lmstudio"
    # Gemini attempted once then cooled down; LM Studio twice
    assert mock_transport.call_count == 3
    clear_cloud_cooldowns()
