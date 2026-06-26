"""LightRAG integration — optional future layer; v1 uses KG bridge in graph_retrieve."""

from __future__ import annotations

from backend.corpus.graph_retrieve import graph_chunk_ids_for_query, lightrag_available

__all__ = ["lightrag_available", "graph_chunk_ids_for_query"]
