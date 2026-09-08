#!/usr/bin/env python3
"""Restructure topic bodies: prose intro → details → code last."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.transcripts.note_topics import parse_note_topics
from scripts.topic_deep_enrichments import format_pedagogy_intro, pedagogy_for

NOTES_DIR = ROOT / "data" / "notes"

TOPIC_HEADING_RE = re.compile(
    r"^(## `?(L\d+-T\d+)`?\s*(?:—|-|–|:)\s*(.+))$",
    re.MULTILINE | re.IGNORECASE,
)
FENCE_RE = re.compile(r"```[\w]*[^\n]*\n[\s\S]*?```", re.MULTILINE)
CONTEXT_BLOCK_RE = re.compile(
    r"\n*(?:> \*\*Context:\*\*[^\n]*(?:\n>(?!##)[^\n]*)*)+",
    re.MULTILINE,
)
REMEMBER_BLOCK_RE = re.compile(
    r"\n*(?:> \*\*Remember:\*\*[^\n]*(?:\n>(?!##)[^\n]*)*)+",
    re.MULTILINE,
)
STRUCTURED_LINE_RE = re.compile(
    r"^\*\*(What it is|Key rule|Syntax|When to use it):\*\*[^\n]*\n?",
    re.MULTILINE | re.IGNORECASE,
)
TAKEAWAY_RE = re.compile(r"(\n\*\*Takeaway:\*\*[^\n]*)", re.IGNORECASE)
PEDAGOGY_PRESENT_RE = re.compile(r"\*\*What it is:\*\*", re.IGNORECASE)


def _normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def _is_redundant(prose: str, intro: str) -> bool:
    p = _normalize_ws(prose)
    if len(p) < 20:
        return True
    i = _normalize_ws(intro)
    if p in i or i in p:
        return True
    # First 60 chars overlap heavily
    if len(p) >= 40 and p[:60] in i:
        return True
    return False


def _strip_syntax_duplicates(prose: str) -> str:
    """Drop legacy one-line 'Syntax: ...' if we emit structured Syntax."""
    return re.sub(
        r"^Syntax:\s*`?array\[start:end\]`.*\n?",
        "",
        prose,
        flags=re.MULTILINE | re.IGNORECASE,
    )


def _extract_takeaway(body: str) -> tuple[str, str | None]:
    m = TAKEAWAY_RE.search(body)
    if not m:
        return body, None
    return body[: m.start()] + body[m.end() :], m.group(1).strip()


def _split_prose_and_fences(body: str) -> tuple[list[str], list[str]]:
    """Return prose chunks and code fences in document order."""
    prose_chunks: list[str] = []
    fences: list[str] = []
    pos = 0
    for m in FENCE_RE.finditer(body):
        before = body[pos : m.start()].strip()
        if before:
            prose_chunks.append(before)
        fences.append(m.group(0).strip())
        pos = m.end()
    tail = body[pos:].strip()
    if tail:
        prose_chunks.append(tail)
    return prose_chunks, fences


def _clean_prose_chunk(chunk: str) -> str:
    chunk = CONTEXT_BLOCK_RE.sub("", chunk)
    chunk = REMEMBER_BLOCK_RE.sub("", chunk)
    chunk = STRUCTURED_LINE_RE.sub("", chunk)
    chunk = _strip_syntax_duplicates(chunk)
    # Collapse excessive blank lines
    chunk = re.sub(r"\n{3,}", "\n\n", chunk).strip()
    return chunk


def restructure_body(body: str, topic_id: str, title: str) -> tuple[str, bool]:
    body, takeaway = _extract_takeaway(body)
    intro = format_pedagogy_intro(pedagogy_for(topic_id, title))

    prose_chunks, fences = _split_prose_and_fences(body)
    extra: list[str] = []
    for chunk in prose_chunks:
        cleaned = _clean_prose_chunk(chunk)
        if not cleaned:
            continue
        if _is_redundant(cleaned, intro):
            continue
        extra.append(cleaned)

    parts: list[str] = [intro.rstrip()]
    if extra:
        parts.append("\n\n".join(extra))
    if fences:
        parts.append("\n\n".join(fences))
    if takeaway:
        parts.append(takeaway)

    new_body = "\n\n" + "\n\n".join(p for p in parts if p) + "\n\n"
    changed = new_body.strip() != body.strip()
    return new_body, changed


def restructure_note(path: Path) -> int:
    raw = path.read_text(encoding="utf-8")
    topics = {t.topic_id.upper(): t for t in parse_note_topics(raw, min_body_chars=20)}
    matches = list(TOPIC_HEADING_RE.finditer(raw))
    if not matches:
        return 0

    out = raw
    count = 0
    for i in range(len(matches) - 1, -1, -1):
        m = matches[i]
        tid_m = re.search(r"(L\d+-T\d+)", m.group(1), re.I)
        if not tid_m:
            continue
        tid = tid_m.group(1).upper()
        topic = topics.get(tid)
        title = topic.title if topic else m.group(2).strip()

        body_start = m.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(out)
        body = out[body_start:body_end]
        new_body, _ = restructure_body(body, tid, title)
        if new_body.strip() != body.strip():
            out = out[:body_start] + new_body + out[body_end:]
            count += 1

    out = re.sub(r"\n{4,}", "\n\n\n", out)
    path.write_text(out, encoding="utf-8")
    return count


def main() -> None:
    total = 0
    for path in sorted(NOTES_DIR.glob("L*.md")):
        n = restructure_note(path)
        print(f"{path.name}: restructured {n} topics")
        total += n
    print(f"done ({total} topics restructured)")


if __name__ == "__main__":
    main()
