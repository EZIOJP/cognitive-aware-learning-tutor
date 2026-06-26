"""Tests for corpus chunking, registry, and retrieval."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from backend.corpus.chunker import chunk_markdown, filter_chapter_markdown
from backend.corpus.ingest import ingest_markdown
from backend.corpus.registry import chunk_count, init_registry, verify_document
from backend.corpus.retrieve import hybrid_retrieve


SAMPLE_MD = """# Mathematics for Machine Learning

## Chapter 1 Introduction

Machine learning uses vectors to represent data.

```python
import numpy as np
x = np.array([1, 2, 3])
print(x.shape)
```

## Chapter 2 Linear Algebra

An eigenvalue lambda satisfies Av = lambda v.

### Dot product

The dot product measures similarity between vectors.
"""


@pytest.fixture()
def isolated_corpus(tmp_path) -> tuple[Path, Path]:
    db = tmp_path / "registry.db"
    bm = tmp_path / "bm25.pkl"
    init_registry(db)
    return db, bm


def test_filter_chapter_markdown():
    ch1 = filter_chapter_markdown(SAMPLE_MD, 1)
    assert "Chapter 1" in ch1
    assert "eigenvalue" not in ch1.lower()


def test_filter_chapter_markdown_mml_hash_headings():
    mml_md = """# Front matter
## Contents

# 1
## Introduction and Motivation
Machine learning uses vectors.

# 2
## Linear Algebra
An eigenvalue satisfies Av = lambda v.
"""
    ch1 = filter_chapter_markdown(mml_md, 1)
    assert "Introduction" in ch1
    assert "eigenvalue" not in ch1.lower()
    ch2 = filter_chapter_markdown(mml_md, 2)
    assert "Linear Algebra" in ch2
    assert "eigenvalue" in ch2.lower()


def test_chunk_markdown_preserves_code_fence():
    chunks = chunk_markdown(SAMPLE_MD, document_breadcrumb="MML")
    code_chunks = [c for c in chunks if c.modality_type == "python_code"]
    assert code_chunks
    assert "numpy" in code_chunks[0].text


def test_ingest_and_retrieve_keyword_fallback(isolated_corpus):
    db, bm = isolated_corpus
    result = ingest_markdown(
        markdown=SAMPLE_MD,
        document_id="test_mml",
        document_title="Test MML",
        source_type="textbook",
        subject_tags=["linear_algebra"],
        db_path=db,
    )
    assert result["chunks_ingested"] >= 3
    assert chunk_count(document_id="test_mml", db_path=db) >= 3
    report = verify_document("test_mml", db_path=db)
    assert report["chunk_count"] >= 3

    hits = hybrid_retrieve(
        "eigenvalue",
        subject_tags=["linear_algebra"],
        top_k=3,
        db_path=db,
        bm25_path=bm,
    )
    assert hits
    assert any("eigen" in h["raw_payload"].lower() for h in hits)


def test_study_intel_corpus_helper(monkeypatch):
    monkeypatch.setattr(
        "backend.corpus.retrieve.corpus_available",
        lambda **_: False,
    )
    from backend.transcripts.study_intel import _combined_source_material

    text, hits = _combined_source_material(["fallback text"], topic="numpy")
    assert "fallback" in text
    assert hits == []


def test_purge_test_documents(isolated_corpus):
    db, bm = isolated_corpus
    ingest_markdown(
        markdown=SAMPLE_MD,
        document_id="test_mml",
        document_title="Test MML",
        source_type="textbook",
        subject_tags=["linear_algebra"],
        db_path=db,
    )
    from backend.corpus.purge import purge_test_documents

    result = purge_test_documents(db_path=db, bm25_path=bm)
    assert result["purged"] == 1
    assert chunk_count(document_id="test_mml", db_path=db) == 0


@pytest.mark.integration
def test_benchmark_recall_threshold():
    from pathlib import Path

    from backend.corpus.benchmark import run_benchmark

    fixture = Path("tests/fixtures/mml_golden_qa.json")
    if not fixture.is_file():
        pytest.skip("golden fixture missing")
    data = fixture.read_text(encoding="utf-8")
    if '"expected_chunk_ids": []' in data and data.count("expected_chunk_ids") == data.count("[]"):
        pytest.skip("golden fixture not populated yet")
    report = run_benchmark(fixture, top_k=5)
    assert report["recall_at_k"] >= 0.5, report


def test_code_lint_blocks_bad_import():
    from backend.corpus.code_lint import lint_python_block

    bad = lint_python_block("import os\nos.system('x')")
    assert not bad["ok"]
    ok = lint_python_block("import numpy as np\nprint(np.array([1]))")
    assert ok["ok"]


def test_ingest_all_full_books_skips_missing(monkeypatch):
    from backend.corpus.library import ingest_all_full_books

    def fake_scan(entry):
        from backend.corpus.library import BookSlot

        return BookSlot(
            subject_id=entry["id"],
            label=entry["label"],
            short_label=entry["short_label"],
            description=entry["description"],
            ingest_priority=entry["ingest_priority"],
            expected_filename="",
            document_id="",
            format="pdf",
            file_present=False,
            file_size_bytes=0,
            metadata_present=True,
            ingested_chunks=0,
            auto_chapters=None,
        )

    monkeypatch.setattr("backend.corpus.library.scan_book_slot", fake_scan)
    result = ingest_all_full_books(skip_indexed=True)
    assert result["ingested"] == 0
    assert len(result["skipped"]) == 4
    assert all(s["reason"] == "missing_file" for s in result["skipped"])


def test_ingest_lecture_handoff_transcript_only(isolated_corpus, tmp_path):
    from backend.corpus.handoff import ingest_lecture_handoff

    tx = tmp_path / "sample_lecture.txt"
    tx.write_text("NumPy arrays support indexing and slicing.\n", encoding="utf-8")
    result = ingest_lecture_handoff(transcript_path=tx)
    assert result.get("transcript_chunks", 0) >= 1
    assert "transcript" in result


def test_pdf_to_markdown_extracts_text(monkeypatch, tmp_path):
    from backend.corpus.converters import pdf_to_markdown

    class FakePage:
        def get_text(self, _mode):
            return {
                "blocks": [
                    {
                        "type": 0,
                        "lines": [
                            {
                                "spans": [
                                    {"text": "Eigenvalues", "size": 17.0},
                                    {"text": " and vectors", "size": 12.0},
                                ]
                            }
                        ],
                    }
                ]
            }

    class FakeDoc:
        def __iter__(self):
            return iter([FakePage()])

        def close(self):
            return None

    class FakeFitz:
        @staticmethod
        def open(_path):
            return FakeDoc()

    monkeypatch.setitem(sys.modules, "fitz", FakeFitz)
    pdf = tmp_path / "sample.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    md = pdf_to_markdown(pdf)
    assert "Eigenvalues" in md
    assert "# Eigenvalues" in md
