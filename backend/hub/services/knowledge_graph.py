"""Knowledge graph service layer.

Provides CRUD helpers for kg_nodes, kg_edges, kg_embeddings, and kg_observations.
Embeddings are stored as raw float32 numpy arrays serialized to bytes.
All heavy computation (embedding) runs on CPU.
"""

from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from sqlalchemy.orm import Session

from backend.models.knowledge_graph import KgEdge, KgEmbedding, KgNode, KgObservation

if TYPE_CHECKING:
    pass

log = logging.getLogger(__name__)

_EMBEDDING_MODEL = None
_EMBED_MODEL_NAME = "all-MiniLM-L6-v2"


def _get_embed_model():
    global _EMBEDDING_MODEL
    if _EMBEDDING_MODEL is not None:
        return _EMBEDDING_MODEL
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore

        _EMBEDDING_MODEL = SentenceTransformer(_EMBED_MODEL_NAME, device="cpu")
        log.info("KG embedding model loaded.")
        return _EMBEDDING_MODEL
    except Exception as exc:  # noqa: BLE001
        log.warning("Could not load embedding model for KG: %s", exc)
        return None


def _embed_text(text: str) -> np.ndarray | None:
    model = _get_embed_model()
    if model is None:
        return None
    try:
        vec: np.ndarray = model.encode(
            [text],
            convert_to_numpy=True,
            show_progress_bar=False,
            device="cpu",
        )[0].astype("float32")
        return vec
    except Exception as exc:  # noqa: BLE001
        log.warning("Embedding failed: %s", exc)
        return None


def _vec_to_blob(vec: np.ndarray) -> bytes:
    return vec.astype("float32").tobytes()


def _blob_to_vec(blob: bytes) -> np.ndarray:
    return np.frombuffer(blob, dtype="float32")


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    na, nb = float(np.linalg.norm(a)), float(np.linalg.norm(b))
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


# ---------------------------------------------------------------------------
# Node operations
# ---------------------------------------------------------------------------


def upsert_node(
    db: Session,
    *,
    user_id: int | None,
    label: str,
    node_type: str = "concept",
    tag_path: str | None = None,
    note_path: str | None = None,
    metadata: dict | None = None,
) -> KgNode:
    """Insert or update a knowledge graph node."""
    node = (
        db.query(KgNode)
        .filter(KgNode.user_id == user_id, KgNode.label == label)
        .first()
    )
    if node is None:
        node = KgNode(
            user_id=user_id,
            label=label,
            node_type=node_type,
            tag_path=tag_path,
            note_path=note_path,
            metadata_json=json.dumps(metadata) if metadata else None,
            created_at=int(time.time()),
        )
        db.add(node)
        db.flush()
    else:
        if tag_path is not None:
            node.tag_path = tag_path
        if note_path is not None:
            node.note_path = note_path
        if metadata:
            node.metadata_json = json.dumps(metadata)
    db.commit()
    db.refresh(node)
    return node


def add_edge(
    db: Session,
    *,
    source_id: int,
    target_id: int,
    relation_type: str = "temporal_next",
    weight: float = 1.0,
) -> KgEdge:
    """Add an edge between two nodes. Idempotent on (source, target, relation)."""
    existing = (
        db.query(KgEdge)
        .filter(
            KgEdge.source_id == source_id,
            KgEdge.target_id == target_id,
            KgEdge.relation_type == relation_type,
        )
        .first()
    )
    if existing:
        return existing
    edge = KgEdge(source_id=source_id, target_id=target_id, relation_type=relation_type, weight=weight)
    db.add(edge)
    db.commit()
    db.refresh(edge)
    return edge


def store_embedding(db: Session, *, node_id: int, vector: np.ndarray) -> None:
    """Upsert the embedding blob for a node."""
    emb = db.query(KgEmbedding).filter(KgEmbedding.node_id == node_id).first()
    blob = _vec_to_blob(vector)
    if emb is None:
        emb = KgEmbedding(node_id=node_id, vector_blob=blob, model_name=_EMBED_MODEL_NAME)
        db.add(emb)
    else:
        emb.vector_blob = blob
        emb.model_name = _EMBED_MODEL_NAME
    db.commit()


