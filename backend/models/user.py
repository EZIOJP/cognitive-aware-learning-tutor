from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    password_plain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    face_embedding_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    progress: Mapped[list["WordProgress"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class WordProgress(Base):
    __tablename__ = "word_progress"
    __table_args__ = (UniqueConstraint("user_id", "word_id", name="uq_user_word"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    word_id: Mapped[int] = mapped_column(Integer, index=True)
    mastery: Mapped[int] = mapped_column(Integer, default=0)
    times_asked: Mapped[int] = mapped_column(Integer, default=0)
    times_correct: Mapped[int] = mapped_column(Integer, default=0)
    consecutive_correct: Mapped[int] = mapped_column(Integer, default=0)
    due_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    interval_days: Mapped[int] = mapped_column(Integer, default=0)
    is_suspended: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )

    user: Mapped[User] = relationship(back_populates="progress")
