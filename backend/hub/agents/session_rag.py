"""Ephemeral session-scoped document RAG (upload PDF for this chat only)."""

from __future__ import annotations

import re
import threading
import time
from dataclasses import dataclass, field

_SESSION_TTL_SEC = 3600.0
_LOCK = threading.Lock()
_STORE: dict[str, "_SessionDoc"] = {}


@dataclass
class _SessionDoc:
    chunks: list[str] = field(default_factory=list)
    filename: str = ""
    created_at: float = field(default_factory=time.time)


def _cleanup_expired() -> None:
    now = time.time()
    expired = [sid for sid, doc in _STORE.items() if now - doc.created_at > _SESSION_TTL_SEC]
    for sid in expired:
        _STORE.pop(sid, None)


def _split_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + chunk_size)
        chunks.append(text[start:end])
        if end >= len(text):
            break
        start = max(0, end - overlap)
    return chunks


def _extract_pdf_bytes(data: bytes) -> str:
    try:
        from pypdf import PdfReader
        from io import BytesIO

        reader = PdfReader(BytesIO(data))
        parts: list[str] = []
        for page in reader.pages[:80]:
            parts.append(page.extract_text() or "")
        return "\n".join(parts)
    except Exception:
        return ""


def ingest_upload(session_id: str, filename: str, data: bytes, content_type: str) -> int:
    """Store upload chunks for session. Returns chunk count."""
    if content_type.startswith("text/"):
        text = data.decode("utf-8", errors="replace")
    elif content_type == "application/pdf" or filename.lower().endswith(".pdf"):
        text = _extract_pdf_bytes(data)
    else:
        text = data.decode("utf-8", errors="replace")

    chunks = _split_text(text)
    with _LOCK:
        _cleanup_expired()
        _STORE[session_id] = _SessionDoc(chunks=chunks, filename=filename)
    return len(chunks)


def _score_chunk(query: str, chunk: str) -> int:
    q_tokens = {t for t in re.findall(r"[a-z0-9]{3,}", query.lower())}
    if not q_tokens:
        return 0
    lower = chunk.lower()
    return sum(1 for t in q_tokens if t in lower)


def retrieve(session_id: str, query: str, top_k: int = 5) -> list[str]:
    with _LOCK:
        doc = _STORE.get(session_id)
    if not doc or not doc.chunks:
        return []
    ranked = sorted(doc.chunks, key=lambda c: _score_chunk(query, c), reverse=True)
    return [c for c in ranked[:top_k] if _score_chunk(query, c) > 0] or ranked[:top_k]


def session_filename(session_id: str) -> str | None:
    with _LOCK:
        doc = _STORE.get(session_id)
    return doc.filename if doc else None


def clear_session(session_id: str) -> None:
    with _LOCK:
        _STORE.pop(session_id, None)
