"""Tests for prompt content and pipeline pass toggles."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from transcript_studio.config import AppConfig
from transcript_studio.llm_client import LlmOptions
from transcript_studio.notes_generator import (
    CHUNK_PROMPT,
    ENRICH_PROMPT,
    REFINE_PROMPT,
    generate_notes_from_text,
)


def test_chunk_prompt_has_code_quality_rules() -> None:
    assert "```python" in CHUNK_PROMPT
    assert "valid and runnable" in CHUNK_PROMPT
    assert "one short explanation paragraph" in CHUNK_PROMPT
    assert "do not invent APIs" in CHUNK_PROMPT
    assert "reference file names" in CHUNK_PROMPT


def test_refine_prompt_has_no_compress_rules() -> None:
    assert "at or above the draft length" in REFINE_PROMPT
    assert "Concept → Why it matters → Example → Snippet → Pitfalls" in REFINE_PROMPT
    assert "roll-call" in REFINE_PROMPT


def test_enrich_prompt_has_pdf_cleanup_rules() -> None:
    assert "Explanation → Code → Expected output" in ENRICH_PROMPT
    assert "15–25 lines" in ENRICH_PROMPT
    assert "Compare & contrast" in ENRICH_PROMPT
    assert "In [1]:" in ENRICH_PROMPT
    assert "truncated due to PDF pagination" in ENRICH_PROMPT


@patch("transcript_studio.notes_generator.llm_available", return_value=True)
@patch("transcript_studio.notes_generator.generate")
@patch("transcript_studio.notes_generator.load_config")
def test_fast_mode_skips_refine_and_enrich(
    mock_load_config: MagicMock,
    mock_generate: MagicMock,
    _mock_llm: MagicMock,
    tmp_path: Path,
) -> None:
    cfg = AppConfig()
    mock_load_config.return_value = cfg
    mock_generate.return_value = "## Topic\n\nSome notes."
    opts = LlmOptions(provider="lmstudio", base_url="http://127.0.0.1:1234", model="test")

    generate_notes_from_text(
        "word " * 500,
        title="test",
        output_dir=tmp_path,
        opts=opts,
        fast_mode=True,
        refine_second_pass=True,
        enrich_with_references=True,
    )

    # Only chunk pass calls — one generate per chunk (single chunk for 500 words)
    assert mock_generate.call_count == 1


@patch("transcript_studio.notes_generator.llm_available", return_value=True)
@patch("transcript_studio.notes_generator.enrich_notes")
@patch("transcript_studio.notes_generator.refine_notes")
@patch("transcript_studio.notes_generator.generate")
@patch("transcript_studio.notes_generator.load_config")
def test_enrich_disabled_skips_enrich_pass(
    mock_load_config: MagicMock,
    mock_generate: MagicMock,
    mock_refine: MagicMock,
    mock_enrich: MagicMock,
    _mock_llm: MagicMock,
    tmp_path: Path,
) -> None:
    cfg = AppConfig()
    mock_load_config.return_value = cfg
    mock_generate.return_value = "## Topic\n\nDraft content."
    mock_refine.return_value = "## Topic\n\nRefined content."
    opts = LlmOptions(provider="lmstudio", base_url="http://127.0.0.1:1234", model="test")

    generate_notes_from_text(
        "word " * 500,
        title="test",
        output_dir=tmp_path,
        opts=opts,
        reference_materials="### Reference: numpy.pdf\n\nimport numpy",
        refine_second_pass=True,
        enrich_with_references=False,
    )

    mock_refine.assert_called_once()
    mock_enrich.assert_not_called()
