"""Initialize and inspect the Knowledge Base (RAG corpus) from Transcript Notes Studio."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from backend.corpus.ingest import ingest_path
from backend.corpus.jobs import CorpusJob, get_job, start_job
from backend.corpus.library import (
    ensure_metadata,
    ingest_latest_transcripts,
    ingest_subject,
    run_auto_setup,
    scan_raw_library,
)
from backend.corpus.registry import chunk_count
from backend.corpus.retrieve import corpus_available


ProgressFn = Callable[[str], None] | None


def get_corpus_summary() -> dict:
    """Lightweight status for the Studio UI."""
    try:
        from backend.corpus.registry import chunk_count, list_documents
        from backend.corpus.retrieve import NOTES_RAG_SOURCE_TYPES, corpus_available

        available = corpus_available()
        total = chunk_count() if available else 0
        docs = list_documents() if available else []
        by_type: dict[str, int] = {}
        for doc in docs:
            st = getattr(doc, "source_type", None) or "unknown"
            by_type[st] = by_type.get(st, 0) + 1
        textbook_count = by_type.get("textbook", 0)
        notes_rag_count = textbook_count
        try:
            from backend.corpus.vector_store import retrieval_backend

            vector_backend = retrieval_backend()
        except Exception:
            vector_backend = "unknown"
        return {
            "available": available,
            "total_chunks": total,
            "document_count": len(docs),
            "textbook_count": textbook_count,
            "notes_rag_count": notes_rag_count,
            "transcript_count": by_type.get("transcript", 0),
            "note_count": by_type.get("note", 0),
            "by_source_type": by_type,
            "notes_rag_source_types": list(NOTES_RAG_SOURCE_TYPES),
            "retrieval_backend": vector_backend,
            "healthy": available and total > 0,
            "issues": [],
        }
    except Exception as exc:
        try:
            from backend.corpus.retrieve import corpus_available
            from backend.corpus.registry import chunk_count

            return {
                "available": corpus_available(),
                "total_chunks": chunk_count() if corpus_available() else 0,
                "document_count": 0,
                "healthy": False,
                "issues": [str(exc)],
            }
        except Exception as inner:
            return {
                "available": False,
                "total_chunks": 0,
                "document_count": 0,
                "healthy": False,
                "issues": [str(inner)],
            }


def ingest_transcript_paths(paths: list[Path], *, on_progress: ProgressFn = None) -> dict:
    """Ingest selected .txt sources into the corpus."""
    results: list[dict] = []
    for path in paths:
        if path.suffix.lower() != ".txt":
            continue
        if on_progress:
            on_progress(f"Corpus: ingesting transcript {path.name}…")
        results.append(ingest_path(source="transcript", path=path))
    total = chunk_count()
    return {"ingested": len(results), "results": results, "total_chunks": total}


def initialize_corpus_quick(
    *,
    transcript_limit: int = 0,
    mml_chapters: list[int] | None = None,
    ingest_full_books: bool = False,
    on_progress: ProgressFn = None,
) -> dict:
    """
    Synchronous quick init — metadata and MML chapters if present (textbooks only).
    Does not require the FastAPI backend.
    """
    log: list[str] = []

    def step(msg: str) -> None:
        log.append(msg)
        if on_progress:
            on_progress(msg)

    step("Corpus init — scanning library…")
    books = scan_raw_library()
    for entry in books:
        ensure_metadata(entry.subject_id)

    mml_result = None
    mml = next((b for b in books if b.subject_id == "linear_algebra"), None)
    if mml and mml.file_present:
        chs = mml_chapters or mml.auto_chapters or [1, 2]
        step(f"Corpus init — ingesting Linear Algebra chapters {chs}…")
        try:
            mml_result = ingest_subject("linear_algebra", chapters=chs)
            step(f"  MML chunks: {mml_result.get('total_chunks', 0)}")
        except Exception as exc:
            step(f"  MML ingest skipped: {exc}")
    else:
        step("Corpus init — MML textbook not on disk (optional)")

    if transcript_limit > 0:
        step(f"Corpus init — ingesting up to {transcript_limit} latest transcripts…")
        tx_result = ingest_latest_transcripts(limit=transcript_limit)
        step(f"  Transcripts ingested: {tx_result.get('ingested', 0)}")
    else:
        step("Corpus init — skipping transcript ingest (textbooks only for notes RAG)")
        tx_result = {"ingested": 0}

    full_result = None
    if ingest_full_books:
        from backend.corpus.library import ingest_all_full_books

        step("Corpus init — ingesting full books on disk…")
        full_result = ingest_all_full_books(skip_indexed=True, log=step)

    total = chunk_count()
    step(f"Corpus init done — {total} total chunks · RAG {'ready' if total > 0 else 'empty'}")
    return {
        "total_chunks": total,
        "available": corpus_available(),
        "mml": mml_result,
        "transcripts": tx_result,
        "full_books": full_result,
        "log": log,
    }


def start_full_corpus_setup(
    *,
    transcript_limit: int = 5,
    mml_chapters: list[int] | None = None,
    ingest_full_books: bool = True,
) -> CorpusJob:
    """Background full setup (same as web Library → Build Knowledge Base)."""

    def worker(job: CorpusJob) -> dict:
        return run_auto_setup(
            job,
            mml_chapters=mml_chapters or [1, 2],
            transcript_limit=transcript_limit,
            ingest_full_books=ingest_full_books,
            skip_indexed_books=True,
            test_query=True,
        )

    return start_job("studio_corpus_setup", worker)


def poll_job(job_id: str | None = None) -> dict | None:
    job = get_job(job_id)
    if job is None:
        return None
    return {
        "job_id": job.job_id,
        "status": job.status,
        "progress": job.progress,
        "message": job.message,
        "logs": list(job.logs[-20:]),
        "error": job.error,
        "total_chunks": chunk_count(),
        "available": corpus_available(),
    }
