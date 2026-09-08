#!/usr/bin/env python3
"""Place New Functions / Quick Lookup block immediately after Topic Index."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NOTES_DIR = ROOT / "data" / "notes"

NEW_FN_HEADING_RE = re.compile(
    r"^##\s+.*new functions.*quick lookup.*$",
    re.IGNORECASE | re.MULTILINE,
)
TOPIC_INDEX_HEADING = "## 🗂️ Topic Index (quiz-gen lookup table)"
TOPIC_H2_RE = re.compile(r"^## `?(L\d+-T\d+)`?\s*[—–-]", re.MULTILINE)


def _find_index_insert_line(lines: list[str]) -> int:
    """Line index to insert after (end of topic index table)."""
    start = next((i for i, ln in enumerate(lines) if TOPIC_INDEX_HEADING in ln), None)
    if start is None:
        raise ValueError("Topic Index not found")
    i = start + 1
    while i < len(lines):
        stripped = lines[i].strip()
        if stripped.startswith("|"):
            i += 1
            continue
        if stripped == "":
            i += 1
            continue
        break
    return i


def _extract_new_functions_block(text: str) -> tuple[str, str]:
    m = NEW_FN_HEADING_RE.search(text)
    if not m:
        return text, ""

    start = m.start()
    rest = text[m.end() :]
    end_match = TOPIC_H2_RE.search(rest)
    if end_match:
        end = m.end() + end_match.start()
    else:
        # Through trailing --- before next major section or EOF
        end = len(text)

    block = text[start:end].strip()
    block = re.sub(
        r"\n---\n\n##\s+(?:\d+\.\s*)?(?:Open Items|Source Verification)[\s\S]*$",
        "",
        block,
        flags=re.IGNORECASE,
    ).strip()
    remainder = (text[:start] + text[end:]).strip()
    remainder = re.sub(r"\n{3,}", "\n\n", remainder) + "\n"
    return remainder, block + "\n\n"


def reorder_note(path: Path) -> bool:
    raw = path.read_text(encoding="utf-8")
    without_block, block = _extract_new_functions_block(raw)
    if not block.strip():
        return False

    lines = without_block.splitlines()
    insert_at = _find_index_insert_line(lines)

    # Already directly after index?
    tail = "\n".join(lines[insert_at : insert_at + 6])
    if NEW_FN_HEADING_RE.search(tail):
        return False

    new_lines = lines[:insert_at] + ["", block.rstrip(), ""] + lines[insert_at:]
    out = re.sub(r"\n{3,}", "\n\n", "\n".join(new_lines)).strip() + "\n"
    # Normalize heading (drop legacy "17." prefixes)
    out = re.sub(
        r"^##\s+\d+\.\s*(🆕\s*New Functions)",
        r"## \1",
        out,
        flags=re.MULTILINE,
    )
    path.write_text(out, encoding="utf-8")
    return True


def main() -> None:
    changed = 0
    for path in sorted(NOTES_DIR.glob("L*.md")):
        if reorder_note(path):
            print(f"reordered: {path.name}")
            changed += 1
        else:
            print(f"ok/skip: {path.name}")
    print(f"done ({changed} updated)")


if __name__ == "__main__":
    main()
