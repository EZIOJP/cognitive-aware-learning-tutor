"""No-op corpus retrieve stubs (RAG package removed)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

NOTES_RAG_SOURCE_TYPES = ("textbook",)


def corpus_available(*, db_path: Path | None = None) -> bool:
    """Always False — corpus / Knowledge Base was removed."""
    return False


def hybrid_retrieve(
    query: str,
    *,
    top_k: int = 8,
    source_types: list[str] | None = None,
    subject_tags: list[str] | None = None,
    db_path: Path | None = None,
) -> list[dict[str, Any]]:
    return []


def format_hits_for_prompt(hits: list[dict[str, Any]], *, max_chars: int = 12000) -> str:
    if not hits:
        return ""
    parts: list[str] = []
    for h in hits:
        cite = str(h.get("citation") or h.get("source_title") or h.get("chunk_id") or "")
        body = str(h.get("raw_payload") or h.get("text") or "")
        if cite or body:
            parts.append(f"{cite}\n{body}".strip())
    text = "\n\n".join(parts)
    return text[:max_chars] if text else ""


def chunk_to_hit(c: Any) -> dict[str, Any]:
    return {}
