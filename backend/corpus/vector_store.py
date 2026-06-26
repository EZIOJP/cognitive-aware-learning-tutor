"""Dense vector store — Qdrant local with SQLite fallback."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np

from backend.corpus.paths import QDRANT_PATH, ensure_corpus_dirs
from backend.corpus.registry import ChunkRecord, list_chunks

if TYPE_CHECKING:
    pass

log = logging.getLogger(__name__)

_COLLECTION = "study_chunks"
_VECTOR_SIZE = 384  # all-MiniLM-L6-v2


class VectorStore:
    def __init__(self) -> None:
        self._mode = "sqlite"
        self._client = None
        self._try_qdrant()

    def _try_qdrant(self) -> None:
        try:
            from qdrant_client import QdrantClient  # type: ignore
            from qdrant_client.models import Distance, PointStruct, VectorParams  # type: ignore

            ensure_corpus_dirs()
            self._client = QdrantClient(path=str(QDRANT_PATH))
            self._qdrant_models = (Distance, PointStruct, VectorParams)
            if not self._client.collection_exists(_COLLECTION):
                self._client.create_collection(
                    collection_name=_COLLECTION,
                    vectors_config=VectorParams(size=_VECTOR_SIZE, distance=Distance.COSINE),
                )
            self._mode = "qdrant"
            log.info("Corpus vector store: Qdrant local at %s", QDRANT_PATH)
        except Exception as exc:  # noqa: BLE001
            log.info("Qdrant unavailable (%s); using SQLite embeddings", exc)
            self._mode = "sqlite"
            self._client = None

    def delete_chunk_ids(self, chunk_ids: list[str]) -> int:
        if not chunk_ids:
            return 0
        if self._mode == "qdrant" and self._client is not None:
            from qdrant_client.models import PointIdsList  # type: ignore

            self._client.delete(
                collection_name=_COLLECTION,
                points_selector=PointIdsList(points=chunk_ids),
            )
            return len(chunk_ids)
        return 0

    def upsert_chunks(self, chunks: list[ChunkRecord]) -> None:
        if not chunks:
            return
        if self._mode == "qdrant" and self._client is not None:
            _, PointStruct, _ = self._qdrant_models
            points = []
            for c in chunks:
                if c.embedding is None:
                    continue
                points.append(
                    PointStruct(
                        id=c.chunk_id,
                        vector=c.embedding.tolist(),
                        payload={
                            "chunk_id": c.chunk_id,
                            "document_id": c.document_id,
                            "breadcrumb": c.breadcrumb,
                        },
                    )
                )
            if points:
                self._client.upsert(collection_name=_COLLECTION, points=points)
            return
        # sqlite embeddings written at insert_chunk time

    def search(
        self,
        query_vector: np.ndarray,
        *,
        top_k: int = 20,
        subject: str | None = None,
    ) -> list[tuple[str, float]]:
        if self._mode == "qdrant" and self._client is not None:
            response = self._client.query_points(
                collection_name=_COLLECTION,
                query=query_vector.tolist(),
                limit=top_k * 2,
            )
            points = getattr(response, "points", response)
            results = [(str(hit.id), float(hit.score)) for hit in points]
            if subject:
                allowed = {c.chunk_id for c in list_chunks(subject=subject)}
                results = [(cid, s) for cid, s in results if cid in allowed]
            return results[:top_k]

        return _sqlite_dense_search(query_vector, top_k=top_k, subject=subject)


def _sqlite_dense_search(
    query_vector: np.ndarray,
    *,
    top_k: int,
    subject: str | None,
) -> list[tuple[str, float]]:
    from backend.transcripts.embedding import cosine_similarity

    chunks = list_chunks(subject=subject)
    scored: list[tuple[str, float]] = []
    for c in chunks:
        if c.embedding is None:
            continue
        scored.append((c.chunk_id, cosine_similarity(query_vector, c.embedding)))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_k]
