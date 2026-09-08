#!/usr/bin/env python3
"""Repair L05 after accidental full re-conversion of code/output lines."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.transcripts.note_lint import sanitize_note_content
from backend.transcripts.note_topic_structure import (
    NOTES_TOPIC_INDEX_HEADING,
    _build_topic_index_table,
    _insert_topic_index,
    strip_topic_index,
)
from backend.transcripts.note_topics import parse_note_topics

PATH = ROOT / "data" / "notes" / "L05_pandas_operations_notes.md"

REAL_TOPIC_PATTERNS = (
    r"Recap",
    r"Loading the dataset",
    r"iloc.*loc",
    r"Duplicate index labels",
    r"Unique values",
    r"Mutability",
    r"Column subsetting",
    r"Identifying.*duplicates",
    r"Aggregation functions",
    r"Sorting a DataFrame",
    r"Combining DataFrames",
    r"Merge join types",
    r"Merge with mismatched",
    r"\.apply\(\) with a custom",
    r"\.apply\(\).*lambda",
    r"Boolean trap",
    r"Building a DataFrame from scratch",
)

_LID_LINE = re.compile(r"^(#{2,6})\s+`L5-T\d+`\s*—\s*(.+)$")


def _is_real_topic(title: str) -> bool:
    return any(re.search(p, title, re.I) for p in REAL_TOPIC_PATTERNS)


def repair_l05(text: str) -> str:
    lines = text.splitlines()
    out: list[str] = []
    topic_counter = 0

    for i, line in enumerate(lines):
        if i == 1 and line.startswith("### `L5-T01`"):
            out.append(
                '### Verified line-by-line against the raw `.ipynb` + live-caption '
                'transcript + slide deck + companion "DataFrame from Scratch" notebook'
            )
            continue

        m = _LID_LINE.match(line)
        if not m:
            out.append(line)
            continue

        title = m.group(2).strip()
        if _is_real_topic(title):
            topic_counter += 1
            out.append(f"## `L5-T{topic_counter:02d}` — {title}")
        else:
            # Code output / inline comment — demote to plain text
            out.append(title)

    result = "\n".join(out)
    result = strip_topic_index(result)
    topics = parse_note_topics(result, min_body_chars=20)
    table = _build_topic_index_table(topics, 5)
    result = _insert_topic_index(result, table)

    reserved = (
        "\n**Reserved, not yet covered:** `groupby` was on today's agenda slide but "
        "the lecture ran out of time before reaching it — see §Open Items. No ID has "
        "been minted for it yet; mint `L5-T18` (or the next free ID in whichever lecture "
        "actually covers it) when it's taught, rather than reusing a gap here.\n"
    )
    if "Reserved, not yet covered" not in result:
        anchor = NOTES_TOPIC_INDEX_HEADING
        if anchor in result:
            idx = result.index(anchor)
            end = result.find("\n\n## ", idx)
            if end > 0:
                result = result[:end] + "\n\n---\n" + reserved + result[end:]

    return sanitize_note_content(result)


def main() -> None:
    raw = PATH.read_text(encoding="utf-8")
    fixed = repair_l05(raw)
    PATH.write_text(fixed, encoding="utf-8")
    topics = parse_note_topics(fixed, min_body_chars=20)
    print(f"topics={len(topics)} ids={[t.topic_id for t in topics]}")


if __name__ == "__main__":
    main()
