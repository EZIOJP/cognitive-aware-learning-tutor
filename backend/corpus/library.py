"""Scan raw library, organize uploads, and run one-click corpus setup."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from backend.corpus.converters import find_source_file, load_metadata
from backend.corpus.ingest import ingest_path
from backend.corpus.jobs import CorpusJob, _append_log
from backend.corpus.paths import RAW_LIBRARY_DIR, resolve_repo_path
from backend.corpus.registry import chunk_count, list_documents, verify_document
from backend.corpus.health import get_corpus_health
from backend.corpus.purge import purge_test_documents
from backend.corpus.retrieve import corpus_available, hybrid_retrieve
from backend.paths import ROOT, TRANSCRIPTS_DIR

SETUP_LOG = ROOT / "data" / "logs" / "corpus_setup_latest.log"

# Subjects ingested as whole books (PDF/EPUB), not chapter slices.
FULL_BOOK_SUBJECTS: tuple[str, ...] = (
    "foundations",
    "statistics",
    "ml_systems",
    "ai_context",
)


def _pandoc_available() -> bool:
    return shutil.which("pandoc") is not None

SUBJECT_CATALOG: list[dict[str, Any]] = [
    {
        "id": "linear_algebra",
        "label": "Mathematics for Machine Learning",
        "short_label": "MML (Linear Algebra)",
        "description": "Primary textbook anchor — ingest chapters 1–2 first.",
        "ingest_priority": 1,
        "auto_chapters": [1, 2],
    },
    {
        "id": "statistics",
        "label": "Practical Statistics for Data Scientists",
        "short_label": "Statistics",
        "description": "Full-book PDF ingest for stats reference and gap-driven retrieval.",
        "ingest_priority": 4,
        "auto_chapters": None,
    },
    {
        "id": "foundations",
        "label": "Data Science from Scratch",
        "short_label": "DS from Scratch",
        "description": "Full-book PDF ingest — Python and ML foundations.",
        "ingest_priority": 3,
        "auto_chapters": None,
    },
    {
        "id": "ml_systems",
        "label": "Designing Machine Learning Systems",
        "short_label": "ML Systems",
        "description": "Full-book PDF ingest — production ML workflows.",
        "ingest_priority": 4,
        "auto_chapters": None,
    },
    {
        "id": "ai_context",
        "label": "AI: A Guide for Thinking Humans",
        "short_label": "AI Context",
        "description": "Full-book PDF ingest — conceptual AI background.",
        "ingest_priority": 5,
        "auto_chapters": None,
    },
]


@dataclass(frozen=True)
class BookSlot:
    subject_id: str
    label: str
    short_label: str
    description: str
    ingest_priority: int
    expected_filename: str
    document_id: str
    format: str
    file_present: bool
    file_size_bytes: int
    metadata_present: bool
    ingested_chunks: int
    auto_chapters: list[int] | None


def _subject_folder(subject_id: str) -> Path:
    return RAW_LIBRARY_DIR / subject_id


def ensure_metadata(subject_id: str) -> Path:
    folder = _subject_folder(subject_id)
    folder.mkdir(parents=True, exist_ok=True)
    meta_path = folder / "metadata.json"
    example = folder / "metadata.json.example"
    if not meta_path.is_file() and example.is_file():
        shutil.copy(example, meta_path)
    return meta_path


def scan_book_slot(entry: dict[str, Any]) -> BookSlot:
    subject_id = entry["id"]
    folder = _subject_folder(subject_id)
    ensure_metadata(subject_id)
    meta = load_metadata(folder)
    src = find_source_file(folder, meta)
    doc_id = meta.get("document_id") or ""
    chunks = chunk_count(document_id=doc_id) if doc_id else 0
    return BookSlot(
        subject_id=subject_id,
        label=entry["label"],
        short_label=entry["short_label"],
        description=entry["description"],
        ingest_priority=entry["ingest_priority"],
        expected_filename=meta.get("filename") or "",
        document_id=doc_id,
        format=meta.get("format") or "",
        file_present=src is not None,
        file_size_bytes=src.stat().st_size if src else 0,
        metadata_present=(folder / "metadata.json").is_file(),
        ingested_chunks=chunks,
        auto_chapters=entry.get("auto_chapters"),
    )


def scan_raw_library() -> list[BookSlot]:
    return [scan_book_slot(e) for e in SUBJECT_CATALOG]


def get_corpus_overview() -> dict[str, Any]:
    books = scan_raw_library()
    docs = list_documents()
    doc_rows = [
        {
            "document_id": d.document_id,
            "title": d.title,
            "source_type": d.source_type,
            "chunks": chunk_count(document_id=d.document_id),
            "source_path": d.source_path,
        }
        for d in docs
    ]
    transcripts = sorted(TRANSCRIPTS_DIR.glob("*.txt"), key=lambda p: p.stat().st_mtime, reverse=True)
    return {
        "books": [
            {
                "subject_id": b.subject_id,
                "label": b.label,
                "short_label": b.short_label,
                "description": b.description,
                "expected_filename": b.expected_filename,
                "document_id": b.document_id,
                "format": b.format,
                "file_present": b.file_present,
                "file_size_bytes": b.file_size_bytes,
                "metadata_present": b.metadata_present,
                "ingested_chunks": b.ingested_chunks,
                "auto_chapters": b.auto_chapters,
                "ready": b.file_present and b.metadata_present,
            }
            for b in books
        ],
        "corpus": {
            "available": corpus_available(),
            "total_chunks": chunk_count(),
            "documents": doc_rows,
        },
        "transcripts": [
            {
                "filename": p.name,
                "size_bytes": p.stat().st_size,
                "ingested_chunks": chunk_count(document_id=f"transcript_{p.stem}"),
            }
            for p in transcripts[:20]
        ],
        "paths": {
            "raw_library": str(RAW_LIBRARY_DIR),
            "transcripts": str(TRANSCRIPTS_DIR),
            "setup_log": str(SETUP_LOG),
        },
        "environment": {
            "pandoc_available": _pandoc_available(),
        },
        "health": get_corpus_health(),
    }


def read_setup_log_tail(lines: int = 80) -> str:
    if not SETUP_LOG.is_file():
        return ""
    text = SETUP_LOG.read_text(encoding="utf-8", errors="replace")
    return "\n".join(text.splitlines()[-lines:])


def save_upload(subject_id: str, filename: str, data: bytes) -> dict[str, Any]:
    entry = next((e for e in SUBJECT_CATALOG if e["id"] == subject_id), None)
    if entry is None:
        raise ValueError(f"Unknown subject: {subject_id}")
    folder = _subject_folder(subject_id)
    ensure_metadata(subject_id)
    meta = load_metadata(folder)
    dest_name = meta.get("filename") or filename
    dest = folder / dest_name
    dest.write_bytes(data)
    slot = scan_book_slot(entry)
    return {
        "subject_id": subject_id,
        "saved_as": str(dest.relative_to(ROOT)).replace("\\", "/"),
        "size_bytes": dest.stat().st_size,
        "book": {
            "file_present": slot.file_present,
            "expected_filename": slot.expected_filename,
        },
    }


def ingest_subject(subject_id: str, *, chapters: list[int] | None = None) -> dict[str, Any]:
    entry = next((e for e in SUBJECT_CATALOG if e["id"] == subject_id), None)
    if entry is None:
        raise ValueError(f"Unknown subject: {subject_id}")
    folder = _subject_folder(subject_id)
    if not find_source_file(folder, load_metadata(folder)):
        raise FileNotFoundError(f"No book file in {folder}")

    chapter_list = chapters if chapters is not None else entry.get("auto_chapters")
    results: list[dict[str, Any]] = []
    if chapter_list:
        for ch in chapter_list:
            results.append(
                ingest_path(source="textbook", path=folder, chapter=ch)
            )
    else:
        results.append(ingest_path(source="textbook", path=folder, chapter=None))

    meta = load_metadata(folder)
    doc_id = meta.get("document_id") or ""
    verify = verify_document(doc_id) if doc_id else {"chunk_count": 0}
    return {
        "subject_id": subject_id,
        "ingest_results": results,
        "verify": verify,
        "total_chunks": chunk_count(document_id=doc_id) if doc_id else chunk_count(),
    }


def ingest_all_full_books(
    *,
    skip_indexed: bool = True,
    force: bool = False,
    log: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Ingest every ready full-book slot in raw_library (whole PDF/EPUB, not MML chapters)."""
    results: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []

    for subject_id in FULL_BOOK_SUBJECTS:
        entry = next((e for e in SUBJECT_CATALOG if e["id"] == subject_id), None)
        if entry is None:
            continue
        slot = scan_book_slot(entry)
        if not slot.file_present:
            if log:
                log(f"  Skip {subject_id}: no file on disk")
            skipped.append({"subject_id": subject_id, "reason": "missing_file"})
            continue
        if slot.format == "epub" and not _pandoc_available():
            if log:
                log(f"  Skip {subject_id}: EPUB requires pandoc on PATH")
            skipped.append({"subject_id": subject_id, "reason": "pandoc_required"})
            continue
        if skip_indexed and not force and slot.ingested_chunks > 0:
            if log:
                log(f"  Skip {subject_id}: already indexed ({slot.ingested_chunks} chunks)")
            skipped.append({"subject_id": subject_id, "reason": "already_indexed"})
            continue
        if log:
            log(f"  Ingesting full book: {slot.label}...")
        try:
            result = ingest_subject(subject_id, chapters=None)
            chunk_n = result.get("verify", {}).get("chunk_count", 0)
            if log:
                log(f"    -> {chunk_n} chunks in registry")
            results.append({"subject_id": subject_id, **result})
        except Exception as exc:  # noqa: BLE001
            if log:
                log(f"    ERROR: {exc}")
            results.append({"subject_id": subject_id, "error": str(exc)})

    return {
        "ingested": len([r for r in results if "error" not in r]),
        "skipped": skipped,
        "results": results,
        "total_chunks": chunk_count(),
    }


