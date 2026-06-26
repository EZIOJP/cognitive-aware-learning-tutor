"""Corpus health checks for CLI and Knowledge Base overview."""

from __future__ import annotations

import shutil
from typing import Any

from backend.corpus.graph_retrieve import lightrag_available
from backend.corpus.paths import get_registry_db
from backend.corpus.purge import list_test_document_ids
from backend.corpus.registry import chunk_count, list_documents
from backend.corpus.vector_store import VectorStore
from backend.transcripts.embedding import is_available


def _pandoc_available() -> bool:
    return shutil.which("pandoc") is not None


def get_corpus_health() -> dict[str, Any]:
    docs = list_documents()
    test_ids = list_test_document_ids()
    store = VectorStore()
    issues: list[str] = []
    if test_ids:
        issues.append(f"Test pollution in registry: {', '.join(test_ids)}")
    if not is_available():
        issues.append("Embedding model unavailable — dense retrieval uses BM25/keyword only")
    if not _pandoc_available():
        issues.append("Pandoc not on PATH — EPUB textbook ingest will fail")
    if not lightrag_available():
        issues.append("LightRAG not installed — using KG graph bridge only (expected for v1)")

    return {
        "registry_db": str(get_registry_db()),
        "total_chunks": chunk_count(),
        "document_count": len(docs),
        "test_document_ids": test_ids,
        "embeddings_available": is_available(),
        "pandoc_available": _pandoc_available(),
        "lightrag_installed": lightrag_available(),
        "vector_store_mode": store._mode,  # noqa: SLF001
        "pandoc_path": shutil.which("pandoc"),
        "issues": issues,
        "healthy": not test_ids,
    }
