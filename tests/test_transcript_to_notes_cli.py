"""Tests for transcript_to_notes CLI."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

MOCK_BODY = "# Test\n\n## Topic\n\n- point one\n"


@patch("backend.scripts.transcript_to_notes._check_llm")
@patch("backend.scripts.transcript_to_notes._index_in_kb")
@patch("backend.scripts.transcript_to_notes.generate_notes_from_file")
@patch("backend.scripts.transcript_to_notes._resolve_latest")
def test_cli_latest(mock_latest, mock_gen, mock_index, mock_llm, tmp_path, monkeypatch):
    notes_root = tmp_path / "notes"
    notes_root.mkdir()
    monkeypatch.setattr("backend.scripts.transcript_to_notes.NOTES_DIR", notes_root)

    transcript = tmp_path / "live_captions_test.txt"
    transcript.write_text("hello lecture", encoding="utf-8")
    mock_latest.return_value = transcript

    out = notes_root / "lecture_test.md"
    mock_gen.return_value = (out, MOCK_BODY)

    from backend.scripts import transcript_to_notes as cli

    with patch.object(cli.sys, "argv", ["transcript_to_notes", "--latest", "--fast"]):
        cli.main()

    mock_gen.assert_called_once()
    call_kw = mock_gen.call_args.kwargs
    assert call_kw["fast_mode"] is True
    assert call_kw["use_semantic_grouping"] is False
    mock_index.assert_called_once()


def test_resolve_context_folder_absolute(tmp_path):
    from backend.transcripts.notes_generator import _resolve_context_folder

    folder = tmp_path / "ctx"
    folder.mkdir()
    assert _resolve_context_folder(str(folder)) == folder


def test_merge_reference_materials():
    from backend.transcripts.notes_generator import _merge_reference_materials

    assert _merge_reference_materials("a", "b") == "a\n\n---\n\nb"
    assert _merge_reference_materials("", "b") == "b"


def test_limit_chunks_merges_long_lists():
    from backend.transcripts.notes_generator import _limit_chunks

    chunks = [f"chunk{i}" for i in range(30)]
    limited = _limit_chunks(chunks, max_chunks=12)
    assert len(limited) <= 12
