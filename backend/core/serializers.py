"""Safe serialization of domain models for API responses."""

from __future__ import annotations

from datetime import datetime

from backend.config import get_settings
from backend.models import User


def _iso(dt: datetime | None) -> str | None:
    if not dt:
        return None
    return dt.isoformat()


def password_field_for_admin(user: User) -> str:
    settings = get_settings()
    if not settings.expose_password_plain:
        return "(hidden — set EXPOSE_PASSWORD_PLAIN=true only for local dev)"
    return user.password_plain or "(not stored — reset it)"


def user_admin_payload(user: User, *, progress_rows: int = 0, mastered_rows: int = 0) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "password": password_field_for_admin(user),
        "created_at": _iso(user.created_at),
        "is_admin": bool(user.is_admin),
        "progress_rows": progress_rows,
        "mastered_rows": mastered_rows,
    }
