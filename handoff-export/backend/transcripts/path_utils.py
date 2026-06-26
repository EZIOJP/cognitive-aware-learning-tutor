"""Path helpers for notes — no DB/SQLAlchemy dependencies (safe for Transcript Notes Studio)."""

from __future__ import annotations

import re
from pathlib import Path


def normalize_folder_path(folder: str | None) -> str:
    if not folder or not str(folder).strip():
        return ""
    parts: list[str] = []
    for part in str(folder).replace("\\", "/").split("/"):
        part = part.strip()
        if not part or part in (".", ".."):
            continue
        if not re.match(r"^[a-zA-Z0-9._\- ]+$", part):
            raise ValueError(f"Invalid folder segment: {part}")
        parts.append(part)
    return "/".join(parts)


def normalize_filename(name: str) -> str:
    raw = name.replace("\\", "/").strip()
    if not raw or ".." in raw:
        raise ValueError("Invalid filename.")
    base = Path(raw).name
    if not base:
        raise ValueError("Invalid filename.")
    stem = Path(base).stem if base.lower().endswith(".md") else base
    safe = "".join(c if c.isalnum() or c in "-_ ." else "_" for c in stem)[:80].strip()
    if not safe:
        raise ValueError("Invalid filename.")
    return f"{safe}.md"


def build_relative_path(folder_path: str, filename: str) -> str:
    folder = normalize_folder_path(folder_path)
    fname = normalize_filename(filename)
    return f"{folder}/{fname}" if folder else fname
