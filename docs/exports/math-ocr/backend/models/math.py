from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base


class MathQuestionTemplate(Base):
    __tablename__ = "math_question_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(160), index=True)
    topic: Mapped[str] = mapped_column(String(80), index=True, default="Arithmetic")
    operation: Mapped[str] = mapped_column(String(40), default="add")
    min_value: Mapped[int] = mapped_column(Integer, default=1)
    max_value: Mapped[int] = mapped_column(Integer, default=20)
    number_type: Mapped[str] = mapped_column(String(20), default="any")
    decimal_places: Mapped[int] = mapped_column(Integer, default=0)
    points: Mapped[int] = mapped_column(Integer, default=10)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
