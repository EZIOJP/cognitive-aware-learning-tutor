"""Study Loop read-gate sessions (same SQLite DB as ReviewCard)."""

from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base


class StudyLoopSession(Base):
    """One tag's read → practice loop. Practice always goes through handler.start_session."""

    __tablename__ = "study_loop_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    tag: Mapped[str] = mapped_column(String(160), index=True)
    read_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    read_card_ids_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    practice_quiz_session_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )
