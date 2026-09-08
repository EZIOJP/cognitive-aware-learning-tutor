"""Runtime snapshot for native C++ enforcer (same SQLite as Python)."""

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base


class EnforcerRuntime(Base):
    """Python writes; C++ CALTEnforcer service reads — shared DB contract."""

    __tablename__ = "enforcer_runtime"
    __table_args__ = (UniqueConstraint("user_id", name="uq_enforcer_runtime_user"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    hard_block_armed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    gate_locked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    incubation_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    exes_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    note: Mapped[str] = mapped_column(String(240), default="", nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
