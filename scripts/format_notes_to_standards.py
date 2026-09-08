#!/usr/bin/env python3
"""Format library lecture notes to L{n}-Txx standards + context preambles."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.transcripts.note_lint import sanitize_note_content
from backend.transcripts.note_topic_structure import (
    ensure_quiz_topic_structure,
    infer_lecture_number,
    rebuild_topic_index,
    strip_lid_headings,
    strip_topic_index,
)
from backend.transcripts.note_topics import parse_note_topics, parse_topic_index

NOTES_DIR = ROOT / "data" / "notes"

PREAMBLE = """## 📌 Topic IDs & quiz generation

Topics use **flat, continuous IDs** (`L{n}-T01`, `L{n}-T02`, …) — one ID per concept, not per document position. The **Topic Index** below is what quiz-gen should read first; pull only the matching section body when writing questions.

{context}

> Meta sections (Quick Lookup, Recap, Open Items) are for study — **do not** generate quiz items from them.
"""

CONTEXT: dict[int, str] = {
    2: (
        "**Context:** Lecture 2 — NumPy indexing, slicing, fancy indexing, reshape, transpose, aggregates. "
        "Builds on the EDA / pandas→NumPy pipeline from the opening lectures. "
        "**Continues in:** `L03_numpy_lecture3_notes.md` (aggregates, sorting, matrix multiply, vectorization intro)."
    ),
    3: (
        "**Context:** Lecture 3 — aggregate functions, sorting, matrix multiplication, vectorization, broadcasting intro. "
        "**Prior:** `L02_numpy_operations_notes.md` (indexing & reshape). "
        "**Continues in:** `L04_vectorization_stacking_pandas_notes.md` (vectorization deep dive, stacking, pandas intro)."
    ),
    4: (
        "**Context:** Lecture 4 — vectorization, vstack/hstack/concatenate, pandas Series/DataFrame intro, `iloc`/`loc` basics. "
        "**Prior:** `L03_numpy_lecture3_notes.md`. "
        "**Continues in:** `L05_pandas_operations_notes.md` (`L5-T03`+ extends `iloc`/`loc`, duplicates, merge, apply)."
    ),
    5: (
        "**Context:** Lecture 5 — pandas operations (unique values, duplicates, agg, sort, concat/merge, apply). "
        "**Prior:** `L04_vectorization_stacking_pandas_notes.md` for pandas/NumPy bridge. "
        "`groupby` was on the agenda but deferred — mint the next free `L5-Txx` when taught."
    ),
}

_TOPIC_ID_NOTE = re.compile(r"^## 📌 Topic IDs", re.MULTILINE)


def _inject_preamble(text: str, lecture_num: int) -> str:
    """Preamble removed from reader-facing notes; rules live in data/notes/rules/."""
    return text


def _already_standard(text: str) -> bool:
    topics = parse_note_topics(text, min_body_chars=20)
    index = parse_topic_index(text)
    if not topics or not index:
        return False
    lids = sum(1 for t in topics if t.source == "lid")
    return lids >= len(topics) * 0.8 and len(index) >= min(10, len(topics) // 2)


def format_note(path: Path, *, force: bool = False) -> dict:
    raw = path.read_text(encoding="utf-8")
    lec = infer_lecture_number(path.name) or 1
    if not force and _already_standard(raw):
        step5 = sanitize_note_content(raw)
        if step5 != raw:
            path.write_text(step5, encoding="utf-8")
        topics = parse_note_topics(step5, min_body_chars=20)
        index = parse_topic_index(step5)
        return {
            "file": path.name,
            "lecture": lec,
            "topics": len(topics),
            "index_rows": len(index),
            "changed": step5 != raw,
            "skipped": True,
        }
    step1 = _inject_preamble(raw, lec)
    step2 = strip_topic_index(step1)
    step3 = strip_lid_headings(step2)
    step4 = ensure_quiz_topic_structure(step3, lecture_num=lec, note_path=path.name)
    step5 = rebuild_topic_index(step4, lecture_num=lec, note_path=path.name)
    step6 = sanitize_note_content(step5)
    if step6 != raw:
        path.write_text(step6, encoding="utf-8")
    topics = parse_note_topics(step6, min_body_chars=20)
    index = parse_topic_index(step6)
    return {
        "file": path.name,
        "lecture": lec,
        "topics": len(topics),
        "index_rows": len(index),
        "changed": step6 != raw,
        "skipped": False,
    }


def main() -> None:
    force = "--force" in sys.argv
    results = []
    for path in sorted(NOTES_DIR.glob("L*.md")):
        results.append(format_note(path, force=force))
    for r in results:
        flag = "ok" if r.get("skipped") else ("updated" if r["changed"] else "ok")
        print(
            f"{r['file']}: {flag} | L{r['lecture']} | {r['index_rows']} index rows | {r['topics']} topics"
        )


if __name__ == "__main__":
    main()
