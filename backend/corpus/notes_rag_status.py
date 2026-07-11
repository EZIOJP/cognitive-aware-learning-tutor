"""Notes-RAG readiness — textbooks only; skip rebuild when healthy."""

from __future__ import annotations

from typing import Any, Callable

from backend.corpus.registry import chunk_count, list_chunks, list_documents
from backend.corpus.retrieve import NOTES_RAG_SOURCE_TYPES, corpus_available, hybrid_retrieve
from backend.corpus.vector_store import retrieval_backend

ProgressFn = Callable[[str], None] | None


def _count_by_source_type() -> dict[str, int]:
    by: dict[str, int] = {}
    for doc in list_documents():
        st = (getattr(doc, "source_type", None) or "unknown").strip().lower() or "unknown"
        by[st] = by.get(st, 0) + 1
    return by


def _textbook_chunk_count() -> int:
    n = 0
    for c in list_chunks():
        if (getattr(c, "source_type", None) or "").strip().lower() == "textbook":
            n += 1
    return n


def assess_notes_rag(*, smoke_query: str = "What is an eigenvalue?") -> dict[str, Any]:
    """
    Decide whether notes RAG is usable and whether a rebuild is needed.

    status:
      - ok       — textbooks indexed + smoke retrieve hits; rebuild not needed
      - degraded — usable but weak (SQLite vectors / pollution); rebuild optional
      - broken   — empty / no textbooks / retrieve fails; rebuild allowed
    """
    reasons: list[str] = []
    by_type = _count_by_source_type()
    textbook_docs = int(by_type.get("textbook", 0))
    transcript_docs = int(by_type.get("transcript", 0))
    note_docs = int(by_type.get("note", 0))
    total = chunk_count() if corpus_available() else 0
    textbook_chunks = _textbook_chunk_count() if total else 0
    backend = "unknown"
    try:
        backend = retrieval_backend()
    except Exception as exc:  # noqa: BLE001
        reasons.append(f"vector_backend_error:{exc}")

    smoke_hits = 0
    smoke_error: str | None = None
    if textbook_chunks > 0:
        try:
            hits = hybrid_retrieve(
                smoke_query,
                source_types=list(NOTES_RAG_SOURCE_TYPES),
                top_k=3,
            )
            smoke_hits = len(hits or [])
        except Exception as exc:  # noqa: BLE001
            smoke_error = str(exc)
            reasons.append(f"smoke_retrieve_failed:{exc}")

    if transcript_docs or note_docs:
        reasons.append(
            f"non_textbook_docs:transcripts={transcript_docs},notes={note_docs} "
            "(notes RAG should be textbooks only)"
        )

    if backend == "sqlite":
        reasons.append("dense_retrieval_sqlite_fallback")

    if not corpus_available() or total <= 0:
        status = "broken"
        reasons.append("corpus_empty")
    elif textbook_docs <= 0 or textbook_chunks <= 0:
        status = "broken"
        reasons.append("no_textbook_chunks")
    elif smoke_hits <= 0:
        status = "broken"
        reasons.append("smoke_query_no_hits")
    elif transcript_docs or note_docs or backend == "sqlite":
        status = "degraded"
    else:
        status = "ok"

    needs_rebuild = status == "broken"
    needs_cleanup = bool(transcript_docs or note_docs)

    return {
        "status": status,
        "ok": status == "ok",
        "usable": status in ("ok", "degraded"),
        "needs_rebuild": needs_rebuild,
        "needs_cleanup": needs_cleanup,
        "skip_rebuild": not needs_rebuild,
        "allow_rebuild": needs_rebuild,
        "textbook_count": textbook_docs,
        "textbook_chunks": textbook_chunks,
        "transcript_count": transcript_docs,
        "note_count": note_docs,
        "total_chunks": total,
        "retrieval_backend": backend,
        "smoke_hits": smoke_hits,
        "smoke_query": smoke_query,
        "smoke_error": smoke_error,
        "notes_rag_source_types": list(NOTES_RAG_SOURCE_TYPES),
        "reasons": reasons,
        "summary": (
            f"notes_rag={status} · {textbook_docs} textbooks ({textbook_chunks:,} chunks) · "
            f"backend={backend} · smoke_hits={smoke_hits}"
        ),
    }


