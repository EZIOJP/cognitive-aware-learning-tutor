#!/usr/bin/env python3
"""Remove duplicate preamble blocks from lecture notes."""

from __future__ import annotations

import re
from pathlib import Path

NOTES_DIR = Path(__file__).resolve().parents[1] / "data" / "notes"
PREAMBLE_START = "## 📌 Topic IDs & quiz generation"


def dedupe_preamble(text: str) -> str:
    parts = text.split(PREAMBLE_START)
    if len(parts) <= 2:
        return text
    # Keep first occurrence + rest without re-adding preamble header duplicates
    first = parts[0]
    rest = PREAMBLE_START.join(parts[1:])
    # rest starts with preamble body; find end of first preamble block
    m = re.search(
        r"(?s)^.*?\n\n(?=## |\Z)",
        rest,
    )
    first_body = m.group(0).rstrip() if m else parts[1]
    remainder = rest[len(first_body) :].lstrip("\n")
    # Drop any repeated preamble headers in remainder
    remainder = re.sub(
        r"(?s)^## 📌 Topic IDs & quiz generation.*?\n\n(?=## )",
        "",
        remainder,
        count=1,
    )
    return first + PREAMBLE_START + first_body + "\n\n" + remainder


def main() -> None:
    for path in sorted(NOTES_DIR.glob("L*.md")):
        raw = path.read_text(encoding="utf-8")
        fixed = dedupe_preamble(raw)
        if fixed != raw:
            path.write_text(fixed, encoding="utf-8")
            print(f"deduped {path.name}")


if __name__ == "__main__":
    main()
