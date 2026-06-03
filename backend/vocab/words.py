"""Word list helpers — delegates to repository (DB + JSON mirror)."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from backend.vocab.normalize import GROUP_SIZE, normalize_words
from backend.vocab.repository import load_words as repo_load_words, replace_all_words

__all__ = [
    "GROUP_SIZE",
    "load_words",
    "save_words",
    "normalize_words",
]


def load_words(db: Session | None = None) -> list[dict[str, Any]]:
    return repo_load_words(db)


def save_words(words: list[dict[str, Any]], db: Session | None = None) -> None:
    if db is None:
        from backend.db.base import SessionLocal

        with SessionLocal() as session:
            replace_all_words(session, words)
        return
    replace_all_words(db, words)
