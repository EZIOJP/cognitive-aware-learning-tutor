"""Word bank access — DB is source of truth when populated; JSON is bootstrap + mirror."""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.models.word import Word
from backend.paths import WORDS_PATH
from backend.vocab.normalize import normalize_words

log = logging.getLogger(__name__)


def _row_to_dict(row: Word) -> dict[str, Any]:
    return json.loads(row.content_json)


def count_words(db: Session) -> int:
    return db.query(Word).count()


def list_words_from_db(db: Session) -> list[dict[str, Any]]:
    rows = db.query(Word).order_by(Word.id).all()
    return [_row_to_dict(r) for r in rows]


def list_words_from_json_file() -> list[dict[str, Any]]:
    if not WORDS_PATH.exists():
        return []
    with open(WORDS_PATH, encoding="utf-8") as f:
        data = json.load(f)
    words = data if isinstance(data, list) else data.get("words", [])
    return normalize_words(words)


def persist_words_to_json(words: list[dict[str, Any]]) -> None:
    normalized = normalize_words(words)
    WORDS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(WORDS_PATH, "w", encoding="utf-8") as f:
        json.dump(normalized, f, ensure_ascii=False, indent=2)


def replace_all_words(db: Session, words: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = normalize_words(words)
    db.query(Word).delete()
    db.flush()
    mappings = [
        {
            "id": int(w["id"]),
            "word": str(w.get("word", "")),
            "group_number": int(w.get("group_number", 1)),
            "content_json": json.dumps(w, ensure_ascii=False),
        }
        for w in normalized
    ]
    if mappings:
        db.bulk_insert_mappings(Word, mappings)
    db.commit()
    persist_words_to_json(normalized)
    return normalized


def seed_words_from_json_if_empty(db: Session) -> int:
    if count_words(db) > 0:
        return 0
    file_words = list_words_from_json_file()
    if not file_words:
        log.info("words table empty and no words.json — skip seed")
        return 0
    replace_all_words(db, file_words)
    log.info("Seeded %d words from %s into database", len(file_words), WORDS_PATH)
    return len(file_words)


def load_words(db: Session | None = None) -> list[dict[str, Any]]:
    """
    Resolve word list: DB when rows exist (or words_source=db), else JSON file.
    """
    settings = get_settings()
    if db is None:
        from backend.db.base import SessionLocal

        with SessionLocal() as session:
            return _resolve_words(session, settings.words_source)
    return _resolve_words(db, settings.words_source)


def _resolve_words(db: Session, source: str) -> list[dict[str, Any]]:
    db_count = count_words(db)
    if source == "json":
        return list_words_from_json_file()
    if source == "db" and db_count > 0:
        return list_words_from_db(db)
    if db_count > 0:
        return list_words_from_db(db)
    return list_words_from_json_file()


def save_words(db: Session, words: list[dict[str, Any]]) -> None:
    replace_all_words(db, words)
