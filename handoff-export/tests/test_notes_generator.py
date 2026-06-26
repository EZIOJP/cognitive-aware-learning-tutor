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


def test_summarize_chunk_escapes_curly_braces_in_transcript():
    from backend.transcripts.notes_generator import summarize_chunk

    captured: list[str] = []

    def fake_generate(prompt: str) -> str:
        captured.append(prompt)
        return "## Notes\n\n- ok"

    chunk = "Use arr[{-1}] and shape {-1} in numpy indexing."
    result = summarize_chunk(
        chunk,
        reference_hint="see df.iloc[-1] too",
        generate_fn=fake_generate,
    )
    assert result == "## Notes\n\n- ok"
    assert len(captured) == 1
    assert "arr[{-1}]" in captured[0]
    assert "df.iloc[-1]" in captured[0]
    assert "{chunk}" not in captured[0]


def test_select_chunks_fast_mode_uses_larger_windows():
    from backend.transcripts.notes_generator import _select_chunks

    text = "word " * 6000
    chunks = _select_chunks(text.strip(), use_semantic_grouping=False, fast_mode=True)
    assert len(chunks) <= 2


def test_split_oversized_chunks_breaks_merged_segment():
    from backend.transcripts.notes_generator import _split_oversized_chunks

    huge = "sentence. " * 8000
    parts = _split_oversized_chunks([huge])
    assert len(parts) > 1
    assert sum(len(p.split()) for p in parts) >= 7000


def test_slice_chunk_for_prompt_keeps_medium_chunk():
    from backend.transcripts.notes_generator import _slice_chunk_for_prompt

    text = "word " * 3000
    sliced, truncated = _slice_chunk_for_prompt(text)
    assert not truncated
    assert sliced == text.strip()


def test_effective_max_chunks_scales_with_lecture_length():
    from backend.transcripts.notes_generator import _effective_max_chunks

    assert _effective_max_chunks(120_000, 12, fast_mode=True) >= 20
    assert _effective_max_chunks(5_000, 12, fast_mode=True) >= 8
