"""Tests for gateway-first LLM routing in Transcript Notes Studio."""

from __future__ import annotations

from transcript_studio.config import AppConfig
from transcript_studio.gateway_llm import (
    default_llm_tier,
    resolve_for_generate,
    uses_gateway,
)


def test_uses_gateway_auto_provider() -> None:
    cfg = AppConfig(llm_provider="auto", llm_use_gateway=True)
    assert uses_gateway(cfg) is True


def test_manual_provider_bypasses_gateway() -> None:
    cfg = AppConfig(llm_provider="lmstudio", llm_use_gateway=False)
    assert uses_gateway(cfg) is False


def test_gemini_provider_uses_gateway() -> None:
    cfg = AppConfig(llm_provider="gemini", llm_use_gateway=False)
    assert uses_gateway(cfg) is True


def test_resolve_for_generate_gateway_mode() -> None:
    cfg = AppConfig(llm_provider="auto", llm_tier="heavy")
    llm, tier = resolve_for_generate(cfg, None)
    assert llm is None
    assert tier == "heavy"


def test_resolve_for_generate_manual_override() -> None:
    cfg = AppConfig(llm_provider="lmstudio", llm_use_gateway=False, llm_model="test-model")
    llm, tier = resolve_for_generate(cfg, None)
    assert llm is not None
    assert llm.model == "test-model"


def test_default_llm_tier_from_config() -> None:
    cfg = AppConfig(llm_tier="light")
    assert default_llm_tier(cfg) == "light"


def test_openrouter_provider_uses_gateway() -> None:
    cfg = AppConfig(llm_provider="openrouter", llm_use_gateway=False)
    assert uses_gateway(cfg) is True


def test_last_generate_meta_legacy(monkeypatch) -> None:
    from transcript_studio import notes_generator as ng

    ng._set_generate_meta(
        mode="legacy",
        rag={"grounding_status": "degraded", "grounding_reason": "corpus_unavailable"},
    )
    meta = ng.last_generate_meta()
    assert meta["grounding_status"] == "degraded"
    assert meta["grounding_reason"] == "corpus_unavailable"

