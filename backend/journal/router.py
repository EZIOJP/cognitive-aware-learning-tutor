"""Daily journal — local-first."""

from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.core.auth import get_current_user
from backend.db.session import get_db
from backend.journal.schemas import JournalEntryCreate, JournalEntryUpdate
from backend.models import User
from backend.models.journal import JournalEntry

router = APIRouter(prefix="/api/journal", tags=["journal"])


def _today_str() -> str:
    return date.today().isoformat()


def _serialize_journal(row: JournalEntry) -> dict:
    return {
        "id": row.id,
        "entry_date": row.entry_date,
        "title": row.title,
        "content": row.content,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


@router.get("/summary")
def journal_summary(
    day: str | None = Query(None, description="YYYY-MM-DD or today"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    day_str = day if day and day not in ("today", "now") else _today_str()
    journal = (
        db.query(JournalEntry)
        .filter(JournalEntry.user_id == user.id, JournalEntry.entry_date == day_str)
        .order_by(JournalEntry.updated_at.desc())
        .first()
    )

    return {
        "day": day_str,
        "journal_written": journal is not None,
        "journal_entry": _serialize_journal(journal) if journal else None,
    }


@router.get("/entries")
def get_journal_entry(
    day: str | None = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    day_str = day if day and day not in ("today", "now") else _today_str()
    rows = (
        db.query(JournalEntry)
        .filter(JournalEntry.user_id == user.id, JournalEntry.entry_date == day_str)
        .order_by(JournalEntry.updated_at.desc())
        .all()
    )
    return {"day": day_str, "entries": [_serialize_journal(r) for r in rows]}


@router.post("/entries")
def upsert_journal_entry(
    body: JournalEntryCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    day_str = body.entry_date or _today_str()
    existing = (
        db.query(JournalEntry)
        .filter(JournalEntry.user_id == user.id, JournalEntry.entry_date == day_str)
        .first()
    )
    now = datetime.now(timezone.utc)
    if existing:
        existing.content = body.content
        if body.title is not None:
            existing.title = body.title
        existing.updated_at = now
        db.commit()
        db.refresh(existing)
        return {"entry": _serialize_journal(existing), "created": False}

    row = JournalEntry(
        user_id=user.id,
        entry_date=day_str,
        title=body.title,
        content=body.content,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"entry": _serialize_journal(row), "created": True}


@router.patch("/entries/{entry_id}")
def update_journal_entry(
    entry_id: int,
    body: JournalEntryUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    row = (
        db.query(JournalEntry)
        .filter(JournalEntry.id == entry_id, JournalEntry.user_id == user.id)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Entry not found")
    if body.title is not None:
        row.title = body.title
    if body.content is not None:
        row.content = body.content
    row.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)
    return {"entry": _serialize_journal(row)}
