"""SQLite index + helpers for lecture notes knowledge base."""

from __future__ import annotations

import time

from sqlalchemy.orm import Session

from backend.models.study import LectureNote
from backend.transcripts.library import normalize_folder_path, note_storage_path


def save_note_record(
    db: Session,
    *,
    user_id: int,
    filename: str,
    title: str,
    topic: str | None = None,
    source: str = "manual",
    transcript_file: str | None = None,
    content: str = "",
    folder_path: str = "",
    kind: str = "lecture",
    relative_path: str | None = None,
) -> LectureNote:
    folder = normalize_folder_path(folder_path)
    rel = (relative_path or filename).replace("\\", "/")
    section_count = content.count("\n## ") + (1 if content.startswith("## ") else 0)
    row = LectureNote(
        user_id=user_id,
        filename=rel,
        relative_path=rel,
        folder_path=folder,
        kind=kind,
        title=title,
        topic=topic,
        source=source,
        transcript_file=transcript_file,
        section_count=max(1, section_count),
        created_at=int(time.time()),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_note_records(
    db: Session,
    user_id: int,
    *,
    topic: str | None = None,
    search: str | None = None,
    folder_path: str | None = None,
) -> list[LectureNote]:
    q = db.query(LectureNote).filter(LectureNote.user_id == user_id)
    if folder_path is not None:
        q = q.filter(LectureNote.folder_path == normalize_folder_path(folder_path))
    if topic:
        q = q.filter(LectureNote.topic == topic)
    if search:
        q = q.filter(LectureNote.title.ilike(f"%{search}%"))
    return q.order_by(LectureNote.created_at.desc()).all()


def list_topics(db: Session, user_id: int) -> list[str]:
    rows = (
        db.query(LectureNote.topic)
        .filter(LectureNote.user_id == user_id, LectureNote.topic.isnot(None))
        .distinct()
        .all()
    )
    return sorted({r[0] for r in rows if r[0]})


def row_to_item(row: LectureNote) -> dict:
    rel = note_storage_path(row)
    return {
        "filename": rel,
        "relative_path": rel,
        "title": row.title,
        "topic": row.topic,
        "source": row.source,
        "kind": row.kind or "lecture",
        "folder_path": row.folder_path or "",
        "section_count": row.section_count,
        "created_at": row.created_at,
        "modified": row.created_at,
        "read_scroll_top": row.read_scroll_top or 0,
        "bookmark_scroll_top": row.bookmark_scroll_top,
        "size_bytes": 0,
    }
