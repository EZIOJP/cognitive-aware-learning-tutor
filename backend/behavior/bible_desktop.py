"""Desktop-side Bible open + credit (no web backend required for reading)."""

from __future__ import annotations

import logging
import os
from pathlib import Path

log = logging.getLogger("desktop_tracker")

_BIBLE_TITLE_MARKERS = (
    "good-news-bible",
    "good news bible",
    "good-news-bible.pdf",
)


def open_bible_pdf() -> Path | None:
    """Open Good News Bible in the default PDF app. Returns path or None."""
    try:
        from backend.bible.paths import ensure_bible_pdf

        path = ensure_bible_pdf()
    except Exception as exc:  # noqa: BLE001
        log.warning("Bible PDF missing: %s", exc)
        return None
    try:
        os.startfile(str(path))  # noqa: S606 — Windows default handler
        log.info("Opened Bible PDF: %s", path)
        return path
    except OSError as exc:
        log.warning("Failed to open Bible PDF: %s", exc)
        return None


def looks_like_bible_reader(exe: str | None, title: str | None) -> bool:
    """True when a PDF reader is showing our Good News Bible file."""
    t = (title or "").lower().replace("\\", "/")
    if any(m in t for m in _BIBLE_TITLE_MARKERS):
        return True
    # Some readers only show "good-news-bible.pdf - Foxit" etc.
    if "good-news" in t and (".pdf" in t or "bible" in t):
        return True
    return False


def credit_bible_if_reading(user_id: int, exe: str, title: str, *, seconds: float = 1.0) -> None:
    """Credit Bible minutes while PDF is focused or embedded reader is open."""
    if not user_id:
        return
    try:
        from backend.behavior.tracker_bible_embed import is_embedded_bible_reading

        embedded = is_embedded_bible_reading()
    except Exception:  # noqa: BLE001
        embedded = False
    if not embedded and not looks_like_bible_reader(exe, title):
        return
    try:
        from backend.bible import store as bible_store

        bible_store.credit_reading_seconds(user_id, seconds)
    except Exception as exc:  # noqa: BLE001
        log.debug("bible credit failed: %s", exc)
