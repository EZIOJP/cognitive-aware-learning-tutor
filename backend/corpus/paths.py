"""Local corpus paths and constants."""

from __future__ import annotations

from pathlib import Path

from backend.paths import CORPUS_DIR, RAW_LIBRARY_DIR, ROOT

REGISTRY_DB = CORPUS_DIR / "registry.db"
BM25_PATH = CORPUS_DIR / "bm25.pkl"
QDRANT_PATH = CORPUS_DIR / "qdrant"


def get_registry_db() -> Path:
    import os

    override = os.environ.get("CORPUS_REGISTRY_DB")
    if override:
        return Path(override)
    return REGISTRY_DB


def get_bm25_path() -> Path:
    import os

    override = os.environ.get("CORPUS_BM25_PATH")
    if override:
        return Path(override)
    return BM25_PATH

DEFAULT_TARGET_TOKENS = 500
DEFAULT_OVERLAP_RATIO = 0.15
HYBRID_POOL = 20
RERANK_TOP = 5

ModalityType = str  # narrative_text | definition | equation | python_code | mermaid_diagram | tabular_data


def ensure_corpus_dirs() -> None:
    CORPUS_DIR.mkdir(parents=True, exist_ok=True)
    RAW_LIBRARY_DIR.mkdir(parents=True, exist_ok=True)


def resolve_repo_path(path: str | Path) -> Path:
    p = Path(path)
    if not p.is_absolute():
        p = ROOT / p
    return p.resolve()
