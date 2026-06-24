"""Per-question spaced-repetition cards (all quiz domains)."""

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base


class ReviewCard(Base):
    __tablename__ = "review_cards"
    __table_args__ = (UniqueConstraint("user_id", "item_key", name="uq_review_cards_user_item"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    domain: Mapped[str] = mapped_column(String(24), index=True)
    item_key: Mapped[str] = mapped_column(String(200), index=True)
    label: Mapped[str] = mapped_column(String(300), default="")
    topic: Mapped[str | None] = mapped_column(String(160), nullable=True)
    note_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    format: Mapped[str] = mapped_column(String(20), default="mcq")
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    srs_json: Mapped[str] = mapped_column(Text, default="{}")
    deck_id: Mapped[int | None] = mapped_column(
        ForeignKey("quiz_decks.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )


class QuizDeck(Base):
    """User-authored quiz collections."""

    __tablename__ = "quiz_decks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200), default="My Quiz")
    topic: Mapped[str | None] = mapped_column(String(160), nullable=True)
    domain: Mapped[str] = mapped_column(String(24), default="study")
    items_json: Mapped[str] = mapped_column(Text, default="[]")
    time_limit_sec: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )
