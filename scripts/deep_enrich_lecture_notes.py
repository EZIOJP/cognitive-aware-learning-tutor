#!/usr/bin/env python3
"""Upgrade lecture notes with pedagogy-first topic sections (prose → code)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.restructure_topic_pedagogy import restructure_note

NOTES_DIR = ROOT / "data" / "notes"


def main() -> None:
    total = 0
    for path in sorted(NOTES_DIR.glob("L*.md")):
        n = restructure_note(path)
        print(f"{path.name}: upgraded {n} topics")
        total += n
    print(f"done ({total} topics enriched)")


if __name__ == "__main__":
    main()
