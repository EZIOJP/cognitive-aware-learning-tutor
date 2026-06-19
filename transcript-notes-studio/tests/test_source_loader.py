"""Tests for PDF and multi-format source loading."""

from __future__ import annotations

from pathlib import Path

import pytest

from transcript_studio import source_loader
from transcript_studio.source_loader import (
    combine_source_files,
    load_source_file,
    prepare_sources,
    reference_slice,
    split_source_paths,
)


def test_load_source_txt(tmp_path: Path) -> None:
    f = tmp_path / "notes.txt"
    f.write_text("Hello transcript", encoding="utf-8")
    assert load_source_file(f) == "Hello transcript"


def test_split_transcript_and_reference(tmp_path: Path) -> None:
    txt = tmp_path / "live_captions.txt"
    pdf = tmp_path / "slides.pdf"
    txt.write_text("lecture words", encoding="utf-8")
    pdf.write_bytes(b"%PDF-1.4")
    transcripts, refs = split_source_paths([txt, pdf])
    assert transcripts == [txt]
    assert refs == [pdf]


def test_prepare_sources_auto_aggressive(tmp_path: Path) -> None:
    txt = tmp_path / "live_captions_20260611.txt"
    md = tmp_path / "numpy_ref.md"
    txt.write_text("hello class", encoding="utf-8")
    md.write_text("# NumPy arrays", encoding="utf-8")
    transcript, reference, auto = prepare_sources([txt, md])
    assert "hello class" in transcript
    assert "NumPy arrays" in reference
    assert auto is True


def test_combine_txt_and_md_as_transcript_only(tmp_path: Path) -> None:
    a = tmp_path / "a.txt"
    b = tmp_path / "b.md"
    a.write_text("Part A", encoding="utf-8")
    b.write_text("Part B slides", encoding="utf-8")
    transcripts, refs = split_source_paths([a, b])
    assert len(transcripts) == 1
    assert refs == [b]


def test_reference_slice_windows() -> None:
    ref = "".join(chr(65 + (i % 26)) for i in range(20000))
    s1 = reference_slice(ref, 1, 4, window=5000)
    s2 = reference_slice(ref, 2, 4, window=5000)
    assert s1 != s2
    assert len(s1) == 5000


def test_unsupported_extension(tmp_path: Path) -> None:
    f = tmp_path / "data.docx"
    f.write_text("x", encoding="utf-8")
    with pytest.raises(ValueError, match="Unsupported"):
        load_source_file(f)


def test_load_pdf(monkeypatch, tmp_path: Path) -> None:
    pdf = tmp_path / "lecture.pdf"
    pdf.write_bytes(b"%PDF-1.4")

    def fake_extract(path: Path, *, max_chars: int | None = None) -> str:
        return "Chapter 1: Introduction"

    monkeypatch.setattr(source_loader, "_extract_pdf", fake_extract)
    assert load_source_file(pdf) == "Chapter 1: Introduction"


def test_context_folder_excludes_source_paths(tmp_path: Path) -> None:
    from transcript_studio.context_loader import load_context_folder

    shared = tmp_path / "numpy_ref.md"
    extra = tmp_path / "prereq.md"
    shared.write_text("# Shared reference", encoding="utf-8")
    extra.write_text("# Prereq only", encoding="utf-8")

    text = load_context_folder(tmp_path, exclude_paths={shared.resolve()})
    assert "Prereq only" in text
    assert "Shared reference" not in text

