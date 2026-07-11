"""OpenRouter advanced routing features."""

from unittest.mock import MagicMock, patch

from backend.core.llm_capabilities import LlmRequirements
from backend.core.llm_tiers import ChainEntry, parse_chain_entry
from backend.core.openrouter_routing import (
    build_openrouter_payload,
    is_openrouter_entry,
    iter_chain_segments,
    normalize_session_id,
    openrouter_models_from_entries,
    openrouter_request_headers,
    parse_openrouter_response,
    provider_prefs_for_request,
    response_cache_enabled_for_task,
    service_tier_for_task,
)


def test_is_openrouter_entry_shorthand():
    entry = parse_chain_entry("openrouter:openai/gpt-4o-mini")
    assert entry is not None
    assert is_openrouter_entry(entry)


def test_iter_chain_segments_groups_openrouter():
    chain = [
        ChainEntry(provider="groq", model="llama-3.1-8b-instant"),
        ChainEntry(provider="openrouter", model="openai/gpt-4o-mini"),
        ChainEntry(provider="openrouter", model="meta-llama/llama-3.3-70b-instruct"),
        ChainEntry(provider="gemini", model="gemini-3.1-flash-lite"),
    ]
    segments = list(iter_chain_segments(chain))
    assert len(segments) == 3
    assert segments[1][0] == "openrouter_batch"
    assert len(segments[1][1]) == 2


def test_normalize_session_id_truncates():
    assert len(normalize_session_id("x" * 300) or "") == 256


def test_build_openrouter_payload_session_id_top_level_not_provider():
    payload = build_openrouter_payload(
        models=["openai/gpt-4o-mini"],
        messages=[{"role": "user", "content": "hi"}],
        max_tokens=256,
        provider={"sort": "price"},
        session_id="calt-notes_chunk-medium",
    )
    assert payload["session_id"] == "calt-notes_chunk-medium"
    assert "session_id" not in payload.get("provider", {})


def test_service_tier_batch_vs_interactive():
    assert service_tier_for_task("notes_chunk") == "flex"
    assert service_tier_for_task("coach") == "priority"


def test_response_cache_quiz_only():
    assert response_cache_enabled_for_task("quiz_gen") is True
    assert response_cache_enabled_for_task("notes_chunk") is False


@patch("backend.config.get_settings")
def test_provider_prefs_heavy_max_price(mock_settings):
    s = MagicMock()
    s.llm_openrouter_provider_sort = ""
    s.llm_openrouter_data_collection = ""
    s.llm_openrouter_zdr = False
    s.llm_openrouter_max_price_prompt = 0.001
    s.llm_openrouter_max_price_completion = 0.002
    s.llm_openrouter_max_latency_light = 2.0
    s.llm_openrouter_max_latency_medium = 8.0
    s.llm_openrouter_max_latency_heavy = 0.0
    s.llm_openrouter_min_throughput_heavy = 0.0
    mock_settings.return_value = s

    prefs = provider_prefs_for_request(tier="heavy", task="corpus_grounded")
    assert prefs["max_price"] == {"prompt": 0.001, "completion": 0.002}
    assert prefs["sort"] == "throughput"


@patch("backend.config.get_settings")
def test_openrouter_headers_metadata_and_cache(mock_settings):
    s = MagicMock()
    s.llm_openrouter_metadata = True
    s.llm_openrouter_response_cache = True
    s.llm_openrouter_site_url = ""
    s.llm_openrouter_app_name = "CALT"
    mock_settings.return_value = s

    opts = MagicMock()
    opts.api_key = "sk-test"
    headers = openrouter_request_headers(opts, session_id="calt-quiz-medium", task="quiz_gen")
    assert headers["X-OpenRouter-Metadata"] == "enabled"
    assert headers["X-OpenRouter-Cache"] == "enabled"
    assert headers["x-session-id"] == "calt-quiz-medium"


def test_build_payload_service_tier_and_preset():
    payload = build_openrouter_payload(
        models=["@preset/calt-medium"],
        messages=[{"role": "user", "content": "hi"}],
        max_tokens=512,
        service_tier="flex",
    )
    assert payload["model"] == "@preset/calt-medium"
    assert payload["service_tier"] == "flex"


def test_parse_openrouter_response_metadata_and_zero_insurance():
    parsed = parse_openrouter_response(
        {
            "id": "gen-1",
            "model": "openai/gpt-4o-mini",
            "provider": "OpenAI",
            "choices": [{"message": {"content": ""}, "finish_reason": "error"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 0, "total_tokens": 10},
            "openrouter_metadata": {"strategy": "fallback", "attempt": 2},
        }
    )
    assert parsed["zero_completion_insurance"] is True
    assert parsed["openrouter_metadata"]["strategy"] == "fallback"
    assert parsed["finish_reason"] == "error"


def test_openrouter_models_from_entries_dedupes():
    entries = [
        ChainEntry(provider="openrouter", model="openai/gpt-4o-mini"),
        ChainEntry(provider="openrouter", model="openai/gpt-4o-mini"),
        ChainEntry(provider="openrouter", model="anthropic/claude-sonnet-4"),
    ]
    assert openrouter_models_from_entries(entries) == [
        "openai/gpt-4o-mini",
        "anthropic/claude-sonnet-4",
    ]
