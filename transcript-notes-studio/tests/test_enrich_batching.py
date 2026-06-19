"""Tests for section-aware enrich batching."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from transcript_studio.config import AppConfig
from transcript_studio.llm_client import LlmOptions
from transcript_studio.notes_generator import _split_h2_sections, enrich_notes


def test_split_h2_sections_on_large_draft() -> None:
    sections = [f"## Topic {i}\n\n{'word ' * 2000}" for i in range(12)]
    draft = "\n\n".join(sections)
    assert len(draft) > 60000
    parts = _split_h2_sections(draft)
    assert len(parts) == 12
    assert all(p.startswith("## Topic") for p in parts)


@patch("transcript_studio.notes_generator.generate")
def test_enrich_batches_by_h2_sections(mock_generate: MagicMock) -> None:
    mock_generate.return_value = "## Topic\n\nEnriched."
    sections = [f"## Topic {i}\n\n{'content ' * 200}" for i in range(8)]
    draft = "\n\n".join(sections)
    context = "reference " * 1000
    opts = LlmOptions(provider="lmstudio", base_url="http://127.0.0.1:1234", model="test")

    result = enrich_notes(draft, context=context, opts=opts)

    assert result is not None
    assert mock_generate.call_count >= 8


@patch("transcript_studio.notes_generator.generate")
def test_enrich_single_call_for_short_notes(mock_generate: MagicMock) -> None:
    mock_generate.return_value = "## Short\n\nDone."
    opts = LlmOptions(provider="lmstudio", base_url="http://127.0.0.1:1234", model="test")

    enrich_notes("## Short\n\nBrief notes.", context="ref text", opts=opts)

    assert mock_generate.call_count == 1
