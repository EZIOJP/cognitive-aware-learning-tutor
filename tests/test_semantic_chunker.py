"""Tests for backend semantic chunker."""

from unittest.mock import patch

import numpy as np

from backend.transcripts.semantic_chunker import _find_boundaries, _merge_small_chunks, semantic_chunk


def test_find_boundaries_percentile_mode():
    embeddings = np.array(
        [
            [1.0, 0.0],
            [0.9, 0.1],
            [0.1, 0.9],
            [0.0, 1.0],
        ],
        dtype="float32",
    )
    sentences = ["one two three", "four five six", "seven eight nine", "ten eleven twelve"]
    in_code = [False, False, False, False]
    boundaries = _find_boundaries(
        embeddings,
        in_code,
        threshold_mode="percentile",
        threshold=0.45,
        percentile=50.0,
        max_words_per_chunk=2500,
        sentences=sentences,
    )
    assert boundaries[0] == 0
    assert len(boundaries) >= 2


@patch("backend.transcripts.semantic_chunker.encode_texts")
@patch("backend.transcripts.semantic_chunker.is_available", return_value=True)
def test_semantic_chunk_returns_segments(mock_avail, mock_encode):
    mock_encode.return_value = np.array([[1.0, 0.0], [0.2, 0.8], [0.1, 0.9]], dtype="float32")
    text = "First topic sentence here. Second topic continues. Third shifts completely."
    chunks = semantic_chunk(text, threshold=0.5, min_words=1, max_words=2500)
    assert chunks is not None
    assert len(chunks) >= 1


def test_merge_small_chunks_respects_max_words():
    tiny = [" ".join(["word"] * 20) for _ in range(400)]
    merged = _merge_small_chunks(tiny, min_words=150, max_words=2500)
    assert len(merged) > 1
    assert all(len(c.split()) <= 2500 for c in merged)
    assert sum(len(c.split()) for c in merged) >= 7000
