"""Daily review — gateway task=daily_review with heavy default tier."""

from __future__ import annotations

from unittest.mock import patch

from backend.hub.services.gemma_review import generate_daily_review


def test_daily_review_uses_gateway_task():
    captured: dict = {}

    def fake_generate(prompt, **kwargs):
        captured.update(kwargs)
        return '{"comments":"Solid day.","next_steps":["Sleep 8h"],"goals":["Focus block"]}'

    with patch("backend.hub.services.gemma_review.training_stats_for_hub", return_value={}):
        with patch("backend.hub.services.gemma_review.ollama_generate", side_effect=fake_generate):
            result = generate_daily_review(
                {"overall_performance": "good", "study_minutes": 45},
                user_id=1,
            )

    assert result["comments"] == "Solid day."
    assert result["source"] == "gemma"
    assert captured.get("task") == "daily_review"
    assert captured.get("timeout") == 90.0
    assert captured.get("tier") is None


def test_daily_review_passes_llm_tier():
    captured: dict = {}

    def fake_generate(prompt, **kwargs):
        captured.update(kwargs)
        return '{"comments":"Keep going.","next_steps":[],"goals":[]}'

    with patch("backend.hub.services.gemma_review.training_stats_for_hub", return_value={}):
        with patch("backend.hub.services.gemma_review.ollama_generate", side_effect=fake_generate):
            generate_daily_review({"overall_performance": "good"}, user_id=1, llm_tier="medium")

    assert captured.get("tier") == "medium"


def test_nim_chain_entry_uses_nim_api_key():
    from backend.core.llm_capabilities import entry_to_options
    from backend.core.llm_tiers import ChainEntry

    entry = ChainEntry(
        provider="openai",
        model="google/gemma-4-31b-it",
        base_url="https://integrate.api.nvidia.com/v1",
    )

    with patch("backend.config.get_settings") as mock_settings:
        mock_settings.return_value.nim_api_key = "nvapi-test-key"
        mock_settings.return_value.ollama_url = "http://127.0.0.1:1234"
        mock_settings.return_value.llm_openrouter_api_key = ""
        mock_settings.return_value.llm_anthropic_api_key = ""
        mock_settings.return_value.llm_api_key = ""
        mock_settings.return_value.llm_max_tokens = 4096
        mock_settings.return_value.llm_provider = "lmstudio"
        mock_settings.return_value.ollama_model = "test"

        opts = entry_to_options(entry)

    assert opts.api_key == "nvapi-test-key"
    assert opts.base_url == "https://integrate.api.nvidia.com/v1"
