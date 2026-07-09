"""Local corpus — hybrid RAG ingest and retrieval."""

from backend.corpus.retrieve import corpus_available, format_hits_for_prompt, hybrid_retrieve, NOTES_RAG_SOURCE_TYPES

__all__ = ["corpus_available", "format_hits_for_prompt", "hybrid_retrieve", "NOTES_RAG_SOURCE_TYPES"]
