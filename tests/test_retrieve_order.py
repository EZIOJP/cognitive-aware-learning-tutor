"""Retrieve pipeline ordering: graph expand before rerank."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from backend.corpus.registry import ChunkRecord


def _fake_chunk(cid: str, *, source_type: str = "textbook") -> ChunkRecord:
    return ChunkRecord(
        chunk_id=cid,
        document_id="doc1",
        document_title="Test Book",
        source_document_id="src1",
        breadcrumb="ch1",
        modality_type="text",
        spatial_location=None,
        subject_tags=["linear_algebra"],
        source_type=source_type,
        raw_payload=f"content for {cid}",
    )


def test_hybrid_retrieve_reranks_after_graph_expansion():
    """Graph neighbors must be in the candidate pool passed to _rerank."""
    seed = _fake_chunk("seed-1")
    graph_neighbor = _fake_chunk("graph-1")
    seen_in_rerank: list[str] = []

    def fake_rerank(query: str, candidates: list, *, top_k: int):
        seen_in_rerank.extend(c.chunk_id for c in candidates)
        return candidates[:top_k]

    with (
        patch("backend.corpus.retrieve.load_bm25") as load_bm25,
        patch("backend.corpus.retrieve.list_chunks", return_value=[seed]),
        patch("backend.corpus.retrieve.is_available", return_value=False),
        patch("backend.corpus.retrieve.get_chunk", side_effect=lambda cid, db_path=None: {
            "seed-1": seed,
            "graph-1": graph_neighbor,
        }.get(cid)),
        patch("backend.corpus.retrieve._rrf_merge", return_value=[("seed-1", 1.0)]),
        patch("backend.corpus.retrieve._rerank", side_effect=fake_rerank),
        patch("backend.corpus.retrieve.SessionLocal", create=True),
        patch(
            "backend.corpus.graph_retrieve.graph_chunk_ids_for_query",
            return_value=["graph-1"],
        ),
        patch("backend.db.base.SessionLocal") as session_local,
    ):
        bm25 = MagicMock()
        bm25.ready = True
        bm25.search.return_value = [("seed-1", 1.0)]
        load_bm25.return_value = bm25
        session_local.return_value = MagicMock()

        from backend.corpus.retrieve import hybrid_retrieve

        hits = hybrid_retrieve("eigenvalue", use_graph=True, top_k=5)

    assert "graph-1" in seen_in_rerank
    assert "seed-1" in seen_in_rerank
    assert {h["chunk_id"] for h in hits} <= {"seed-1", "graph-1"}