def _ingest_textbooks_only(
    *,
    force: bool,
    ingest_full_books: bool,
    mml_chapters: list[int] | None,
    step: Callable[[str], None],
) -> dict[str, Any]:
    from backend.corpus.library import (
        ensure_metadata,
        ingest_all_full_books,
        ingest_subject,
        scan_raw_library,
    )

    books = scan_raw_library()
    for entry in books:
        ensure_metadata(entry.subject_id)

    mml = next((b for b in books if b.subject_id == "linear_algebra"), None)
    mml_result = None
    if mml and mml.file_present:
        chs = mml_chapters or mml.auto_chapters or [1, 2]
        step(f"Ingesting MML chapters {chs}…")
        mml_result = ingest_subject("linear_algebra", chapters=chs)
    else:
        step("MML textbook not on disk (optional)")

    full_result = None
    if ingest_full_books:
        step("Ingesting full textbooks on disk…")
        full_result = ingest_all_full_books(
            skip_indexed=not force,
            force=force,
            log=step,
        )
    return {"mml": mml_result, "full_books": full_result, "transcripts_ingested": 0}


def ensure_notes_rag_textbooks(
    *,
    force: bool = False,
    ingest_full_books: bool = True,
    mml_chapters: list[int] | None = None,
    on_progress: ProgressFn = None,
) -> dict[str, Any]:
    """
    Keep notes RAG healthy without rebuilding when already working.

    - force=False + usable → skip rebuild (purge transcript/note pollution if present)
    - force=False + broken → wipe if empty + ingest textbooks only
    - force=True → wipe + ingest textbooks only
    """
    from backend.corpus.purge import purge_by_source_types, reset_corpus

    def step(msg: str) -> None:
        if on_progress:
            try:
                on_progress(msg)
            except Exception:
                pass

    before = assess_notes_rag()
    step(before["summary"])

    if before.get("needs_cleanup"):
        step("Removing transcript/note docs (notes RAG = textbooks only)…")
        cleaned = purge_by_source_types(["transcript", "note"])
        step(f"  Purged {cleaned.get('purged', 0)} non-textbook document(s)")
        before = assess_notes_rag()
        step(before["summary"])
        if before.get("usable") and not force and not before.get("needs_rebuild"):
            return {
                "action": "cleaned",
                "skipped_rebuild": True,
                "force": False,
                "before": before,
                "after": before,
                "cleanup": cleaned,
                "total_chunks": before.get("total_chunks", 0),
                "message": "Removed non-textbook docs — rebuild skipped",
                "transcripts_ingested": 0,
            }

    if before.get("usable") and not before.get("needs_rebuild") and not force:
        step("Notes RAG already usable — skip rebuild (Force rebuild to wipe).")
        return {
            "action": "skipped",
            "skipped_rebuild": True,
            "force": False,
            "before": before,
            "after": before,
            "total_chunks": before.get("total_chunks", 0),
            "message": "RAG working — rebuild skipped",
            "transcripts_ingested": 0,
        }

    wipe = None
    if force or before.get("textbook_chunks", 0) <= 0:
        step("Wiping corpus (registry / BM25 / Qdrant)…")
        wipe = reset_corpus(wipe_files=True)
        step(f"  Wipe ok={wipe.get('ok')} removed={len(wipe.get('removed') or [])}")

    ingest = _ingest_textbooks_only(
        force=force or True,
        ingest_full_books=ingest_full_books,
        mml_chapters=mml_chapters,
        step=step,
    )
    after = assess_notes_rag()
    step(after["summary"])
    return {
        "action": "force_rebuild" if force else "rebuild",
        "skipped_rebuild": False,
        "force": force,
        "before": before,
        "after": after,
        "wipe": wipe,
        "total_chunks": after.get("total_chunks", 0),
        "message": "Textbooks rebuilt",
        **ingest,
    }
