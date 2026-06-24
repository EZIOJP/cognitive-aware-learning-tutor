from pathlib import Path
from unittest.mock import patch

import pytest

MOCK_SECTION = """## Array Reversal

- Use two pointers at start and end

```mermaid
flowchart LR
  A[start] --> B[swap]
```
"""


@patch("backend.transcripts.notes_generator._select_chunks", return_value=["chunk one"])
@patch("backend.transcripts.notes_generator.ollama_available", return_value="http://127.0.0.1:11434")
@patch("backend.transcripts.notes_generator.summarize_chunk", return_value=MOCK_SECTION)
def test_generate_notes_from_text(mock_summarize, mock_available, mock_chunks, tmp_path, monkeypatch):
    from backend.transcripts.notes_generator import generate_notes_from_text

    monkeypatch.setattr("backend.transcripts.notes_generator.NOTES_DIR", tmp_path)
    raw = "Today we learn array reversal."
    path, body = generate_notes_from_text(raw, title="test_lecture")
    assert path.is_file()
    assert "## Array Reversal" in body
    mock_summarize.assert_called_once()


@patch("backend.transcripts.notes_generator.ollama_available", return_value=None)
def test_generate_notes_requires_ollama(_mock_available):
    from backend.transcripts.notes_generator import generate_notes_from_text

    with pytest.raises(RuntimeError, match="Local LLM is not enabled"):
        generate_notes_from_text("some transcript text")


def test_generate_notes_empty_after_cleanup():
    from backend.transcripts.notes_generator import generate_notes_from_text

    with patch("backend.transcripts.notes_generator.ollama_available", return_value="http://127.0.0.1:11434"):
        with pytest.raises(ValueError, match="empty after cleanup"):
            generate_notes_from_text("   \n\n  ")


def test_select_chunks_fast_mode_uses_larger_windows():
    from backend.transcripts.notes_generator import _select_chunks

    text = "word " * 6000
    chunks = _select_chunks(text.strip(), use_semantic_grouping=False, fast_mode=True)
    assert len(chunks) <= 2
