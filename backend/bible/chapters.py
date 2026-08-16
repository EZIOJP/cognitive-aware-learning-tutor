"""Detect Bible book/chapter page ranges from Good News PDF headers."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from backend.bible.paths import bible_dir, ensure_bible_pdf

log = logging.getLogger("desktop_tracker")

# Common GNB book names as they appear in running headers
_BOOKS = (
    "Genesis",
    "Exodus",
    "Leviticus",
    "Numbers",
    "Deuteronomy",
    "Joshua",
    "Judges",
    "Ruth",
    "1 Samuel",
    "2 Samuel",
    "1 Kings",
    "2 Kings",
    "1 Chronicles",
    "2 Chronicles",
    "Ezra",
    "Nehemiah",
    "Esther",
    "Job",
    "Psalms",
    "Psalm",
    "Proverbs",
    "Ecclesiastes",
    "Song of Songs",
    "Isaiah",
    "Jeremiah",
    "Lamentations",
    "Ezekiel",
    "Daniel",
    "Hosea",
    "Joel",
    "Amos",
    "Obadiah",
    "Jonah",
    "Micah",
    "Nahum",
    "Habakkuk",
    "Zephaniah",
    "Haggai",
    "Zechariah",
    "Malachi",
    "Matthew",
    "Mark",
    "Luke",
    "John",
    "Acts",
    "Romans",
    "1 Corinthians",
    "2 Corinthians",
    "Galatians",
    "Ephesians",
    "Philippians",
    "Colossians",
    "1 Thessalonians",
    "2 Thessalonians",
    "1 Timothy",
    "2 Timothy",
    "Titus",
    "Philemon",
    "Hebrews",
    "James",
    "1 Peter",
    "2 Peter",
    "1 John",
    "2 John",
    "3 John",
    "Jude",
    "Revelation",
)

# Longer names first so "1 Samuel" matches before "Samuel"
_BOOK_ALT = sorted(_BOOKS, key=len, reverse=True)
_HEADER_RE = re.compile(
    r"^(" + "|".join(re.escape(b) for b in _BOOK_ALT) + r")(?:\s+(\d+)\.)?",
    re.IGNORECASE,
)

_CACHE_NAME = "chapter_index.json"


@dataclass(frozen=True)
class ChapterSpan:
    book: str
    chapter: int
    start_page: int  # 1-based inclusive
    end_page: int  # 1-based inclusive (page before next chapter)


def _cache_path() -> Path:
    return bible_dir() / _CACHE_NAME


def _normalize_book(name: str) -> str:
    n = name.strip()
    if n.lower() == "psalm":
        return "Psalms"
    for b in _BOOKS:
        if b.lower() == n.lower():
            return "Psalms" if b == "Psalm" else b
    return n.title()


def _first_line(page_text: str) -> str:
    for line in page_text.splitlines():
        s = line.strip()
        if s:
            return s
    return ""


def scan_chapters(pdf_path: Path | None = None) -> list[ChapterSpan]:
    """Walk PDF headers; chapter ends at the page before the next chapter heading."""
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError("PyMuPDF required") from exc

    path = pdf_path or ensure_bible_pdf()
    doc = fitz.open(str(path))
    total_pages = len(doc)
    # First sighting of each (book, chapter) → start page
    first_seen: list[tuple[str, int, int]] = []
    prev_key: tuple[str, int] | None = None
    try:
        for i in range(total_pages):
            first = _first_line(doc.load_page(i).get_text("text"))
            m = _HEADER_RE.match(first)
            if not m:
                continue
            book = _normalize_book(m.group(1))
            chap_s = m.group(2)
            if chap_s is None:
                # Title page like "Genesis" / "Matthew" → chapter 1 starts here
                chap = 1
            else:
                chap = int(chap_s)
            key = (book, chap)
            if key == prev_key:
                continue
            # Only record first time we see this chapter
            if any(b == book and c == chap for b, c, _ in first_seen):
                prev_key = key
                continue
            first_seen.append((book, chap, i + 1))
            prev_key = key
    finally:
        doc.close()

    spans: list[ChapterSpan] = []
    for idx, (book, chap, start) in enumerate(first_seen):
        if idx + 1 < len(first_seen):
            end = first_seen[idx + 1][2] - 1
        else:
            end = total_pages
        if end < start:
            end = start
        spans.append(ChapterSpan(book=book, chapter=chap, start_page=start, end_page=end))
    return spans


def load_or_build_chapters(*, force: bool = False) -> list[dict[str, Any]]:
    """Cached chapter index (JSON). Rebuild if missing or force."""
    cache = _cache_path()
    if cache.is_file() and not force:
        try:
            raw = json.loads(cache.read_text(encoding="utf-8"))
            if isinstance(raw, list) and raw:
                return raw
        except (OSError, json.JSONDecodeError):
            pass
    spans = scan_chapters()
    data = [asdict(s) for s in spans]
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(data, indent=2), encoding="utf-8")
    log.info("Bible chapter index built: %s chapters → %s", len(data), cache)
    return data


def chapter_at_page(chapters: list[dict[str, Any]], page: int) -> dict[str, Any] | None:
    page = max(1, int(page))
    for ch in chapters:
        if int(ch["start_page"]) <= page <= int(ch["end_page"]):
            return ch
    return None


def chapters_completed_through(chapters: list[dict[str, Any]], page: int) -> set[str]:
    """Chapter keys completed when reader has reached the next chapter (or finished)."""
    page = max(1, int(page))
    done: set[str] = set()
    for ch in chapters:
        # Complete once you've reached the first page of the *next* span, i.e. page > end_page
        # or you're past this chapter's end.
        key = f"{ch['book']}|{ch['chapter']}"
        if page > int(ch["end_page"]):
            done.add(key)
    return done
