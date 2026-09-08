#!/usr/bin/env python3
"""Refine all lecture notes for search, flashcards, and quiz topic tags.

- Promote ### L-ID headings to ## (consistent top-level topics)
- Strip L-IDs from empty parent sections (overview headers only)
- Fix truncated titles (e.g. "D Arrays" → "2D Arrays")
- Rebuild Topic Index with prose scopes (not raw code)
- Dedupe preambles, lint fences, sync library DB
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.db.session import SessionLocal
from backend.transcripts.library import sync_disk_notes_for_user
from backend.transcripts.note_lint import sanitize_note_content
from backend.transcripts.note_topic_structure import (
    infer_lecture_number,
    rebuild_topic_index,
    strip_topic_index,
)
from backend.transcripts.note_topics import parse_note_topics, parse_topic_index

NOTES_DIR = ROOT / "data" / "notes"

_LID_H3 = re.compile(
    r"^###\s+`?(L\d+-T\d+)`?\s*(?:—|-|–|:)\s*(.+)$",
    re.IGNORECASE,
)
_LID_H2 = re.compile(
    r"^(##)\s+`?(L\d+-T\d+)`?\s*(?:—|-|–|:)\s*(.+)$",
    re.IGNORECASE,
)
_TITLE_FIXES = (
    (re.compile(r"— D Arrays\b"), "— 2D Arrays"),
    (re.compile(r"— D array\b", re.I), "— 2D array"),
)

_PREAMBLE = re.compile(r"^## 📌 Topic IDs", re.MULTILINE)
_NUMBERING_NOTE = re.compile(
    r"^## 📌 A note on the numbering in this file\s*\n[\s\S]*?(?=\n## |\Z)",
    re.MULTILINE,
)


def _strip_topic_ids_preamble(text: str) -> str:
    """Remove reader-facing quiz-gen preamble (rules live in data/notes/rules/)."""
    out = _NUMBERING_NOTE.sub("\n", text)
    lines = out.splitlines()
    result: list[str] = []
    i = 0
    while i < len(lines):
        if lines[i].strip() == "## 📌 Topic IDs & quiz generation":
            i += 1
            while i < len(lines) and not (
                lines[i].startswith("## ") or lines[i].startswith("### ")
            ):
                i += 1
            continue
        result.append(lines[i])
        i += 1
    return re.sub(r"\n{3,}", "\n\n", "\n".join(result)).strip() + "\n"


def _dedupe_preamble(text: str) -> str:
    parts = text.split("## 📌 Topic IDs & quiz generation")
    if len(parts) <= 2:
        return text
    first = parts[0]
    rest = "## 📌 Topic IDs & quiz generation".join(parts[1:])
    m = re.match(r"(?s)(.*?\n\n)(?=## )", rest)
    first_block = m.group(0) if m else parts[1]
    remainder = rest[len(first_block) :] if m else ""
    remainder = re.sub(
        r"(?s)^## 📌 Topic IDs & quiz generation.*?\n\n(?=## )",
        "",
        remainder,
        count=10,
    )
    return first + "## 📌 Topic IDs & quiz generation" + first_block + remainder


def _promote_lid_headings(text: str) -> str:
    out: list[str] = []
    for line in text.splitlines():
        m = _LID_H3.match(line)
        if m:
            out.append(f"## `{m.group(1).upper()}` — {m.group(2).strip()}")
        else:
            out.append(line)
    return "\n".join(out)


def _fix_titles(text: str) -> str:
    for pat, repl in _TITLE_FIXES:
        text = pat.sub(repl, text)
    return text


def refine_note(path: Path, *, sync: bool = False) -> dict:
    raw = path.read_text(encoding="utf-8")
    lec = infer_lecture_number(path.name) or 1
    step = _dedupe_preamble(raw)
    step = _strip_topic_ids_preamble(step)
    step = _promote_lid_headings(step)
    step = _fix_titles(step)
    step = rebuild_topic_index(step, lecture_num=lec, note_path=path.name)
    step = sanitize_note_content(step)
    changed = step != raw
    if changed:
        path.write_text(step, encoding="utf-8")
    topics = parse_note_topics(step, min_body_chars=20)
    index = parse_topic_index(step)
    return {
        "file": path.name,
        "lecture": lec,
        "topics": len(topics),
        "index_rows": len(index),
        "changed": changed,
    }


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Refine lecture notes for search/quiz indexing")
    parser.add_argument(
        "--force-rebuild",
        action="store_true",
        help="Strip all L-IDs and re-assign from headings (destructive; use only if structure is broken)",
    )
    args = parser.parse_args()
    if args.force_rebuild:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "format_notes",
            ROOT / "scripts" / "format_notes_to_standards.py",
        )
        mod = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(mod)
        results = [mod.format_note(p, force=True) for p in sorted(NOTES_DIR.glob("L*.md"))]
    else:
        results = [refine_note(p) for p in sorted(NOTES_DIR.glob("L*.md"))]
    for r in results:
        flag = "updated" if r["changed"] else "ok"
        print(
            f"{r['file']}: {flag} | L{r['lecture']} | "
            f"{r['index_rows']} index | {r['topics']} topics"
        )
    with SessionLocal() as db:
        n = sync_disk_notes_for_user(db, user_id=1)
        db.commit()
        print(f"synced {n} library row(s)")


if __name__ == "__main__":
    main()
