"""Local corpus — hybrid RAG ingest and retrieval."""

from backend.corpus.retrieve import corpus_available, format_hits_for_prompt, hybrid_retrieve

__all__ = ["corpus_available", "format_hits_for_prompt", "hybrid_retrieve"]
