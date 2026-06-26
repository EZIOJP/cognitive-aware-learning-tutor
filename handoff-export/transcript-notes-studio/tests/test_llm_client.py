"""Tests for LLM temperature configuration."""

from __future__ import annotations

from transcript_studio.config import AppConfig
from transcript_studio.llm_client import LlmOptions, options_from_config


def test_options_from_config_temperature() -> None:
    cfg = AppConfig(llm_temperature=0.25)
    opts = options_from_config(cfg)
    assert opts.temperature == 0.25


def test_temperature_clamped() -> None:
    cfg = AppConfig(llm_temperature=5.0)
    opts = options_from_config(cfg)
    assert opts.temperature == 2.0


def test_llm_options_has_temperature_field() -> None:
    opts = LlmOptions(
        provider="openai",
        base_url="http://127.0.0.1:8000",
        model="test",
        temperature=0.35,
    )
    assert opts.temperature == 0.35
