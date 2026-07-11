"""Remove documents from registry, BM25, and Qdrant."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Any

from backend.corpus.bm25_index import rebuild_bm25_from_registry
from backend.corpus.paths import CORPUS_DIR, QDRANT_PATH, ensure_corpus_dirs, get_bm25_path, get_registry_db
from backend.corpus.registry import (
    delete_document_chunks,
    list_chunks,
    list_documents,
    registry_conn,
)
from backend.corpus.vector_store import VectorStore, close_vector_store

log = logging.getLogger(__name__)


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


def purge_by_source_types(
    source_types: list[str],
    *,
    db_path: Path | None = None,
    bm25_path: Path | None = None,
) -> dict[str, Any]:
    """Remove all documents whose source_type is in ``source_types`` (e.g. transcript, note)."""
    wanted = {s.strip().lower() for s in source_types if s and str(s).strip()}
    if not wanted:
        return {"purged": 0, "documents": []}
    results: list[dict[str, Any]] = []
    for doc in list_documents(db_path=db_path):
        st = (getattr(doc, "source_type", None) or "").strip().lower()
        if st in wanted:
            results.append(purge_document(doc.document_id, db_path=db_path, bm25_path=bm25_path))
    return {"purged": len(results), "documents": results, "source_types": sorted(wanted)}


def reset_corpus(*, wipe_files: bool = True) -> dict[str, Any]:
    """
    Hard reset: close Qdrant, delete registry / BM25 / Qdrant dir, recreate empty dirs.

    Call only when no other process holds ``data/corpus/qdrant``.
    """
    close_vector_store()
    removed: list[str] = []
    errors: list[str] = []
    if wipe_files:
        for path in (get_registry_db(), get_bm25_path()):
            try:
                if path.is_file():
                    path.unlink()
                    removed.append(str(path))
            except OSError as exc:
                errors.append(f"{path}: {exc}")
        try:
            if QDRANT_PATH.exists():
                shutil.rmtree(QDRANT_PATH)
                removed.append(str(QDRANT_PATH))
        except OSError as exc:
            errors.append(f"{QDRANT_PATH}: {exc}")
            log.warning("Could not remove Qdrant path: %s", exc)
    ensure_corpus_dirs()
    # Touch empty registry schema
    from backend.corpus.registry import init_registry

    init_registry(get_registry_db())
    return {
        "ok": not errors,
        "corpus_dir": str(CORPUS_DIR),
        "removed": removed,
        "errors": errors,
    }
