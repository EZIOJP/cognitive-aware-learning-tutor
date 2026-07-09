"""Shared helpers for querying desktop tracker sessions across users."""

from __future__ import annotations

from sqlalchemy.orm import Session

from backend.models import User


def _admin_user(db: Session) -> User | None:
    return db.query(User).filter(User.username == "admin").first()


def _demo_user(db: Session) -> User | None:
    return db.query(User).filter(User.username == "demo").first()


def tracker_user_ids(db: Session, user: User) -> list[int]:
    """
    User IDs whose desktop_tracker rows belong to this viewer.

    The standalone tracker writes as **admin** by default. In local single-user
    mode, every logged-in user should see those sessions (plus legacy demo rows).
    """
    ids: list[int] = [user.id]
    admin = _admin_user(db)
    if admin and admin.id not in ids:
        ids.append(admin.id)
    demo = _demo_user(db)
    if demo and demo.id not in ids:
        ids.append(demo.id)
    return ids


def primary_tracker_user_id(db: Session) -> int:
    """User id used when backfilling CSV → tracked_sessions."""
    admin = _admin_user(db)
    if admin:
        return admin.id
    demo = _demo_user(db)
    if demo:
        return demo.id
    return 1
