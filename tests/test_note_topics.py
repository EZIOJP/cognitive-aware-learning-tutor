"""Tests for lecture note topic parsing (L{n}-Txx + decimal fallback)."""

from backend.transcripts.note_topics import (
    parse_note_topics,
    remap_legacy_note_path,
    topics_as_sections,
)


L5_SAMPLE = """
# Pandas Operations

## 🗂️ Topic Index (quiz-gen lookup table)

| ID | Topic | One-line scope |
|---|---|---|
| `L5-T05` | Unique values | unique nunique value_counts |
| `L5-T08` | Duplicates | duplicated drop_duplicates |

## 🆕 New Functions & Methods Learned Today (Quick Lookup)

| Function | What | Topic |
|---|---|---|
| `df.unique()` | distinct | `L5-T05` |

## `L5-T05` — Unique values: unique(), nunique(), value_counts()

```python
df["col"].unique()
```

Use unique for the array of distinct values. nunique counts them.
value_counts returns frequencies sorted descending.

## `L5-T08` — Identifying & handling duplicates

```python
df.duplicated()
df.drop_duplicates()
```

keep first last or False. subset selects columns.

## Quick Reference Cheat-Sheet

Do not quiz this meta section.
"""

DECIMAL_SAMPLE = """
# Lecture 4

## 🆕 New Functions & Methods

| fn | does |
|---|---|

## 2. Vectorization — Deep Dive

### 2.1 The core idea

Vectorization means operating on whole arrays without Python loops.
This paragraph is long enough to count as a real topic body for quizzes.

### 2.2 The demonstration

np.vectorize wraps a scalar function. More body text here so the section
passes the minimum character threshold used by the topic parser.

## Quick Reference Cheat-Sheet

meta only
"""


def test_remap_legacy_note_path_string():
    assert (
        remap_legacy_note_path("lecture5/lecture5_pandas_operations_notes.md")
        == "data_foundations/lecture_5/lecture5_pandas_operations_notes.md"
    )
    assert (
        remap_legacy_note_path("lecture_2/numpy_lecture_notes.md")
        == "data_foundations/lecture_2/numpy_lecture_notes.md"
    )


def test_canonical_library_path_only_when_exists():
    from backend.transcripts.note_topics import canonical_library_path

    # Real moved file
    assert canonical_library_path(
        "lecture5/lecture5_pandas_operations_notes.md"
    ).startswith("data_foundations/lecture_5/")
    # Fake legacy path must stay unchanged (tests / new notes)
    assert canonical_library_path("lecture_2/short.md") == "lecture_2/short.md"


def test_parse_l5_topics_skips_meta():
    topics = parse_note_topics(L5_SAMPLE)
    ids = [t.topic_id for t in topics]
    assert ids == ["L5-T05", "L5-T08"]
    assert all(t.source == "lid" for t in topics)
    assert "unique" in topics[0].title.lower() or "Unique" in topics[0].title


def test_parse_topic_filter():
    topics = parse_note_topics(L5_SAMPLE, topic_ids=["L5-T05"])
    assert len(topics) == 1
    assert topics[0].topic_id == "L5-T05"


def test_decimal_fallback():
    topics = parse_note_topics(DECIMAL_SAMPLE)
    assert topics
    assert all(t.source in ("decimal", "heading") for t in topics)
    ids = {t.topic_id for t in topics}
    assert "2.1" in ids or "2" in ids


def test_topics_as_sections_labels():
    topics = parse_note_topics(L5_SAMPLE)
    sections = topics_as_sections(topics)
    assert sections[0][0].startswith("L5-T05")
    assert "unique()" in sections[0][1].lower() or "unique" in sections[0][1].lower()
