"""Corpus RAG stubs — full Knowledge Base package removed; Lecture Notes uses non-RAG path."""

from backend.corpus.retrieve import (
    NOTES_RAG_SOURCE_TYPES,
    corpus_available,
    format_hits_for_prompt,
    hybrid_retrieve,
)

__all__ = [
    "NOTES_RAG_SOURCE_TYPES",
    "corpus_available",
    "format_hits_for_prompt",
    "hybrid_retrieve",
]
