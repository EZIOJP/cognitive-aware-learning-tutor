"""Test defaults — avoid heavy word seed during API tests."""

import os

import pytest

os.environ.setdefault("SEED_WORDS_ON_STARTUP", "false")
os.environ.setdefault("DEV_MODE", "true")


@pytest.fixture(autouse=True)
def isolate_corpus_registry(request, tmp_path, monkeypatch):
    """Keep unit tests off the production corpus registry unless marked integration."""
    if request.node.get_closest_marker("integration"):
        return
    db = tmp_path / "corpus_registry.db"
    bm = tmp_path / "bm25.pkl"
    monkeypatch.setenv("CORPUS_REGISTRY_DB", str(db))
    monkeypatch.setenv("CORPUS_BM25_PATH", str(bm))
    from backend.corpus.registry import init_registry

    init_registry(db)


def pytest_configure(config):
    config.addinivalue_line("markers", "integration: hits production corpus index (not isolated tmp db)")

