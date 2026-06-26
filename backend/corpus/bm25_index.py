"""BM25 sparse index persisted alongside registry."""

from __future__ import annotations

import pickle
import re
from pathlib import Path

from backend.corpus.paths import BM25_PATH, ensure_corpus_dirs, get_bm25_path
from backend.corpus.registry import ChunkRecord, list_chunks

_TOKEN_RE = re.compile(r"[a-zA-Z0-9_]+")


def _tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text)]


class Bm25Index:
    def __init__(self) -> None:
        self._chunk_ids: list[str] = []
        self._bm25 = None

    @property
    def ready(self) -> bool:
        return self._bm25 is not None and bool(self._chunk_ids)

    def build(self, chunks: list[ChunkRecord]) -> None:
        from rank_bm25 import BM25Okapi  # type: ignore

        self._chunk_ids = [c.chunk_id for c in chunks]
        corpus = [_tokenize(f"{c.breadcrumb} {c.raw_payload}") for c in chunks]
        self._bm25 = BM25Okapi(corpus) if corpus else None

    def search(self, query: str, *, top_k: int = 20) -> list[tuple[str, float]]:
        if not self.ready or self._bm25 is None:
            return []
        scores = self._bm25.get_scores(_tokenize(query))
        ranked = sorted(
            zip(self._chunk_ids, scores, strict=False),
            key=lambda x: x[1],
            reverse=True,
        )
        return [(cid, float(s)) for cid, s in ranked[:top_k] if s > 0]


def save_bm25(index: Bm25Index, path: Path | None = None) -> None:
    ensure_corpus_dirs()
    target = path or get_bm25_path()
    with target.open("wb") as f:
        pickle.dump({"chunk_ids": index._chunk_ids, "bm25": index._bm25}, f)


def load_bm25(path: Path | None = None) -> Bm25Index:
    index = Bm25Index()
    target = path or get_bm25_path()
    if not target.is_file():
        return index
    with target.open("rb") as f:
        data = pickle.load(f)
    index._chunk_ids = data.get("chunk_ids", [])
    index._bm25 = data.get("bm25")
    return index


def rebuild_bm25_from_registry(*, db_path: Path | None = None, bm25_path: Path | None = None) -> Bm25Index:
    chunks = list_chunks(db_path=db_path)
    index = Bm25Index()
    index.build(chunks)
    save_bm25(index, bm25_path)
    return index
