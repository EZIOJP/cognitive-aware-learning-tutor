"""Tests for slide merge and context loading."""

from __future__ import annotations

from pathlib import Path

from transcript_studio.context_loader import load_context_folder
from transcript_studio.source_loader import combine_transcript_sources
from transcript_studio.snapshots import (
    SlideCapture,
    TranscriptSegment,
    inject_snapshot_images,
    merge_slides_into_transcript,
)


def test_merge_slides_into_transcript_inserts_markers(tmp_path: Path) -> None:
    segments = [
        TranscriptSegment(start=0.0, end=5.0, text="Introduction to graphs."),
        TranscriptSegment(start=5.0, end=12.0, text="We cover BFS next."),
    ]
    captures = [
        SlideCapture(index=1, elapsed_sec=4.0, path=tmp_path / "1.png", captured_at="t1"),
        SlideCapture(index=2, elapsed_sec=10.0, path=tmp_path / "2.png", captured_at="t2"),
    ]
    text = merge_slides_into_transcript("ignored", segments, captures)
    assert "[SNAPSHOT 1]" in text
    assert "[SNAPSHOT 2]" in text


def test_inject_snapshot_images(tmp_path: Path) -> None:
    snaps = tmp_path / "snapshots"
    snaps.mkdir()
    (snaps / "1.png").write_bytes(b"png")
    note = tmp_path / "notes" / "lecture.md"
    note.parent.mkdir()
    raw = "Intro\n[SNAPSHOT 1]\nMore text"
    out = inject_snapshot_images(raw, snaps, note_path=note)
    assert "![Slide 1]" in out
    assert "../snapshots/1.png" in out or "snapshots/1.png" in out


def test_load_context_folder_md_and_ipynb(tmp_path: Path) -> None:
    (tmp_path / "prereq.md").write_text("# Prereq\n\nKnow Python basics.", encoding="utf-8")
    nb = {
        "cells": [
            {"cell_type": "markdown", "source": ["## Demo"]},
            {"cell_type": "code", "source": ["print('hi')"]},
        ]
    }
    import json

    (tmp_path / "demo.ipynb").write_text(json.dumps(nb), encoding="utf-8")
    ctx = load_context_folder(tmp_path)
    assert "Prereq" in ctx
    assert "print('hi')" in ctx
    assert "demo.ipynb" in ctx


def test_combine_transcript_files(tmp_path: Path) -> None:
    a = tmp_path / "part1.txt"
    b = tmp_path / "part2.txt"
    a.write_text("First lecture part.", encoding="utf-8")
    b.write_text("Second part continues.", encoding="utf-8")
    combined = combine_transcript_sources([a, b])
    assert "part1.txt" in combined
    assert "part2.txt" in combined
    assert "First lecture" in combined
    assert "Second part" in combined
