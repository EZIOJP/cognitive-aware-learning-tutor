"""Offline World English Bible (structured JSON) — book/chapter/verse lookup."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from backend.bible.paths import bible_dir

_VERSION_ALIASES = {"web": "web", "worldenglishbible": "web", "worldenglish": "web"}


def structured_path(version: str = "web") -> Path:
    key = _normalize_version(version)
    return bible_dir() / "structured" / f"{key}.json"


def _normalize_version(version: str) -> str:
    raw = re.sub(r"[^a-z0-9]+", "", (version or "web").lower())
    return _VERSION_ALIASES.get(raw, raw or "web")


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (name or "").lower())


@lru_cache(maxsize=4)
def load_bible(version: str = "web") -> dict[str, Any]:
    path = structured_path(version)
    if not path.is_file():
        raise FileNotFoundError(
            f"Bible text missing at {path}. Place structured WEB JSON there."
        )
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("books"), list):
        raise ValueError(f"Invalid bible structured file: {path}")
    return data


def clear_cache() -> None:
    load_bible.cache_clear()


def list_books(version: str = "web") -> list[dict[str, Any]]:
    data = load_bible(version)
    out = []
    for b in data["books"]:
        out.append(
            {
                "id": str(b.get("id") or _slug(str(b.get("name") or ""))),
                "name": str(b["name"]),
                "testament": str(b.get("testament") or ""),
                "num_chapters": int(b.get("num_chapters") or len(b.get("chapters") or [])),
            }
        )
    return out


def _find_book(data: dict[str, Any], book: str) -> dict[str, Any] | None:
    needle = _slug(book)
    aliases = {
        "psalm": "psalms",
        "songofsongs": "songofsolomon",
        "canticles": "songofsolomon",
        "revelationofjohn": "revelation",
        "rev": "revelation",
        "gn": "genesis",
        "ex": "exodus",
        "mt": "matthew",
        "mk": "mark",
        "lk": "luke",
        "jn": "john",
    }
    needle = aliases.get(needle, needle)
    for b in data["books"]:
        bid = str(b.get("id") or _slug(str(b.get("name") or "")))
        if bid == needle or _slug(str(b.get("name") or "")) == needle:
            return b
        if _slug(str(b.get("raw_name") or "")) == needle:
            return b
    return None


def chapter_key(book: str, chapter: int) -> str:
    return f"{book}|{int(chapter)}"


def read_chapter(version: str, book: str, chapter: int) -> dict[str, Any]:
    data = load_bible(version)
    b = _find_book(data, book)
    if b is None:
        raise KeyError(f"Unknown book: {book}")
    chapters = b.get("chapters") or []
    n = len(chapters)
    ch = int(chapter)
    if ch < 1 or ch > n:
        raise IndexError(f"Chapter {ch} out of range 1..{n} for {b['name']}")
    verses_raw = chapters[ch - 1]
    verses: list[dict[str, Any]] = []
    for i, v in enumerate(verses_raw):
        if isinstance(v, dict):
            verses.append(
                {
                    "number": int(v.get("number") or i + 1),
                    "text": str(v.get("text") or "").strip(),
                }
            )
        else:
            verses.append({"number": i + 1, "text": str(v).strip()})
    return {
        "version": str(data.get("version") or _normalize_version(version)),
        "version_name": str(data.get("versionName") or ""),
        "name": str(b["name"]),
        "book_id": str(b.get("id") or _slug(str(b["name"]))),
        "testament": str(b.get("testament") or ""),
        "num_chapters": n,
        "chapter": ch,
        "verses": verses,
    }


def meta(version: str = "web") -> dict[str, Any]:
    data = load_bible(version)
    books = list_books(version)
    return {
        "version": str(data.get("version") or _normalize_version(version)),
        "version_name": str(data.get("versionName") or ""),
        "license": str(data.get("license") or ""),
        "book_count": len(books),
        "books": books,
    }


def sequential_plan(version: str = "web") -> list[dict[str, Any]]:
    """Canonical Genesis→Revelation chapter list for one-chapter-per-day assignment."""
    out: list[dict[str, Any]] = []
    for b in list_books(version):
        name = str(b["name"])
        n = max(1, int(b.get("num_chapters") or 1))
        for ch in range(1, n + 1):
            out.append({"book": name, "chapter": ch, "key": chapter_key(name, ch)})
    return out


def verses_for_chapter_keys(
    keys: list[str], *, version: str = "web", limit: int = 500
) -> list[dict[str, Any]]:
    """Expand 'Book|N' keys into verse dicts for watch rotation."""
    out: list[dict[str, Any]] = []
    for key in keys:
        if "|" not in key:
            continue
        book, _, ch_s = key.partition("|")
        try:
            ch = int(ch_s)
        except ValueError:
            continue
        try:
            chapter = read_chapter(version, book, ch)
        except (KeyError, IndexError, FileNotFoundError, ValueError):
            continue
        for v in chapter["verses"]:
            out.append(
                {
                    "ref": f"{chapter['name']} {chapter['chapter']}:{v['number']}",
                    "text": v["text"],
                    "book": chapter["name"],
                    "chapter": chapter["chapter"],
                    "verse": v["number"],
                    "source_key": chapter_key(chapter["name"], chapter["chapter"]),
                }
            )
            if len(out) >= limit:
                return out
    return out
