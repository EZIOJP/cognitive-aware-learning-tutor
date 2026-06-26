"""Hybrid retrieval: dense + BM25 + optional rerank."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import numpy as np

from backend.corpus.bm25_index import load_bm25, rebuild_bm25_from_registry
from backend.corpus.paths import HYBRID_POOL, RERANK_TOP
from backend.corpus.registry import ChunkRecord, get_chunk, list_chunks
from backend.corpus.vector_store import VectorStore
from backend.transcripts.embedding import encode_texts, is_available

log = logging.getLogger(__name__)


def _rrf_merge(
    dense: list[tuple[str, float]],
    sparse: list[tuple[str, float]],
    *,
    k: int = 60,
) -> list[tuple[str, float]]:
    scores: dict[str, float] = {}
    for rank, (cid, _) in enumerate(dense):
        scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank + 1)
    for rank, (cid, _) in enumerate(sparse):
        scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)


def _rerank(query: str, candidates: list[ChunkRecord], *, top_k: int) -> list[ChunkRecord]:
    if len(candidates) <= top_k:
        return candidates
    try:
        from flashrank import Ranker, RerankRequest  # type: ignore

        ranker = Ranker()
        passages = [{"id": c.chunk_id, "text": c.raw_payload[:1200]} for c in candidates]
        req = RerankRequest(query=query, passages=passages)
        results = ranker.rerank(req)
        order = [r["id"] for r in results]
        by_id = {c.chunk_id: c for c in candidates}
        out = [by_id[cid] for cid in order if cid in by_id]
        return out[:top_k]
    except Exception as exc:  # noqa: BLE001
        log.debug("FlashRank unavailable (%s); using RRF order", exc)
        return candidates[:top_k]


def hybrid_retrieve(
    query: str,
    *,
    subject_tags: list[str] | None = None,
    top_k: int = RERANK_TOP,
    pool_size: int = HYBRID_POOL,
    db_path: Path | None = None,
    bm25_path: Path | None = None,
    use_graph: bool = True,
    user_id: int | None = None,
) -> list[dict[str, Any]]:
    if not query.strip():
        return []

    bm25 = load_bm25(bm25_path)
    if list_chunks(db_path=db_path) and not bm25.ready:
        rebuild_bm25_from_registry(db_path=db_path, bm25_path=bm25_path)
        bm25 = load_bm25(bm25_path)

    subject = subject_tags[0] if subject_tags and len(subject_tags) == 1 else None
    sparse_hits = bm25.search(query, top_k=pool_size) if bm25.ready else []

    dense_hits: list[tuple[str, float]] = []
    if is_available():
        vec = encode_texts([query])
        if vec is not None and len(vec):
            store = VectorStore()
            dense_hits = store.search(vec[0], top_k=pool_size, subject=subject)

    if not dense_hits and not sparse_hits:
        # keyword fallback on breadcrumbs
        q = query.lower()
        chunks = list_chunks(subject=subject, db_path=db_path)
        sparse_hits = [
            (c.chunk_id, 1.0)
            for c in chunks
            if q in c.raw_payload.lower() or q in c.breadcrumb.lower()
        ][:pool_size]

    merged = _rrf_merge(dense_hits, sparse_hits)[:pool_size]
    candidates: list[ChunkRecord] = []
    for cid, _ in merged:
        c = get_chunk(cid, db_path=db_path)
        if c is None:
            continue
        if subject_tags and not any(t in c.subject_tags for t in subject_tags):
            continue
        candidates.append(c)

    ranked = _rerank(query, candidates, top_k=top_k)
    hits = [chunk_to_hit(c) for c in ranked]

    if use_graph:
        try:
            from backend.corpus.graph_retrieve import graph_chunk_ids_for_query, merge_graph_hits
            from backend.db.base import SessionLocal

            db = SessionLocal()
            try:
                graph_ids = graph_chunk_ids_for_query(db, query, user_id=user_id, top_k=top_k)
            finally:
                db.close()
            graph_hits = []
            for cid in graph_ids:
                rec = get_chunk(cid, db_path=db_path)
                if rec:
                    graph_hits.append(chunk_to_hit(rec))
            hits = merge_graph_hits(hits, graph_hits, top_k=top_k)
        except Exception as exc:  # noqa: BLE001
            log.debug("Graph retrieve skipped: %s", exc)

    return hits


def chunk_to_hit(c: ChunkRecord) -> dict[str, Any]:
    return {
        "chunk_id": c.chunk_id,
        "document_id": c.document_id,
        "document_title": c.document_title,
        "breadcrumb": c.breadcrumb,
        "modality_type": c.modality_type,
        "spatial_location": c.spatial_location,
        "subject_tags": c.subject_tags,
        "raw_payload": c.raw_payload,
        "citation": f"[{c.document_title}, {c.breadcrumb}]",
    }


def format_hits_for_prompt(hits: list[dict[str, Any]], *, max_chars: int = 12000) -> str:
    parts: list[str] = []
    used = 0
    for h in hits:
        block = (
            f"<!-- cite: {h['chunk_id']} -->\n"
            f"{h['citation']}\n"
            f"{h['raw_payload']}"
        )
        if used + len(block) > max_chars:
            break
        parts.append(block)
        used += len(block)
    return "\n\n---\n\n".join(parts)


def corpus_available(*, db_path: Path | None = None) -> bool:
    return list_chunks(db_path=db_path) != []
