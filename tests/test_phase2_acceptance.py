"""Phase 2 acceptance smoke — mocked LLM, real transcript file."""

from pathlib import Path
from unittest.mock import patch

MOCK_NARRATIVE = """## Module Overview

The instructor introduced NumPy arrays as the fundamental structure for numerical computing.
Therefore students should understand indexing before advanced operations.

### Semantic Glossary
- ndarray: N-dimensional array container
"""


@patch("backend.transcripts.notes_generator.finalize_full_note", side_effect=lambda body, **kw: body)
@patch("backend.transcripts.notes_generator._select_chunks", return_value=["chunk one"])
@patch("backend.transcripts.notes_generator.ollama_available", return_value="http://127.0.0.1:1234")
@patch("backend.transcripts.notes_generator.summarize_chunk", return_value=MOCK_NARRATIVE)
def test_phase2_acceptance_smoke(mock_summarize, mock_available, mock_chunks, mock_finalize, tmp_path, monkeypatch):
    from backend.transcripts.notes_generator import generate_notes_from_file

    monkeypatch.setattr("backend.transcripts.notes_generator.NOTES_DIR", tmp_path)
    transcript = Path("data/transcripts/test_!.txt")
    if not transcript.is_file():
        transcript.write_text("numpy arrays and indexing " * 500, encoding="utf-8")

    path, body = generate_notes_from_file(
        transcript,
        title="phase2_acceptance",
        already_cleaned=False,
        note_style="narrative",
        coherence_mode="compact",
        restore_punctuation=False,
        use_semantic_grouping=True,
    )
    assert path.is_file()
    assert "## Module Overview" in body
    assert "Confidence Score" not in body[:500]
    mock_summarize.assert_called()
