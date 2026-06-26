"""Dual-layer semantic prompt cache for LLM calls.

Layer 1 — Exact hash match (SHA-256 of normalized prompt).
Layer 2 — Embedding cosine similarity > threshold (default 0.95).

Backed by a dedicated SQLite database in transcript-notes-studio/data/llm_cache.db.
Runs on CPU only; does not require GPU.
"""

from __future__ import annotations

import hashlib
import logging
import sqlite3
import time
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np

log = logging.getLogger(__name__)

_CACHE_DB_PATH: Path | None = None
_EMBED_MODEL = None
_EMBED_MODEL_NAME = "all-MiniLM-L6-v2"

# ---------------------------------------------------------------------------
# DB path (resolve relative to this file's project root)
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_CACHE_DB = _PROJECT_ROOT / "data" / "llm_cache.db"


def _get_db_path() -> Path:
    global _CACHE_DB_PATH
    if _CACHE_DB_PATH is not None:
        return _CACHE_DB_PATH
    path = _DEFAULT_CACHE_DB
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def set_cache_db_path(path: Path) -> None:
    """Override the cache DB path (useful for testing)."""
    global _CACHE_DB_PATH
    _CACHE_DB_PATH = path


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_DDL = """
CREATE TABLE IF NOT EXISTS llm_cache (
    id INTEGER PRIMARY KEY,
    prompt_hash TEXT UNIQUE,
    prompt_vector BLOB,
    response TEXT,
    model TEXT,
    temperature REAL,
    created_at INTEGER
);
CREATE INDEX IF NOT EXISTS ix_llm_cache_model ON llm_cache(model);
"""


def _get_conn(db_path: Path | None = None) -> sqlite3.Connection:
    path = db_path or _get_db_path()
    conn = sqlite3.connect(str(path))
    conn.executescript(_DDL)
    conn.commit()
    return conn


# ---------------------------------------------------------------------------
# Embedding helper
# ---------------------------------------------------------------------------


def _load_embed_model():
    global _EMBED_MODEL
    if _EMBED_MODEL is not None:
        return _EMBED_MODEL
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore

        _EMBED_MODEL = SentenceTransformer(_EMBED_MODEL_NAME, device="cpu")
        return _EMBED_MODEL
    except Exception as exc:  # noqa: BLE001
        log.warning("Semantic cache: embedding model unavailable: %s", exc)
        return None


def _embed(text: str) -> "np.ndarray | None":
    model = _load_embed_model()
    if model is None:
        return None
    try:
        import numpy as np  # noqa: PLC0415

        vec: np.ndarray = model.encode(
            [text],
            convert_to_numpy=True,
            show_progress_bar=False,
            device="cpu",
        )[0].astype("float32")
        return vec
    except Exception as exc:  # noqa: BLE001
        log.warning("Semantic cache: embed error: %s", exc)
        return None


def _cosine(a: "np.ndarray", b: "np.ndarray") -> float:
    import numpy as np  # noqa: PLC0415

    na, nb = float(np.linalg.norm(a)), float(np.linalg.norm(b))
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def _normalize_prompt(prompt: str) -> str:
    return " ".join(prompt.lower().split())


def _hash_prompt(prompt: str) -> str:
    return hashlib.sha256(_normalize_prompt(prompt).encode("utf-8")).hexdigest()


def _vec_to_blob(vec: "np.ndarray") -> bytes:
    return vec.astype("float32").tobytes()


def _blob_to_vec(blob: bytes) -> "np.ndarray":
    import numpy as np  # noqa: PLC0415

    return np.frombuffer(blob, dtype="float32")


# ---------------------------------------------------------------------------
# Cache lookup
# ---------------------------------------------------------------------------


def cache_lookup(
    prompt: str,
    *,
    model: str,
    temperature: float,
    threshold: float = 0.95,
    max_age_days: int = 30,
    db_path: Path | None = None,
) -> str | None:
    """Return a cached response or None if not found.

    First tries exact SHA-256 hash match, then cosine similarity.
    """
    conn = _get_conn(db_path)
    try:
        ph = _hash_prompt(prompt)
        cutoff = int(time.time()) - max_age_days * 86400

        # Layer 1 — exact hash
        row = conn.execute(
            "SELECT response FROM llm_cache WHERE prompt_hash=? AND model=? AND created_at>=?",
            (ph, model, cutoff),
        ).fetchone()
        if row:
            log.debug("Semantic cache: exact hit")
            return row[0]

        # Layer 2 — cosine similarity
        q_vec = _embed(prompt)
        if q_vec is None:
            return None

        rows = conn.execute(
            "SELECT prompt_vector, response FROM llm_cache WHERE model=? AND created_at>=?",
            (model, cutoff),
        ).fetchall()

        best_sim = 0.0
        best_response: str | None = None
        for vec_blob, response in rows:
            if vec_blob is None:
                continue
            v = _blob_to_vec(vec_blob)
            sim = _cosine(q_vec, v)
            if sim > best_sim:
                best_sim = sim
                best_response = response

        if best_sim >= threshold and best_response is not None:
            log.debug("Semantic cache: cosine hit (sim=%.3f)", best_sim)
            return best_response

        return None
    finally:
        conn.close()


def cache_store(
    prompt: str,
    response: str,
    *,
    model: str,
    temperature: float,
    db_path: Path | None = None,
) -> None:
    """Store a prompt → response pair in the cache."""
    conn = _get_conn(db_path)
    try:
        ph = _hash_prompt(prompt)
        vec = _embed(prompt)
        blob = _vec_to_blob(vec) if vec is not None else None
        conn.execute(
            """
            INSERT OR REPLACE INTO llm_cache
                (prompt_hash, prompt_vector, response, model, temperature, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (ph, blob, response, model, temperature, int(time.time())),
        )
        conn.commit()
    finally:
        conn.close()


def cache_purge_old(max_age_days: int = 30, db_path: Path | None = None) -> int:
    """Delete entries older than max_age_days. Returns count deleted."""
    conn = _get_conn(db_path)
    try:
        cutoff = int(time.time()) - max_age_days * 86400
        cur = conn.execute("DELETE FROM llm_cache WHERE created_at < ?", (cutoff,))
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()
