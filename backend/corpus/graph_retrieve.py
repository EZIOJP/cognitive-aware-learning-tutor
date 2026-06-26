"""KG graph traversal retrieval — LightRAG bridge / fallback."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

log = logging.getLogger(__name__)

_LIGHTRAG_AVAILABLE: bool | None = None


def lightrag_available() -> bool:
    """Spike: LightRAG package not required for v1 — KG traverse is the bridge."""
    global _LIGHTRAG_AVAILABLE  # noqa: PLW0603
    if _LIGHTRAG_AVAILABLE is None:
        try:
            import importlib.util

            _LIGHTRAG_AVAILABLE = importlib.util.find_spec("lightrag") is not None
        except Exception:  # noqa: BLE001
            _LIGHTRAG_AVAILABLE = False
    return _LIGHTRAG_AVAILABLE


def graph_chunk_ids_for_query(
    db: Session,
    query: str,
    *,
    user_id: int | None = None,
    top_k: int = 5,
) -> list[str]:
    """Traverse KG from query-matched concept nodes; map chunk nodes to registry ids."""
    from backend.hub.services.knowledge_graph import find_nodes_by_query, find_related_nodes
    from backend.models.knowledge_graph import KgNode

    top_nodes = find_nodes_by_query(db, query, user_id=user_id, top_k=top_k)
    chunk_ids: list[str] = []
    seen: set[str] = set()

    for node, _score in top_nodes:
        if node.node_type == "chunk":
            meta = node.metadata_json or ""
            import json

            try:
                data = json.loads(meta) if meta else {}
            except json.JSONDecodeError:
                data = {}
            cid = data.get("chunk_id")
            if cid and cid not in seen:
                seen.add(cid)
                chunk_ids.append(cid)
        for related in find_related_nodes(db, node.id, hops=2):
            if related.node_type != "chunk":
                continue
            import json

            try:
                data = json.loads(related.metadata_json or "{}")
            except json.JSONDecodeError:
                data = {}
            cid = data.get("chunk_id")
            if cid and cid not in seen:
                seen.add(cid)
                chunk_ids.append(cid)

    # Also match concept labels in query for MML seeds
    if len(chunk_ids) < top_k:
        q = query.lower()
        concepts = (
            db.query(KgNode)
            .filter(KgNode.node_type == "concept")
            .limit(200)
            .all()
        )
        for c in concepts:
            tag = (c.tag_path or c.label or "").lower()
            if tag and any(w in q for w in tag.split() if len(w) > 4):
                for related in find_related_nodes(db, c.id, hops=1):
                    if related.node_type != "chunk":
                        continue
                    import json

                    try:
                        data = json.loads(related.metadata_json or "{}")
                    except json.JSONDecodeError:
                        data = {}
                    cid = data.get("chunk_id")
                    if cid and cid not in seen:
                        seen.add(cid)
                        chunk_ids.append(cid)
            if len(chunk_ids) >= top_k:
                break

    return chunk_ids[:top_k]


def merge_graph_hits(
    base_hits: list[dict[str, Any]],
    graph_hits: list[dict[str, Any]],
    *,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    seen = {h["chunk_id"] for h in base_hits}
    merged = list(base_hits)
    for h in graph_hits:
        if h["chunk_id"] in seen:
            continue
        merged.append(h)
        seen.add(h["chunk_id"])
        if len(merged) >= top_k:
            break
    return merged[:top_k]
