"""Tests for topic/function-level note search."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.models.study import Base
from backend.transcripts.library import search_library_notes
from backend.transcripts.note_search import search_note_content

MERGE_NOTE = """# Pandas lecture

## Topic Index

| ID | Topic | One-line scope |
|---|---|---|
| `L5-T11` | Combining DataFrames — concat vs merge | stacking vs joins |
| `L5-T12` | Merge join types | inner outer left right |

## New Functions

| Function / Syntax | What it does | Topic |
|---|---|---|
| `pd.merge(df1, df2, on=..., how=...)` | SQL-style key-based join | `L5-T11` |
| `pd.merge(..., left_on=..., right_on=...)` | mismatched key names | `L5-T13` |

## `L5-T11` — Combining DataFrames: pd.concat vs pd.merge

Use merge when you need a key-based join between tables.

```python
pd.merge(samples_orders, samples_products, on="product_id", how="inner")
```

## `L5-T12` — Merge join types (how=)

Inner, outer, left, and right joins follow SQL semantics.
"""


@pytest.fixture()
def db(tmp_path, monkeypatch):
    notes_dir = tmp_path / "notes"
    notes_dir.mkdir()
    monkeypatch.setattr("backend.transcripts.library.NOTES_DIR", notes_dir)
    monkeypatch.setattr("backend.paths.NOTES_DIR", notes_dir)
    monkeypatch.setattr("backend.transcripts.note_search.paths.NOTES_DIR", notes_dir)

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_search_note_content_finds_topics_and_functions():
    hits = search_note_content(
        "merge",
        relative_path="data_foundations/pandas.md",
        file_title="Pandas lecture",
        folder_path="data_foundations",
        kind="lecture",
        body=MERGE_NOTE,
    )
    kinds = {h["match_kind"] for h in hits}
    assert "topic" in kinds
    assert "function" in kinds
    topic_ids = {h["topic_id"] for h in hits if h["topic_id"]}
    assert "L5-T11" in topic_ids
    assert "L5-T12" in topic_ids
    fn_labels = [h["label"] for h in hits if h["match_kind"] == "function"]
    assert any("pd.merge" in lbl for lbl in fn_labels)


def test_search_library_notes_merge(db):
    from backend.transcripts.library import create_note_file

    create_note_file(
        db,
        user_id=1,
        title="Pandas lecture",
        folder_path="data_foundations",
        kind="lecture",
        content=MERGE_NOTE,
    )
    create_note_file(
        db,
        user_id=1,
        title="merge filename only",
        folder_path="data_foundations",
        kind="lecture",
        content="# Other\n\nNo keyword here except once: merge.\n",
    )
    hits = search_library_notes(db, 1, "merge", limit=20)
    assert len(hits) >= 3
    by_path = {h["relative_path"]: h["body_match_count"] for h in hits}
    counts = list(by_path.values())
    assert max(counts) > min(counts)
    # Richest file should be listed first (most body matches)
    assert hits[0]["body_match_count"] == max(counts)
    assert any(h["match_kind"] == "function" for h in hits)
    assert any(h["topic_id"] == "L5-T12" for h in hits)
