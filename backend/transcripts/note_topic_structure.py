"""Ensure lecture notes have L{n}-Txx topic structure for per-topic quiz generation."""

from __future__ import annotations

import re

from backend.transcripts.note_topics import (
    _is_meta_heading,
    parse_note_topics,
    parse_topic_index,
)

NOTES_TOPIC_INDEX_HEADING = "## 🗂️ Topic Index (quiz-gen lookup table)"

_LID_HEADING = re.compile(
    r"^(#{2,4})\s+`?(L\d+-T\d+)`?\s*(?:—|-|–|:)\s*(.+)$",
    re.IGNORECASE,
)
_DECIMAL_HEADING = re.compile(
    r"^(#{2,4})\s+(\d+(?:\.\d+)*)\s*[.:—\-–]?\s*(.+)$",
)
_GENERIC_H2 = re.compile(r"^(#{2,4})\s+(.+)$")
_PREAMBLE_LID = re.compile(
    r"^(#{2,4})\s+`?L\d+-T\d+`?\s*—\s*📌\s+Topic IDs",
    re.IGNORECASE,
)


def infer_lecture_number(path_or_title: str) -> int | None:
    """Best-effort lecture number from path or title (e.g. lecture_5 → 5)."""
    text = (path_or_title or "").replace("\\", "/")
    for pat in (
        r"^L(\d+)[-_/]",
        r"lecture[_\s-]?(\d+)",
        r"/l(\d+)[-_/]",
        r"\bL(\d+)-T",
    ):
        m = re.search(pat, text, re.I)
        if m:
            try:
                return int(m.group(1))
            except ValueError:
                continue
    return None


def _has_lid_topics(material: str) -> bool:
    topics = parse_note_topics(material, min_body_chars=20)
    return bool(topics) and any(t.source == "lid" for t in topics)


def _topic_scope_line(body: str, title: str) -> str:
    """One-line scope for Topic Index — prose summary, not raw code."""
    text = re.sub(r"```[\s\S]*?```", " ", body or "")
    text = re.sub(r"`[^`]+`", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    for line in (body or "").splitlines():
        raw = line.strip()
        if not raw or raw.startswith("|") or raw.startswith("#"):
            continue
        if raw.startswith(">"):
            raw = raw.lstrip("> ").strip()
        if raw.lower().startswith("**description:**"):
            return raw.split(":", 1)[-1].strip()[:80]
        if len(raw) >= 24 and not raw.startswith("```"):
            return raw[:80]
    if text:
        return text[:80]
    return (title or "Topic section")[:80]


def _build_topic_index_table(topics: list, lecture_num: int) -> str:
    rows = ["| ID | Topic | One-line scope |", "|---|---|---|"]
    for t in topics:
        scope = _topic_scope_line(t.body or "", t.title)
        rows.append(f"| `{t.topic_id}` | {t.title[:60]} | {scope} |")
    return f"{NOTES_TOPIC_INDEX_HEADING}\n\n" + "\n".join(rows) + "\n\n"


def rebuild_topic_index(
    markdown: str,
    *,
    lecture_num: int | None = None,
    note_path: str = "",
    min_body_chars: int = 20,
) -> str:
    """Replace Topic Index table with fresh rows from parsed L-ID sections."""
    text = strip_topic_index(markdown or "")
    n = lecture_num or infer_lecture_number(note_path) or infer_lecture_number(text[:200]) or 1
    topics = parse_note_topics(text, min_body_chars=min_body_chars)
    if not topics:
        return markdown
    table = _build_topic_index_table(topics, n)
    return _insert_topic_index(text, table)


def _index_insert_line_index(lines: list[str]) -> int:
    """Line index after which to insert Topic Index (after title/preamble block)."""
    h1 = next((i for i, ln in enumerate(lines) if re.match(r"^#\s+\S", ln)), -1)
    if h1 < 0:
        return 0
    for i in range(h1 + 1, len(lines)):
        if lines[i].strip() == "---":
            return i + 1
    for i, ln in enumerate(lines):
        if "note on the numbering" in ln.lower():
            j = i + 1
            while j < len(lines) and not re.match(r"^##\s+", lines[j]):
                j += 1
            return j
    for i, ln in enumerate(lines):
        if re.match(r"^##\s+📌\s+Topic IDs", ln):
            j = i + 1
            while j < len(lines) and not re.match(r"^##\s+", lines[j]):
                j += 1
            return j
    return h1 + 1


def _insert_topic_index(text: str, table: str) -> str:
    if parse_topic_index(text):
        return text
    lines = text.splitlines()
    at = _index_insert_line_index(lines)
    block = ["", table.rstrip(), ""]
    return "\n".join(lines[:at] + block + lines[at:])


def strip_lid_headings(markdown: str) -> str:
    """Remove L{n}-Txx prefixes so headings can be re-assigned cleanly."""
    out: list[str] = []
    for line in (markdown or "").splitlines():
        m = _LID_HEADING.match(line)
        if m:
            out.append(f"{m.group(1)} {m.group(3).strip()}")
        else:
            out.append(line)
    return "\n".join(out).strip() + "\n"


def strip_topic_index(markdown: str) -> str:
    """Remove Topic Index table so structure can be rebuilt."""
    lines = (markdown or "").splitlines()
    out: list[str] = []
    i = 0
    while i < len(lines):
        if NOTES_TOPIC_INDEX_HEADING.split("(")[0].strip() in lines[i]:
            i += 1
            while i < len(lines) and (
                not lines[i].strip()
                or lines[i].startswith("|")
                or lines[i].strip() == "---"
            ):
                i += 1
            continue
        out.append(lines[i])
        i += 1
    return "\n".join(out).strip() + "\n"


def ensure_quiz_topic_structure(
    markdown: str,
    *,
    lecture_num: int | None = None,
    note_path: str = "",
) -> str:
    """Add or repair Topic Index + L{n}-Txx headings when missing.

    Idempotent when the note already uses canonical L-IDs.
    """
    text = (markdown or "").strip()
    if not text:
        return text

    n = lecture_num or infer_lecture_number(note_path) or infer_lecture_number(text[:200]) or 1

    if _has_lid_topics(text):
        index = parse_topic_index(text)
        topics = parse_note_topics(text, min_body_chars=20)
        if index or not topics:
            return text
        table = _build_topic_index_table(topics, n)
        return _insert_topic_index(text, table)

    lines = text.splitlines()
    out: list[str] = []
    topic_counter = 0

    i = 0
    while i < len(lines):
        line = lines[i]
        if _PREAMBLE_LID.match(line):
            i += 1
            continue

        m_lid = _LID_HEADING.match(line)
        if m_lid:
            out.append(line)
            i += 1
            continue

        m_dec = _DECIMAL_HEADING.match(line)
        m_gen = _GENERIC_H2.match(line) if not m_dec else None
        m = m_dec or m_gen
        if m:
            hashes, raw_title = m.group(1), (m.group(3) if m_dec else m.group(2)).strip()
            if _is_meta_heading(raw_title):
                out.append(line)
                i += 1
                continue
            topic_counter += 1
            tid = f"L{n}-T{topic_counter:02d}"
            title = raw_title[:120]
            out.append(f"{hashes} `{tid}` — {title}")
            i += 1
            continue

        out.append(line)
        i += 1

    if topic_counter == 0:
        return text

    result = "\n".join(out)
    topics = parse_note_topics(result, min_body_chars=20)
    if not topics:
        return result

    if parse_topic_index(result):
        return result

    table = _build_topic_index_table(topics, n)
    return _insert_topic_index(result, table)
