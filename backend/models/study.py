from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base


class FocusEvent(Base):
    __tablename__ = "focus_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    session_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    event_type: Mapped[str] = mapped_column(String(32))
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    pomodoro_mode: Mapped[str] = mapped_column(String(16), default="focus")
    started_at: Mapped[int] = mapped_column(Integer)
    ended_at: Mapped[int | None] = mapped_column(Integer, nullable=True)


class LectureNote(Base):
    __tablename__ = "lecture_notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    filename: Mapped[str] = mapped_column(String(255), unique=True)
    title: Mapped[str] = mapped_column(String(255))
    topic: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    source: Mapped[str] = mapped_column(String(32), default="manual")
    transcript_file: Mapped[str | None] = mapped_column(String(255), nullable=True)
    section_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[int] = mapped_column(Integer)
    folder_path: Mapped[str] = mapped_column(String(512), default="", index=True)
    kind: Mapped[str] = mapped_column(String(32), default="lecture", index=True)
    relative_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    read_scroll_top: Mapped[int] = mapped_column(Integer, default=0)
    bookmark_scroll_top: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[int | None] = mapped_column(Integer, nullable=True)
