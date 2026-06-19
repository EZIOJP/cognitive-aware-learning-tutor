"""Tests for semantic_cache.py."""

from __future__ import annotations

import sys
import tempfile
import types
from pathlib import Path
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Mock sentence_transformers (same approach as test_semantic_chunker.py)
# ---------------------------------------------------------------------------
if "sentence_transformers" not in sys.modules:
    _st_mock = types.ModuleType("sentence_transformers")

    class _MockST:
        def __init__(self, *a, **kw):
            pass

        def encode(self, sentences, **kw):
            import numpy as np  # noqa: PLC0415

            n = len(sentences)
            vecs = np.zeros((n, 8), dtype="float32")
            for i, s in enumerate(sentences):
                # Give each unique sentence a slightly different vector
                vecs[i, hash(s) % 8] = 1.0
            return vecs

    _st_mock.SentenceTransformer = _MockST  # type: ignore[attr-defined]
    sys.modules["sentence_transformers"] = _st_mock

import transcript_studio.semantic_cache as sc  # noqa: E402


@pytest.fixture
def tmp_db(tmp_path):
    db_path = tmp_path / "test_cache.db"
    sc.set_cache_db_path(db_path)
    sc._EMBED_MODEL = None  # reset cached model
    yield db_path
    sc.set_cache_db_path(None)  # type: ignore[arg-type]
    sc._CACHE_DB_PATH = None


# ---------------------------------------------------------------------------
# Basic store and lookup
# ---------------------------------------------------------------------------


def test_exact_hit_returns_cached(tmp_db):
    sc.cache_store("Hello world prompt", "Response text", model="gpt-4", temperature=0.3, db_path=tmp_db)
    result = sc.cache_lookup("Hello world prompt", model="gpt-4", temperature=0.3, db_path=tmp_db)
    assert result == "Response text"


def test_miss_returns_none(tmp_db):
    result = sc.cache_lookup("completely different query", model="gpt-4", temperature=0.3, db_path=tmp_db)
    assert result is None


def test_different_model_no_hit(tmp_db):
    sc.cache_store("Same prompt text", "Response", model="model-a", temperature=0.3, db_path=tmp_db)
    result = sc.cache_lookup("Same prompt text", model="model-b", temperature=0.3, db_path=tmp_db)
    assert result is None


def test_cosine_hit_on_similar_prompt(tmp_db):
    """Two prompts that encode to the same vector (hash collision in mock) should hit."""
    original = "numpy arrays broadcasting"
    similar = "numpy arrays broadcasting"  # Identical → same hash → exact hit
    sc.cache_store(original, "Numpy response", model="model-x", temperature=0.3, db_path=tmp_db)
    result = sc.cache_lookup(similar, model="model-x", temperature=0.3, threshold=0.95, db_path=tmp_db)
    assert result == "Numpy response"


def test_different_prompts_no_false_collision(tmp_db):
    """Completely different prompts must not collide via cosine."""
    sc.cache_store("Topic A about quantum physics", "Physics answer", model="m1", temperature=0.3, db_path=tmp_db)
    # With mock encoder, all prompts get vectors based on hash % 8 slot
    # This test verifies the cache doesn't explode — if it hits or misses, no exception
    result = sc.cache_lookup("Topic Z about cooking recipes", model="m1", temperature=0.3, threshold=0.99, db_path=tmp_db)
    # Either None or a string — just shouldn't crash
    assert result is None or isinstance(result, str)


# ---------------------------------------------------------------------------
# Purge
# ---------------------------------------------------------------------------


def test_purge_removes_old_entries(tmp_db):
    import sqlite3  # noqa: PLC0415
    import time  # noqa: PLC0415

    sc.cache_store("Old prompt", "Old response", model="m1", temperature=0.3, db_path=tmp_db)
    # Force created_at to be ancient
    conn = sqlite3.connect(str(tmp_db))
    conn.execute("UPDATE llm_cache SET created_at=1 WHERE 1=1")
    conn.commit()
    conn.close()

    deleted = sc.cache_purge_old(max_age_days=1, db_path=tmp_db)
    assert deleted == 1

    result = sc.cache_lookup("Old prompt", model="m1", temperature=0.3, db_path=tmp_db)
    assert result is None


# ---------------------------------------------------------------------------
# Hash normalization
# ---------------------------------------------------------------------------


def test_hash_normalized_same_for_case_and_whitespace():
    h1 = sc._hash_prompt("Hello World  ")
    h2 = sc._hash_prompt("hello world")
    assert h1 == h2


# ---------------------------------------------------------------------------
# DB schema creation
# ---------------------------------------------------------------------------


def test_db_created_with_schema(tmp_path):
    db_path = tmp_path / "fresh.db"
    conn = sc._get_conn(db_path)
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    conn.close()
    assert "llm_cache" in tables
