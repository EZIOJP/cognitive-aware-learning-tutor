from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base


class MathQuestion(Base):
    """Imported static math problem (bank). Format extensible via metadata_json."""

    __tablename__ = "math_questions"
    __table_args__ = (
        UniqueConstraint("topic", "external_id", name="uq_math_question_topic_external"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    external_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    topic: Mapped[str] = mapped_column(String(80), index=True)
    prompt: Mapped[str] = mapped_column(String(1000))
    expected_answer: Mapped[str] = mapped_column(String(500))
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    latex: Mapped[str | None] = mapped_column(Text, nullable=True)
    difficulty: Mapped[str | None] = mapped_column(String(20), nullable=True)
    answer_format: Mapped[str | None] = mapped_column(String(40), nullable=True)
    tags_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str | None] = mapped_column(String(40), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))


class MathAttempt(Base):
    __tablename__ = "math_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    template_id: Mapped[int | None] = mapped_column(
        ForeignKey("math_question_templates.id"), nullable=True, index=True
    )
    question_id: Mapped[int | None] = mapped_column(
        ForeignKey("math_questions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    generated_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    topic: Mapped[str] = mapped_column(String(80), index=True)
    prompt: Mapped[str] = mapped_column(String(1000))
    expected_answer: Mapped[str] = mapped_column(String(500))
    user_answer: Mapped[str] = mapped_column(String(500))
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False)
    mastery_delta: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
