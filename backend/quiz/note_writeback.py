from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from backend import paths
from backend.quiz.atomic_io import atomic_write_text
from backend.quiz.read_cards import make_card_id
from backend.quiz.source_stamp import bump_notes
from backend.transcripts.note_lint import sanitize_note_content
from backend.transcripts.note_topics import canonicalize_topic_id

_HEADING_RE = re.compile(r"^(#{2,4})\s+(.*)$")
_FENCE_RE = re.compile(r"^```")


def _find_section_bounds(lines: list[str], tid: str) -> tuple[int, int, int]:
    in_fence = False
    start: int | None = None
    end: int | None = None
    start_level = 2
    tid_key = tid.lower()
    for i, line in enumerate(lines):
        stripped = line.rstrip("\n")
        if _FENCE_RE.match(stripped):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = _HEADING_RE.match(stripped)
        if not m:
            continue
        level = len(m.group(1))
        heading = m.group(2)
        if start is None and tid_key in heading.lower().replace("`", ""):
            start = i
            start_level = level
            continue
        if start is not None and level <= start_level:
            end = i
            break
    if start is None:
        raise FileNotFoundError(f"section {tid}")
    if end is None:
        end = len(lines)
    return start, end, start_level


def patch_note_section(
    *,
    note_path: str,
    topic_id: str,
    body_markdown: str,
    title: str | None = None,
    expected_mtime: float | None = None,
    root: Path | None = None,
    user_id: int | None = None,
    db: Session | None = None,
) -> dict[str, Any]:
    _ = user_id, db
    base = Path(root) if root else paths.NOTES_DIR
    rel = note_path.replace("\\", "/").lstrip("/")
    path = (base / rel).resolve()
    if not path.is_relative_to(base.resolve()):
        raise ValueError("Invalid note path.")
    if not path.is_file():
        raise FileNotFoundError(rel)
    current_mtime = path.stat().st_mtime
    if expected_mtime is not None and abs(current_mtime - float(expected_mtime)) > 0.001:
        raise ValueError("mtime_conflict")
    tid = canonicalize_topic_id(topic_id) or topic_id.strip().upper()
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    start, end, _ = _find_section_bounds(lines, tid)
    heading_line = lines[start].rstrip("\n")
    hm = _HEADING_RE.match(heading_line)
    marks = hm.group(1) if hm else "##"
    new_title = (title or "").strip()
    if new_title:
        heading_line = f"{marks} `{tid}` — {new_title}"
    else:
        heading_line = lines[start].rstrip("\n")
    body = body_markdown.strip("\n")
    new_block = heading_line + "\n\n" + body + ("\n" if body else "")
    if end < len(lines) and not new_block.endswith("\n"):
        new_block += "\n"
    if end < len(lines) and not lines[end].startswith("\n") and not new_block.endswith("\n\n"):
        new_block += "\n"
    updated = "".join(lines[:start]) + new_block + "".join(lines[end:])
    if new_title:
        updated = re.sub(
            rf"(\|\s*`?{re.escape(tid)}`?\s*\|\s*)([^|]+)\|",
            rf"\1{new_title} |",
            updated,
            count=1,
            flags=re.IGNORECASE,
        )
        updated = re.sub(
            rf"([-*]\s*`?{re.escape(tid)}`?\s*(?:—|-|–|:)\s*)(.+)$",
            rf"\1{new_title}",
            updated,
            count=1,
            flags=re.IGNORECASE | re.MULTILINE,
        )
    updated = sanitize_note_content(updated)
    atomic_write_text(path, updated)
    bump_notes()
    return {
        "card_id": make_card_id(rel, tid),
        "note_path": rel,
        "tag": tid,
        "mtime": path.stat().st_mtime,
        "title": new_title or None,
    }
