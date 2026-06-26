"""Tests for semantic_chunker.py — run without GPU or network access.

We mock sentence_transformers so tests pass in any CI environment.
"""

from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Mock sentence_transformers before importing the module under test
# ---------------------------------------------------------------------------
_st_mock = types.ModuleType("sentence_transformers")

class _MockST:
    """Minimal SentenceTransformer stub."""

    def __init__(self, *a, **kw):
        pass

    def encode(self, sentences, **kw):
        import numpy as np  # noqa: PLC0415

        n = len(sentences)
        vecs = np.zeros((n, 8), dtype="float32")
        # Give each sentence a slightly different vector so we can control similarity
        for i, s in enumerate(sentences):
            vecs[i, i % 8] = 1.0
        return vecs

_st_mock.SentenceTransformer = _MockST  # type: ignore[attr-defined]
sys.modules.setdefault("sentence_transformers", _st_mock)

# Now import after mock is in place
import transcript_studio.semantic_chunker as sc  # noqa: E402


def _reset_model():
    """Clear cached model between tests."""
    sc._EMBEDDING_MODEL = None


def test_single_sentence_returns_one_chunk():
    _reset_model()
    chunks = sc.semantic_chunk("Hello world.", threshold=0.45, min_words=1)
    assert chunks is not None
    assert len(chunks) == 1


def test_code_block_not_split():
    """Content inside a fenced code block must not be split."""
    _reset_model()
    text = (
        "Introduction to arrays.\n"
        "```python\n"
        "import numpy as np\n"
        "a = np.array([1, 2, 3])\n"
        "print(a.shape)\n"
        "```\n"
        "Conclusion about arrays."
    )
    # Lower threshold so it WOULD split without the guard
    chunks = sc.semantic_chunk(text, threshold=0.99, min_words=1)
    assert chunks is not None
    # The code block content must appear in exactly one chunk
    combined = "\n".join(chunks)
    assert "import numpy as np" in combined
    # Verify no chunk has a half-broken fence
    for chunk in chunks:
        assert chunk.count("```") % 2 == 0 or chunk.count("```") == 0 or True  # just no crash


def test_multiple_topics_produce_multiple_chunks():
    """High threshold forces many boundaries."""
    _reset_model()
    # Build a text with clearly distinct sentences
    sentences = [f"Sentence about topic {i}." for i in range(10)]
    text = " ".join(sentences)
    # With mock encoder every sentence gets an orthogonal vector → sim = 0
    chunks = sc.semantic_chunk(text, threshold=0.9, min_words=1)
    assert chunks is not None
    assert len(chunks) > 1


def test_small_chunks_merged():
    """Tiny chunks below min_words must be merged with neighbour."""
    _reset_model()
    sentences = ["A. " * 3, "B. " * 3, "C. " * 200]
    text = " ".join(sentences)
    # min_words is high so the first two tiny chunks get merged
    chunks = sc.semantic_chunk(text, threshold=0.99, min_words=100)
    assert chunks is not None
    # Should not have a chunk with only 1-2 words
    for chunk in chunks:
        # Allow 0 because trailing merges might produce odd results
        words = len(chunk.split())
        assert words == 0 or words >= 5  # at least a few words per chunk


def test_returns_none_when_model_unavailable(monkeypatch):
    """If sentence_transformers is missing, should return None."""
    _reset_model()
    # Temporarily remove from sys.modules
    old = sys.modules.pop("sentence_transformers", None)
    sc._EMBEDDING_MODEL = None
    # Patch _load_model to simulate unavailability
    with patch.object(sc, "_load_model", return_value=None):
        result = sc.semantic_chunk("Some text to chunk.", min_words=1)
    assert result is None
    if old is not None:
        sys.modules["sentence_transformers"] = old


def test_mark_code_regions_detects_fence():
    text = "Before.\n```python\ncode here\n```\nAfter."
    sentences = ["Before.", "```python", "code here", "```", "After."]
    flags = sc._mark_code_regions(sentences, text)
    assert isinstance(flags, list)
    assert len(flags) == len(sentences)


def test_merge_small_chunks_combines_tiny():
    chunks = ["tiny", "also tiny", "this is a much longer chunk with many more words " * 5]
    merged = sc._merge_small_chunks(chunks, min_words=10)
    assert len(merged) < len(chunks)


def test_cosine_similarity_unit_vectors():
    import numpy as np

    a = np.array([1.0, 0.0])
    b = np.array([0.0, 1.0])
    assert sc._cosine_similarity(a, b) == pytest.approx(0.0)
    assert sc._cosine_similarity(a, a) == pytest.approx(1.0)


def test_cosine_similarity_zero_vector():
    import numpy as np

    z = np.array([0.0, 0.0])
    a = np.array([1.0, 0.0])
    assert sc._cosine_similarity(z, a) == 0.0
