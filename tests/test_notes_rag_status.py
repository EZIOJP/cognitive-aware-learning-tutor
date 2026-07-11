"""Tests for notes RAG health gate."""

from __future__ import annotations

from unittest.mock import patch

from backend.corpus.notes_rag_status import assess_notes_rag, ensure_notes_rag_textbooks


def test_assess_broken_when_empty() -> None:
    with (
        patch("backend.corpus.notes_rag_status.corpus_available", return_value=False),
        patch("backend.corpus.notes_rag_status.chunk_count", return_value=0),
        patch("backend.corpus.notes_rag_status.list_documents", return_value=[]),
        patch("backend.corpus.notes_rag_status.list_chunks", return_value=[]),
        patch("backend.corpus.notes_rag_status.retrieval_backend", return_value="qdrant"),
    ):
        a = assess_notes_rag()
    assert a["status"] == "broken"
    assert a["needs_rebuild"] is True
    assert a["skip_rebuild"] is False


def test_ensure_skips_when_usable() -> None:
    healthy = {
        "status": "ok",
        "usable": True,
        "needs_rebuild": False,
        "needs_cleanup": False,
        "skip_rebuild": True,
        "total_chunks": 100,
        "textbook_chunks": 100,
        "summary": "notes_rag=ok",
        "reasons": [],
    }
    with patch("backend.corpus.notes_rag_status.assess_notes_rag", return_value=healthy):
        result = ensure_notes_rag_textbooks(force=False)
    assert result["skipped_rebuild"] is True
    assert result["action"] == "skipped"
    assert result["transcripts_ingested"] == 0
