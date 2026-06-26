"""Ingest orchestration for transcripts, notes, and textbooks."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Any

from backend.corpus.bm25_index import rebuild_bm25_from_registry
from backend.corpus.chunker import TextChunk, chunk_markdown
from backend.corpus.converters import file_to_markdown, find_source_file, load_metadata, describe_missing_source
from backend.corpus.registry import (
    delete_document_chunks,
    insert_chunk,
    upsert_document,
)
from backend.corpus.vector_store import VectorStore
from backend.paths import NOTES_DIR, TRANSCRIPTS_DIR
from backend.transcripts.cleanup import clean_transcript
from backend.transcripts.embedding import encode_texts

log = logging.getLogger(__name__)


def _embed_chunks(chunks: list[TextChunk]) -> list[Any]:
    texts = [c.text for c in chunks]
    vectors = encode_texts(texts)
    if vectors is None:
        return [None] * len(chunks)
    return [vectors[i] for i in range(len(chunks))]


def ingest_markdown(
    *,
    markdown: str,
    document_id: str,
    document_title: str,
    source_type: str,
    subject_tags: list[str] | None = None,
    category: str = "",
    source_path: str = "",
    chapter: int | None = None,
    replace: bool = True,
    db_path: Path | None = None,
) -> dict[str, Any]:
    if replace:
        delete_document_chunks(document_id, db_path=db_path)

    upsert_document(
        document_id=document_id,
        title=document_title,
        source_type=source_type,
        category=category,
        subject_tags=subject_tags,
        source_path=source_path,
        db_path=db_path,
    )

    chunks = chunk_markdown(
        markdown,
        document_breadcrumb=document_title,
        chapter=chapter,
    )
    embeddings = _embed_chunks(chunks)
    stored: list[str] = []
    records = []

    for i, c in enumerate(chunks):
        emb = embeddings[i] if i < len(embeddings) else None
        cid = insert_chunk(
            document_id=document_id,
            document_title=document_title,
            breadcrumb=c.breadcrumb,
            raw_payload=c.text,
            modality_type=c.modality_type,
            spatial_location=c.spatial_location,
            subject_tags=subject_tags,
            source_type=source_type,
            chunk_id=c.chunk_id,
            embedding=emb,
            db_path=db_path,
        )
        stored.append(cid)
        from backend.corpus.registry import get_chunk

        rec = get_chunk(cid, db_path=db_path)
        if rec:
            records.append(rec)

    rebuild_bm25_from_registry(db_path=db_path)
    VectorStore().upsert_chunks(records)

    return {
        "document_id": document_id,
        "chunks_ingested": len(stored),
        "chunk_ids": stored[:5],
    }


def ingest_textbook_folder(
    folder: Path,
    *,
    chapter: int | None = None,
    user_id: int | None = None,
    seed_kg: bool = True,
) -> dict[str, Any]:
    meta = load_metadata(folder)
    src = find_source_file(folder, meta)
    if src is None:
        raise FileNotFoundError(describe_missing_source(folder, meta))

    document_id = meta.get("document_id") or src.stem
    title = meta.get("title") or src.stem
    subject_tags = meta.get("subject_tags") or []
    category = meta.get("category") or "textbook"

    md = file_to_markdown(src, chapter=chapter)
    result = ingest_markdown(
        markdown=md,
        document_id=document_id,
        document_title=title,
        source_type="textbook",
        subject_tags=subject_tags,
        category=category,
        source_path=str(src),
        chapter=chapter,
        replace=chapter is None,
    )

    if seed_kg and document_id == "mml_2021_deisenroth" and chapter is not None:
        try:
            from backend.db.base import SessionLocal  # noqa: PLC0415
            from backend.corpus.kg_anchor import extract_equation_nodes, seed_mml_concepts  # noqa: PLC0415

            db = SessionLocal()
            try:
                seed_mml_concepts(db, user_id=user_id, chapters=[chapter], document_id=document_id)
                extract_equation_nodes(
                    db,
                    user_id=user_id,
                    chapter=chapter,
                    markdown=md,
                    document_id=document_id,
                )
            finally:
                db.close()
        except Exception as exc:  # noqa: BLE001
            log.warning("KG seed skipped: %s", exc)

    result["source_path"] = str(src)
    result["chapter"] = chapter
    return result


def ingest_transcript(path: Path, *, user_id: int | None = None) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8")
    cleaned = clean_transcript(raw)
    doc_id = f"transcript_{path.stem}"
    result = ingest_markdown(
        markdown=cleaned,
        document_id=doc_id,
        document_title=path.stem,
        source_type="transcript",
        subject_tags=["lecture"],
        source_path=str(path),
    )
    result["kg_alignments"] = _align_transcript_chunks(doc_id, user_id=user_id)
    return result


def _align_transcript_chunks(document_id: str, *, user_id: int | None = None) -> int:
    """Link lecture chunks to MML concept nodes (chapters 1–2)."""
    from backend.corpus.kg_anchor import MML_CONCEPT_SEEDS, align_lecture_chunk_to_concepts
    from backend.corpus.registry import list_chunks

    concept_labels = [
        label for ch in (1, 2) for label, _ in MML_CONCEPT_SEEDS.get(ch, [])
    ]
    if not concept_labels:
        return 0
    try:
        from backend.db.base import SessionLocal  # noqa: PLC0415

        db = SessionLocal()
        total = 0
        try:
            for rec in list_chunks(document_id=document_id):
                links = align_lecture_chunk_to_concepts(
                    db,
                    user_id=user_id,
                    chunk_id=rec.chunk_id,
                    chunk_text=rec.raw_payload,
                    concept_labels=concept_labels,
                )
                total += len(links)
            db.commit()
        finally:
            db.close()
        return total
    except Exception as exc:  # noqa: BLE001
        log.warning("Lecture KG alignment skipped: %s", exc)
        return 0


def ingest_note(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    rel = path.relative_to(NOTES_DIR) if path.is_relative_to(NOTES_DIR) else path.name
    doc_id = f"note_{uuid.uuid5(uuid.NAMESPACE_URL, str(rel))}"
    return ingest_markdown(
        markdown=text,
        document_id=doc_id,
        document_title=str(rel),
        source_type="note",
        subject_tags=["lecture"],
        source_path=str(path),
    )


def ingest_path(
    *,
    source: str,
    path: Path,
    chapter: int | None = None,
) -> dict[str, Any]:
    source = source.lower().strip()
    if source == "textbook":
        if path.is_dir():
            return ingest_textbook_folder(path, chapter=chapter)
        if path.is_file():
            return ingest_textbook_folder(path.parent, chapter=chapter)
        raise FileNotFoundError(path)
    if source == "transcript":
        if path.is_dir():
            results = [ingest_transcript(p) for p in sorted(path.glob("*.txt"))]
            return {"ingested": len(results), "results": results}
        return ingest_transcript(path)
    if source == "note":
        if path.is_dir():
            results = [ingest_note(p) for p in sorted(path.rglob("*.md"))]
            return {"ingested": len(results), "results": results}
        return ingest_note(path)
    raise ValueError(f"Unknown source type: {source}")
