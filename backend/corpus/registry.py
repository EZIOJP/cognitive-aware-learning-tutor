"""SQLite chunk registry with WAL mode."""

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator

import numpy as np

from backend.corpus.paths import ensure_corpus_dirs


def _db_path(db_path: Path | None = None) -> Path:
    if db_path is not None:
        return db_path
    from backend.corpus.paths import get_registry_db

    return get_registry_db()


@dataclass(frozen=True)
class ChunkRecord:
    chunk_id: str
    document_id: str
    document_title: str
    source_document_id: str
    breadcrumb: str
    modality_type: str
    spatial_location: int | None
    subject_tags: list[str]
    raw_payload: str
    source_type: str
    embedding: np.ndarray | None = None


@dataclass(frozen=True)
class DocumentRecord:
    document_id: str
    title: str
    source_type: str
    category: str
    subject_tags: list[str]
    source_path: str
    ingested_at: str


def _connect(db_path: Path | None = None) -> sqlite3.Connection:
    path = _db_path(db_path)
    ensure_corpus_dirs()
    conn = sqlite3.connect(str(path), timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_registry(db_path: Path | None = None) -> None:
    with _connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS documents (
                document_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                source_type TEXT NOT NULL,
                category TEXT,
                subject_tags TEXT,
                source_path TEXT,
                ingested_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS chunks (
                chunk_id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL,
                document_title TEXT NOT NULL,
                breadcrumb TEXT NOT NULL,
                modality_type TEXT NOT NULL DEFAULT 'narrative_text',
                spatial_location INTEGER,
                subject_tags TEXT,
                raw_payload TEXT NOT NULL,
                source_type TEXT NOT NULL,
                embedding_blob BLOB,
                FOREIGN KEY (document_id) REFERENCES documents(document_id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_chunks_document ON chunks(document_id);
            CREATE INDEX IF NOT EXISTS idx_chunks_modality ON chunks(modality_type);
            """
        )
        conn.commit()


@contextmanager
def registry_conn(db_path: Path | None = None) -> Iterator[sqlite3.Connection]:
    init_registry(db_path)
    conn = _connect(db_path)
    try:
        yield conn
    finally:
        conn.close()


def upsert_document(
    *,
    document_id: str,
    title: str,
    source_type: str,
    category: str = "",
    subject_tags: list[str] | None = None,
    source_path: str = "",
    db_path: Path | None = None,
) -> None:
    tags = json.dumps(subject_tags or [])
    now = datetime.now(UTC).isoformat()
    with registry_conn(db_path) as conn:
        conn.execute(
            """
            INSERT INTO documents (document_id, title, source_type, category, subject_tags, source_path, ingested_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(document_id) DO UPDATE SET
                title=excluded.title,
                source_type=excluded.source_type,
                category=excluded.category,
                subject_tags=excluded.subject_tags,
                source_path=excluded.source_path,
                ingested_at=excluded.ingested_at
            """,
            (document_id, title, source_type, category, tags, source_path, now),
        )
        conn.commit()


def delete_document_chunks(document_id: str, *, db_path: Path | None = None) -> int:
    with registry_conn(db_path) as conn:
        cur = conn.execute("DELETE FROM chunks WHERE document_id = ?", (document_id,))
        conn.commit()
        return int(cur.rowcount)


def insert_chunk(
    *,
    document_id: str,
    document_title: str,
    breadcrumb: str,
    raw_payload: str,
    modality_type: str = "narrative_text",
    spatial_location: int | None = None,
    subject_tags: list[str] | None = None,
    source_type: str = "textbook",
    chunk_id: str | None = None,
    embedding: np.ndarray | None = None,
    db_path: Path | None = None,
) -> str:
    cid = chunk_id or str(uuid.uuid4())
    blob = embedding.astype("float32").tobytes() if embedding is not None else None
    tags = json.dumps(subject_tags or [])
    with registry_conn(db_path) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO chunks (
                chunk_id, document_id, document_title, breadcrumb, modality_type,
                spatial_location, subject_tags, raw_payload, source_type, embedding_blob
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                cid,
                document_id,
                document_title,
                breadcrumb,
                modality_type,
                spatial_location,
                tags,
                raw_payload,
                source_type,
                blob,
            ),
        )
        conn.commit()
    return cid


def list_chunks(
    *,
    document_id: str | None = None,
    subject: str | None = None,
    db_path: Path | None = None,
) -> list[ChunkRecord]:
    with registry_conn(db_path) as conn:
        sql = "SELECT * FROM chunks"
        params: list[Any] = []
        clauses: list[str] = []
        if document_id:
            clauses.append("document_id = ?")
            params.append(document_id)
        if subject:
            clauses.append("subject_tags LIKE ?")
            params.append(f'%"{subject}"%')
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY spatial_location, breadcrumb"
        rows = conn.execute(sql, params).fetchall()
    return [_row_to_chunk(r) for r in rows]


def get_chunk(chunk_id: str, *, db_path: Path | None = None) -> ChunkRecord | None:
    with registry_conn(db_path) as conn:
        row = conn.execute("SELECT * FROM chunks WHERE chunk_id = ?", (chunk_id,)).fetchone()
    return _row_to_chunk(row) if row else None


def chunk_count(*, document_id: str | None = None, db_path: Path | None = None) -> int:
    with registry_conn(db_path) as conn:
        if document_id:
            row = conn.execute(
                "SELECT COUNT(*) AS c FROM chunks WHERE document_id = ?", (document_id,)
            ).fetchone()
        else:
            row = conn.execute("SELECT COUNT(*) AS c FROM chunks").fetchone()
    return int(row["c"]) if row else 0


def list_documents(*, db_path: Path | None = None) -> list[DocumentRecord]:
    with registry_conn(db_path) as conn:
        rows = conn.execute("SELECT * FROM documents ORDER BY ingested_at DESC").fetchall()
    out: list[DocumentRecord] = []
    for r in rows:
        out.append(
            DocumentRecord(
                document_id=r["document_id"],
                title=r["title"],
                source_type=r["source_type"],
                category=r["category"] or "",
                subject_tags=json.loads(r["subject_tags"] or "[]"),
                source_path=r["source_path"] or "",
                ingested_at=r["ingested_at"],
            )
        )
    return out


def all_chunks_with_embeddings(*, db_path: Path | None = None) -> list[ChunkRecord]:
    return list_chunks(db_path=db_path)


def _row_to_chunk(row: sqlite3.Row) -> ChunkRecord:
    emb = None
    if row["embedding_blob"]:
        emb = np.frombuffer(row["embedding_blob"], dtype="float32")
    return ChunkRecord(
        chunk_id=row["chunk_id"],
        document_id=row["document_id"],
        document_title=row["document_title"],
        source_document_id=row["document_id"],
        breadcrumb=row["breadcrumb"],
        modality_type=row["modality_type"],
        spatial_location=row["spatial_location"],
        subject_tags=json.loads(row["subject_tags"] or "[]"),
        raw_payload=row["raw_payload"],
        source_type=row["source_type"],
        embedding=emb,
    )


def verify_document(document_id: str, *, db_path: Path | None = None) -> dict[str, Any]:
    chunks = list_chunks(document_id=document_id, db_path=db_path)
    modalities: dict[str, int] = {}
    missing_breadcrumb = 0
    for c in chunks:
        modalities[c.modality_type] = modalities.get(c.modality_type, 0) + 1
        if not c.breadcrumb.strip():
            missing_breadcrumb += 1
    return {
        "document_id": document_id,
        "chunk_count": len(chunks),
        "modalities": modalities,
        "missing_breadcrumb": missing_breadcrumb,
        "sample_breadcrumbs": [c.breadcrumb for c in chunks[:5]],
    }