def ingest_latest_transcripts(*, limit: int = 3) -> dict[str, Any]:
    paths = sorted(TRANSCRIPTS_DIR.glob("*.txt"), key=lambda p: p.stat().st_mtime, reverse=True)
    results = []
    for path in paths[:limit]:
        results.append(ingest_path(source="transcript", path=path))
    return {"ingested": len(results), "results": results}


def run_auto_setup(
    job: CorpusJob,
    *,
    mml_chapters: list[int] | None = None,
    transcript_limit: int = 3,
    ingest_full_books: bool = True,
    skip_indexed_books: bool = True,
    test_query: bool = True,
) -> dict[str, Any]:
    log_lines: list[str] = []
    SETUP_LOG.parent.mkdir(parents=True, exist_ok=True)

    def log(line: str) -> None:
        log_lines.append(line)
        _append_log(job, line)

    steps = 7 if ingest_full_books else 6
    step = 0

    log("Step 1/{} — Scanning raw library".format(steps))
    purge_result = purge_test_documents()
    if purge_result["purged"]:
        log(f"  Removed {purge_result['purged']} test document(s) from registry")
    books = scan_raw_library()
    ready = [b for b in books if b.file_present]
    log(f"  {len(ready)}/{len(books)} books on disk")
    step += 1
    job.progress = step / steps

    log("Step 2/{} — Ensuring metadata.json in each folder".format(steps))
    for entry in SUBJECT_CATALOG:
        ensure_metadata(entry["id"])
    step += 1
    job.progress = step / steps

    mml = next(b for b in books if b.subject_id == "linear_algebra")
    mml_result: dict[str, Any] | None = None
    if mml.file_present:
        chs = mml_chapters or mml.auto_chapters or [1, 2]
        log(f"Step 3/{steps} — Ingesting MML chapters {chs}")
        mml_result = ingest_subject("linear_algebra", chapters=chs)
        log(f"  MML chunks in registry: {mml_result['verify'].get('chunk_count', 0)}")
    else:
        log(f"Step 3/{steps} — MML PDF missing; upload Mathematics_for_ML.pdf first")
    step += 1
    job.progress = step / steps

    log(f"Step 4/{steps} — Ingesting up to {transcript_limit} latest lecture transcripts")
    tx_result = ingest_latest_transcripts(limit=transcript_limit)
    log(f"  Transcripts ingested: {tx_result['ingested']}")
    step += 1
    job.progress = step / steps

    full_books_result: dict[str, Any] | None = None
    if ingest_full_books:
        log(f"Step 5/{steps} — Ingesting full PDF books on disk")
        full_books_result = ingest_all_full_books(skip_indexed=skip_indexed_books, log=log)
        log(f"  Full books ingested: {full_books_result['ingested']}")
        if full_books_result["skipped"]:
            log(f"  Skipped: {len(full_books_result['skipped'])} slot(s)")
        step += 1
        job.progress = step / steps

    status_step = step + 1
    log(f"Step {status_step}/{steps} — Corpus status")
    overview = get_corpus_overview()
    total = overview["corpus"]["total_chunks"]
    log(f"  Total chunks: {total}")
    step = status_step
    job.progress = step / steps

    query_hits: list[dict[str, Any]] = []
    query_step = step + 1
    if test_query and total > 0:
        log(f'Step {query_step}/{steps} — Test query: "What is an eigenvalue?"')
        query_hits = hybrid_retrieve("What is an eigenvalue?", subject_tags=["linear_algebra"], top_k=3)
        log(f"  Hits: {len(query_hits)}")
    else:
        log(f"Step {query_step}/{steps} — Skipped test query (empty corpus)")
    job.progress = 1.0

    report = "\n".join(log_lines)
    SETUP_LOG.write_text(
        "============================================================\n"
        f"Corpus auto-setup (GUI)\n"
        f"Project: {ROOT}\n"
        "============================================================\n\n"
        f"{report}\n\n"
        f"JSON overview:\n{json.dumps(overview, indent=2)}\n",
        encoding="utf-8",
    )

    return {
        "overview": overview,
        "mml": mml_result,
        "transcripts": tx_result,
        "full_books": full_books_result,
        "query_hit_count": len(query_hits),
    }