def log_observation(
    db: Session,
    *,
    node_id: int,
    user_id: int | None,
    interaction_type: str,
    value: float = 0.0,
) -> KgObservation:
    obs = KgObservation(
        node_id=node_id,
        user_id=user_id,
        timestamp=int(time.time()),
        interaction_type=interaction_type,
        value=value,
    )
    db.add(obs)
    db.commit()
    db.refresh(obs)
    return obs


def find_related_nodes(db: Session, node_id: int, hops: int = 2) -> list[KgNode]:
    """BFS traversal following all edge types up to `hops` levels."""
    visited: set[int] = {node_id}
    queue: list[int] = [node_id]
    result: list[KgNode] = []

    for _ in range(hops):
        next_queue: list[int] = []
        for nid in queue:
            edges = db.query(KgEdge).filter(
                (KgEdge.source_id == nid) | (KgEdge.target_id == nid)
            ).all()
            for edge in edges:
                neighbour = edge.target_id if edge.source_id == nid else edge.source_id
                if neighbour not in visited:
                    visited.add(neighbour)
                    next_queue.append(neighbour)
                    node = db.query(KgNode).filter(KgNode.id == neighbour).first()
                    if node:
                        result.append(node)
        queue = next_queue

    return result


# ---------------------------------------------------------------------------
# Semantic node lookup (GraphRAG step 1)
# ---------------------------------------------------------------------------


def find_nodes_by_query(
    db: Session,
    query: str,
    user_id: int | None,
    top_k: int = 3,
) -> list[tuple[KgNode, float]]:
    """Embed query and return top-k nodes by cosine similarity."""
    q_vec = _embed_text(query)
    if q_vec is None:
        return []

    embeddings = db.query(KgEmbedding).all()
    scored: list[tuple[KgNode, float]] = []
    for emb in embeddings:
        if emb.vector_blob is None:
            continue
        node = db.query(KgNode).filter(KgNode.id == emb.node_id).first()
        if node is None:
            continue
        if user_id is not None and node.user_id not in (user_id, None):
            continue
        v = _blob_to_vec(emb.vector_blob)
        sim = _cosine(q_vec, v)
        scored.append((node, sim))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_k]


# ---------------------------------------------------------------------------
# Note indexing — parse markdown headings → nodes + edges
# ---------------------------------------------------------------------------

_H2_RE = re.compile(r"^##\s+(.+)$", re.MULTILINE)
_H3_RE = re.compile(r"^###\s+(.+)$", re.MULTILINE)


def index_note_file(
    db: Session,
    note_path: Path,
    user_id: int | None = None,
) -> list[KgNode]:
    """Parse a markdown note and upsert kg_nodes for every ## heading.

    Adds temporal_next edges between sequential headings and stores embeddings.
    Returns the list of upserted nodes.
    """
    if not note_path.is_file():
        log.warning("index_note_file: file not found: %s", note_path)
        return []

    content = note_path.read_text(encoding="utf-8")
    headings = _H2_RE.findall(content)
    if not headings:
        log.info("index_note_file: no ## headings found in %s", note_path)
        return []

    rel_path = str(note_path)
    nodes: list[KgNode] = []

    for i, heading in enumerate(headings):
        heading = heading.strip()
        node = upsert_node(
            db,
            user_id=user_id,
            label=heading,
            node_type="concept",
            note_path=rel_path,
        )
        nodes.append(node)

        # Store embedding
        vec = _embed_text(heading)
        if vec is not None:
            store_embedding(db, node_id=node.id, vector=vec)

    # Add temporal_next edges between sequential nodes
    for i in range(len(nodes) - 1):
        add_edge(
            db,
            source_id=nodes[i].id,
            target_id=nodes[i + 1].id,
            relation_type="temporal_next",
        )

    log.info("Indexed %d nodes from %s", len(nodes), note_path.name)
    return nodes
