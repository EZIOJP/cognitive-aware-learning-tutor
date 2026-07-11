"""Initialize and inspect the Knowledge Base (RAG corpus) from Transcript Notes Studio."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from backend.corpus.jobs import CorpusJob, get_job, start_job
from backend.corpus.registry import chunk_count
from backend.corpus.retrieve import corpus_available


ProgressFn = Callable[[str], None] | None


def get_corpus_summary() -> dict:
    """Lightweight status for the Studio UI (notes RAG = textbooks only)."""
    try:
        from backend.corpus.notes_rag_status import assess_notes_rag

        assessment = assess_notes_rag()
        return {
            "available": bool(assessment.get("total_chunks", 0) > 0),
            "total_chunks": assessment.get("total_chunks", 0),
            "document_count": (
                int(assessment.get("textbook_count", 0))
                + int(assessment.get("transcript_count", 0))
                + int(assessment.get("note_count", 0))
            ),
            "textbook_count": assessment.get("textbook_count", 0),
            "notes_rag_count": assessment.get("textbook_count", 0),
            "transcript_count": assessment.get("transcript_count", 0),
            "note_count": assessment.get("note_count", 0),
            "by_source_type": {
                "textbook": assessment.get("textbook_count", 0),
                "transcript": assessment.get("transcript_count", 0),
                "note": assessment.get("note_count", 0),
            },
            "notes_rag_source_types": assessment.get("notes_rag_source_types", ["textbook"]),
            "retrieval_backend": assessment.get("retrieval_backend", "unknown"),
            "healthy": bool(assessment.get("usable")),
            "notes_rag_status": assessment.get("status"),
            "notes_rag_summary": assessment.get("summary"),
            "needs_rebuild": assessment.get("needs_rebuild"),
            "skip_rebuild": assessment.get("skip_rebuild"),
            "smoke_hits": assessment.get("smoke_hits"),
            "issues": list(assessment.get("reasons") or []),
        }
    except Exception as exc:
        try:
            return {
                "available": corpus_available(),
                "total_chunks": chunk_count() if corpus_available() else 0,
                "document_count": 0,
                "healthy": False,
                "notes_rag_status": "broken",
                "needs_rebuild": True,
                "issues": [str(exc)],
            }
        except Exception as inner:
            return {
                "available": False,
                "total_chunks": 0,
                "document_count": 0,
                "healthy": False,
                "notes_rag_status": "broken",
                "needs_rebuild": True,
                "issues": [str(inner)],
            }


def ingest_transcript_paths(paths: list[Path], *, on_progress: ProgressFn = None) -> dict:
    """Blocked for notes RAG — transcripts must not enter the notes corpus."""
    raise RuntimeError(
        "Transcript ingest is disabled for notes RAG. "
        "Only textbooks are indexed. Generate notes still retrieves textbooks; "
        "use Study Library quiz handoff later if you need lecture chunks indexed."
    )


def initialize_corpus_quick(
    *,
    transcript_limit: int = 0,
    mml_chapters: list[int] | None = None,
    ingest_full_books: bool = False,
    on_progress: ProgressFn = None,
    force: bool = False,
) -> dict:
    """
    Ensure textbooks are indexed for notes RAG. Skips when already usable unless force=True.
    Never ingests transcripts (transcript_limit ignored / forced to 0).
    """
    from backend.corpus.notes_rag_status import ensure_notes_rag_textbooks

    if transcript_limit and transcript_limit > 0 and on_progress:
        on_progress("Ignoring transcript ingest — notes RAG is textbooks only")
    return ensure_notes_rag_textbooks(
        force=force,
        ingest_full_books=ingest_full_books,
        mml_chapters=mml_chapters,
        on_progress=on_progress,
    )


def start_full_corpus_setup(
    *,
    transcript_limit: int = 0,
    mml_chapters: list[int] | None = None,
    ingest_full_books: bool = True,
    force: bool = False,
) -> CorpusJob:
    """Background ensure textbooks — skips when healthy unless force=True."""

    def worker(job: CorpusJob) -> dict:
        from backend.corpus.notes_rag_status import ensure_notes_rag_textbooks

        def log(msg: str) -> None:
            job.message = msg
            if hasattr(job, "logs"):
                job.logs.append(msg)

        return ensure_notes_rag_textbooks(
            force=force,
            ingest_full_books=ingest_full_books,
            mml_chapters=mml_chapters or [1, 2],
            on_progress=log,
        )

    return start_job("studio_corpus_setup", worker)


def reset_and_rebuild_textbooks(
    *,
    mml_chapters: list[int] | None = None,
    ingest_full_books: bool = True,
    on_progress: ProgressFn = None,
    force: bool = True,
) -> dict:
    """Force wipe + textbook rebuild (explicit force rebuild)."""
    from backend.corpus.notes_rag_status import ensure_notes_rag_textbooks

    return ensure_notes_rag_textbooks(
        force=True,
        ingest_full_books=ingest_full_books,
        mml_chapters=mml_chapters,
        on_progress=on_progress,
    )


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
