"""Remove documents from registry, BM25, and Qdrant."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.corpus.bm25_index import rebuild_bm25_from_registry
from backend.corpus.paths import get_bm25_path, get_registry_db
from backend.corpus.registry import (
    delete_document_chunks,
    list_chunks,
    list_documents,
    registry_conn,
)
from backend.corpus.vector_store import VectorStore


def _chunk_ids_for_document(document_id: str, *, db_path: Path | None = None) -> list[str]:
    return [c.chunk_id for c in list_chunks(document_id=document_id, db_path=db_path)]


def purge_document(
    document_id: str,
    *,
    db_path: Path | None = None,
    bm25_path: Path | None = None,
) -> dict[str, Any]:
    """Delete one document, its chunks, vectors, and rebuild BM25."""
    db_path = db_path or get_registry_db()
    bm25_path = bm25_path or get_bm25_path()
    chunk_ids = _chunk_ids_for_document(document_id, db_path=db_path)
    VectorStore().delete_chunk_ids(chunk_ids)
    removed = delete_document_chunks(document_id, db_path=db_path)
    with registry_conn(db_path) as conn:
        conn.execute("DELETE FROM documents WHERE document_id = ?", (document_id,))
        conn.commit()
    rebuild_bm25_from_registry(db_path=db_path, bm25_path=bm25_path)
    return {
        "document_id": document_id,
        "chunks_removed": removed,
        "vector_points_removed": len(chunk_ids),
    }


def list_test_document_ids(*, db_path: Path | None = None) -> list[str]:
    return [d.document_id for d in list_documents(db_path=db_path) if d.document_id.startswith("test_")]


def purge_test_documents(
    *,
    db_path: Path | None = None,
    bm25_path: Path | None = None,
) -> dict[str, Any]:
    """Remove all documents whose id starts with ``test_`` (pytest pollution)."""
    doc_ids = list_test_document_ids(db_path=db_path)
    results: list[dict[str, Any]] = []
    for doc_id in doc_ids:
        results.append(purge_document(doc_id, db_path=db_path, bm25_path=bm25_path))
    return {"purged": len(results), "documents": results}
