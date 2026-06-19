"""Tests for wikilink_injector.py."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from transcript_studio.wikilink_injector import (
    _add_backlink,
    _code_regions,
    _inject_wikilinks_in_text,
    _strip_backlinks_section,
    build_heading_index,
    inject_wikilinks,
)


# ---------------------------------------------------------------------------
# _code_regions
# ---------------------------------------------------------------------------


def test_code_regions_single_fence():
    text = "Before.\n```python\ncode here\n```\nAfter."
    regions = _code_regions(text)
    assert len(regions) == 1
    start, end = regions[0]
    assert "code here" in text[start:end]


def test_code_regions_no_fence():
    text = "No code here at all."
    assert _code_regions(text) == []


def test_code_regions_multiple_fences():
    text = "A.\n```\nfirst\n```\nB.\n```\nsecond\n```\nC."
    regions = _code_regions(text)
    assert len(regions) == 2


# ---------------------------------------------------------------------------
# build_heading_index
# ---------------------------------------------------------------------------


def test_build_heading_index(tmp_path):
    (tmp_path / "note1.md").write_text("## Introduction\nSome text.\n### Details\nMore.", encoding="utf-8")
    (tmp_path / "note2.md").write_text("## Conclusion\nFinal thoughts.", encoding="utf-8")
    idx = build_heading_index(tmp_path)
    assert "Introduction" in idx
    assert "Conclusion" in idx
    assert "Details" in idx
    assert idx["Introduction"] == "note1"


# ---------------------------------------------------------------------------
# _inject_wikilinks_in_text
# ---------------------------------------------------------------------------


def test_inject_links_basic():
    index = {"Introduction": "note1", "Conclusion": "note2"}
    content = "See the Introduction section and the Conclusion."
    modified, targets = _inject_wikilinks_in_text(content, index, own_stem="current")
    assert "[[Introduction]]" in modified
    assert "[[Conclusion]]" in modified
    assert "note1" in targets
    assert "note2" in targets


def test_inject_links_not_in_code_fence():
    index = {"Introduction": "other_note"}
    content = "Normal text.\n```python\n# Introduction to Python\n```\nEnd."
    modified, targets = _inject_wikilinks_in_text(content, index, own_stem="current")
    # The heading inside the code fence should not be linked
    assert "[[Introduction]]" not in modified or "```python" in modified


def test_inject_links_no_self_link():
    index = {"Introduction": "current_note"}
    content = "The Introduction is here."
    modified, _ = _inject_wikilinks_in_text(content, index, own_stem="current_note")
    assert "[[Introduction]]" not in modified


def test_inject_links_already_linked_not_doubled():
    index = {"Introduction": "other_note"}
    content = "See [[Introduction]] for more."
    modified, _ = _inject_wikilinks_in_text(content, index, own_stem="current")
    assert modified.count("[[Introduction]]") == 1


def test_inject_links_first_occurrence_only():
    index = {"Arrays": "numpy_note"}
    content = "Arrays are important. Arrays are vectors. Arrays can be sliced."
    modified, _ = _inject_wikilinks_in_text(content, index, own_stem="current")
    assert modified.count("[[Arrays]]") == 1


# ---------------------------------------------------------------------------
# _strip_backlinks_section
# ---------------------------------------------------------------------------


def test_strip_backlinks_section_removes_existing():
    content = "# Note\n\nContent here.\n\n---\n\n## Backlinks\n\n- [[other]] → heading"
    stripped = _strip_backlinks_section(content)
    assert "Backlinks" not in stripped
    assert "Content here." in stripped


def test_strip_backlinks_section_no_backlinks():
    content = "# Note\n\nClean content."
    assert _strip_backlinks_section(content) == content


# ---------------------------------------------------------------------------
# inject_wikilinks — full end-to-end
# ---------------------------------------------------------------------------


def test_inject_wikilinks_creates_links(tmp_path):
    # Create two notes where note_a references a heading from note_b
    note_b = tmp_path / "note_b.md"
    note_b.write_text("## Arrays\nNumPy arrays are multi-dimensional.", encoding="utf-8")

    note_a = tmp_path / "note_a.md"
    note_a.write_text("# Lecture 1\n\nWe will study Arrays in depth.", encoding="utf-8")

    inject_wikilinks(note_a, folder=tmp_path)
    content_a = note_a.read_text(encoding="utf-8")
    assert "[[Arrays]]" in content_a


def test_inject_wikilinks_creates_backlinks(tmp_path):
    note_b = tmp_path / "note_b.md"
    note_b.write_text("## Arrays\nContent.", encoding="utf-8")

    note_a = tmp_path / "note_a.md"
    note_a.write_text("# Intro\n\nArrays are studied here.", encoding="utf-8")

    inject_wikilinks(note_a, folder=tmp_path)

    content_b = note_b.read_text(encoding="utf-8")
    assert "Backlinks" in content_b
    assert "note_a" in content_b


def test_inject_wikilinks_idempotent(tmp_path):
    note_b = tmp_path / "note_b.md"
    note_b.write_text("## Arrays\nContent.", encoding="utf-8")

    note_a = tmp_path / "note_a.md"
    note_a.write_text("# Intro\n\nArrays are studied here.", encoding="utf-8")

    inject_wikilinks(note_a, folder=tmp_path)
    content_after_first = note_a.read_text(encoding="utf-8")

    inject_wikilinks(note_a, folder=tmp_path)
    content_after_second = note_a.read_text(encoding="utf-8")

    # No duplicate wikilinks
    assert content_after_second.count("[[Arrays]]") == content_after_first.count("[[Arrays]]")


def test_inject_wikilinks_missing_file_returns_path(tmp_path):
    fake = tmp_path / "nonexistent.md"
    result = inject_wikilinks(fake, folder=tmp_path)
    assert result == fake
