"""Canonical lecture-note topic parsing for quiz generation.

Primary: ``L{n}-Txx`` IDs (Topic Index + ``## `L5-T05` — title`` headings).
Fallback: decimal outline headings (``## 2`` / ``### 2.1``).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

# Meta H2s that must never become quiz topics
_META_HEADING_RE = re.compile(
    r"(?i)^(topic\s*index|new\s+functions|quick\s+lookup|quick\s+reference|"
    r"cheat[\s\-]?sheet|open\s+items|source\s+verification|additional\s+doubt|"
    r"recap\s*&\s*today|today'?s\s+agenda|functions\s*&\s*methods)"
)

_LID_IN_HEADING = re.compile(
    r"`?(L\d+-T\d+)`?\s*(?:—|-|–|:)\s*(.+)$",
    re.IGNORECASE,
)
_LID_ONLY = re.compile(r"`?(L\d+-T\d+)`?", re.IGNORECASE)
_DECIMAL_HEADING = re.compile(
    r"^(\d+(?:\.\d+)*)\s*[.:—\-–]?\s*(.+)$",
)
_INDEX_ROW = re.compile(
    r"\|\s*`?(L\d+-T\d+)`?\s*\|\s*([^|]+)\|",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class NoteTopic:
    topic_id: str
    title: str
    body: str
    source: str  # "lid" | "decimal" | "heading"

    def as_dict(self) -> dict[str, Any]:
        return {
            "topic_id": self.topic_id,
            "title": self.title,
            "char_count": len(self.body),
            "source": self.source,
            "label": f"{self.topic_id} — {self.title}" if self.topic_id else self.title,
        }


def remap_legacy_note_path(relative_path: str) -> str:
    """Map pre-data_foundations paths onto the new tree (string-only)."""
    rel = (relative_path or "").replace("\\", "/").lstrip("/")
    if not rel or rel.startswith("data_foundations/"):
        return rel
    aliases = (
        ("lecture5/", "data_foundations/lecture_5/"),
        ("lecture_5/", "data_foundations/lecture_5/"),
        ("lecture_4/", "data_foundations/lecture_4/"),
        ("lecture_3/", "data_foundations/lecture_3/"),
        ("lecture_2/", "data_foundations/lecture_2/"),
    )
    for old, new in aliases:
        if rel.startswith(old):
            return new + rel[len(old) :]
    return rel


def canonical_library_path(relative_path: str) -> str:
    """Return remapped path when that file exists on disk; otherwise keep input."""
    from backend.paths import NOTES_DIR

    rel = (relative_path or "").replace("\\", "/").lstrip("/")
    remapped = remap_legacy_note_path(rel)
    if remapped != rel and (NOTES_DIR / remapped).is_file():
        return remapped
    return rel


def _is_meta_heading(heading: str) -> bool:
    clean = re.sub(r"^#+\s*", "", heading or "").strip()
    clean = re.sub(r"[^\w\s&\-]", " ", clean)
    clean = re.sub(r"\s+", " ", clean).strip()
    return bool(_META_HEADING_RE.search(clean))


def _parse_heading_identity(heading: str) -> tuple[str, str, str] | None:
    """Return (topic_id, title, source) or None if not a content topic."""
    raw = re.sub(r"^#+\s*", "", heading or "").strip()
    if not raw or _is_meta_heading(raw):
        return None

    m = _LID_IN_HEADING.match(raw)
    if m:
        return m.group(1).upper(), m.group(2).strip()[:120], "lid"

    m = _LID_ONLY.search(raw)
    if m and raw.upper().startswith(m.group(1).upper()):
        rest = raw[m.end() :].lstrip(" —–-:").strip() or m.group(1).upper()
        return m.group(1).upper(), rest[:120], "lid"

    m = _DECIMAL_HEADING.match(raw)
    if m:
        num, title = m.group(1), m.group(2).strip()
        if title and not title.lower().startswith("recap"):
            return num, title[:120], "decimal"
        if title:
            return num, title[:120], "decimal"

    # Generic ## heading (non-meta) — use slug as id for cover_all
    if len(raw) >= 3:
        slug = re.sub(r"[^a-zA-Z0-9]+", "-", raw.lower()).strip("-")[:40]
        return slug or "section", raw[:120], "heading"
    return None


def _split_markdown_sections(material: str) -> list[tuple[str, str]]:
    text = (material or "").strip()
    if not text:
        return []
    parts = re.split(r"(?m)^(#{2,4}\s+.+)$", text)
    if len(parts) == 1:
        return [("Full notes", text)]
    out: list[tuple[str, str]] = []
    i = 1
    while i + 1 < len(parts):
        heading = parts[i].strip()
        body = (parts[i + 1] or "").strip()
        i += 2
        out.append((heading, body))
    return out


def parse_topic_index(material: str) -> dict[str, str]:
    """Map L-IDs → one-line titles from the Topic Index table when present."""
    found: dict[str, str] = {}
    for m in _INDEX_ROW.finditer(material or ""):
        tid = m.group(1).upper()
        title = m.group(2).strip()
        if tid and title and tid not in found:
            found[tid] = title[:120]
    return found


def parse_note_topics(
    material: str,
    *,
    topic_ids: list[str] | None = None,
    max_topics: int = 40,
    min_body_chars: int = 40,
    max_body_chars: int = 5500,
) -> list[NoteTopic]:
    """Extract quiz-ready topics from a lecture note.

    Prefers ``L{n}-Txx`` sections. If none exist, falls back to decimal / generic H2+.
    """
    index_titles = parse_topic_index(material)
    sections = _split_markdown_sections(material)
    want = {t.strip().upper() for t in (topic_ids or []) if t and t.strip()}

    lid_topics: list[NoteTopic] = []
    fallback: list[NoteTopic] = []

    for heading, body in sections:
        if len(body) < min_body_chars:
            continue
        ident = _parse_heading_identity(heading)
        if not ident:
            continue
        tid, title, source = ident
        if source == "lid" and tid in index_titles and (
            not title or title.upper() == tid
        ):
            title = index_titles[tid]
        topic = NoteTopic(
            topic_id=tid,
            title=title,
            body=body[:max_body_chars],
            source=source,
        )
        if source == "lid":
            lid_topics.append(topic)
        else:
            fallback.append(topic)

    topics = lid_topics if lid_topics else fallback
    if want:
        topics = [
            t
            for t in topics
            if t.topic_id.upper() in want or t.topic_id in want
        ]
    return topics[:max_topics]


def topics_as_sections(topics: list[NoteTopic]) -> list[tuple[str, str]]:
    """Compatibility shape for cover_all: (section_title, body)."""
    return [(t.as_dict()["label"], t.body) for t in topics]
