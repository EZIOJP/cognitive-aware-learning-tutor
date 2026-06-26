"""Textbook concept nodes and lecture alignment."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

log = logging.getLogger(__name__)

MML_CONCEPT_SEEDS: dict[int, list[tuple[str, str]]] = {
    1: [
        ("mml.ch1.learning_objectives", "What ML needs from math"),
        ("mml.ch1.data_vs_knowledge", "Data as observations vs models as knowledge"),
        ("mml.ch1.vector_representation", "Features as vectors"),
        ("mml.ch1.systems_of_equations", "Systems of equations preview"),
    ],
    2: [
        ("mml.ch2.vectors_spaces", "Vectors and vector spaces"),
        ("mml.ch2.linear_combinations", "Linear combinations and basis"),
        ("mml.ch2.matrices", "Matrices and matrix-vector product"),
        ("mml.ch2.linear_transformations", "Linear transformations"),
        ("mml.ch2.systems_linear_equations", "Systems of linear equations Ax=b"),
        ("mml.ch2.gaussian_elimination", "Gaussian elimination"),
        ("mml.ch2.vector_spaces", "Subspaces and rank"),
        ("mml.ch2.determinants", "Determinants"),
        ("mml.ch2.eigenvalues_eigenvectors", "Eigenvalues and eigenvectors"),
        ("mml.ch2.orthogonality", "Inner products and orthogonality"),
    ],
}


def seed_mml_concepts(
    db: Session,
    *,
    user_id: int | None,
    chapters: list[int],
    document_id: str = "mml_2021_deisenroth",
) -> list[int]:
    from backend.hub.services.knowledge_graph import add_edge, upsert_node  # noqa: PLC0415

    created: list[int] = []
    book_node = upsert_node(
        db,
        user_id=user_id,
        label=document_id,
        node_type="textbook",
        metadata={"title": "Mathematics for Machine Learning"},
    )
    created.append(book_node.id)

    prev_chapter_id: int | None = None
    for ch in chapters:
        ch_label = f"{document_id}.chapter_{ch}"
        ch_node = upsert_node(
            db,
            user_id=user_id,
            label=ch_label,
            node_type="chapter",
            metadata={"chapter": ch},
        )
        add_edge(db, source_id=book_node.id, target_id=ch_node.id, relation_type="contains")
        if prev_chapter_id is not None:
            add_edge(
                db,
                source_id=prev_chapter_id,
                target_id=ch_node.id,
                relation_type="temporal_next",
            )
        prev_chapter_id = ch_node.id
        created.append(ch_node.id)

        for concept_id, title in MML_CONCEPT_SEEDS.get(ch, []):
            concept = upsert_node(
                db,
                user_id=user_id,
                label=concept_id,
                node_type="concept",
                tag_path=title,
                metadata={"chapter": ch, "document_id": document_id},
            )
            add_edge(db, source_id=ch_node.id, target_id=concept.id, relation_type="contains")
            created.append(concept.id)
    return created


def align_lecture_chunk_to_concepts(
    db: Session,
    *,
    user_id: int | None,
    chunk_id: str,
    chunk_text: str,
    concept_labels: list[str],
) -> list[dict[str, Any]]:
    """Create aligns_with edges from lecture chunk to textbook concepts (by label match in text)."""
    from backend.hub.services.knowledge_graph import add_edge, upsert_node  # noqa: PLC0415
    from backend.models.knowledge_graph import KgNode  # noqa: PLC0415

    lower = chunk_text.lower()
    linked: list[dict[str, Any]] = []
    chunk_node = upsert_node(
        db,
        user_id=user_id,
        label=f"chunk:{chunk_id}",
        node_type="chunk",
        metadata={"chunk_id": chunk_id},
    )
    for label in concept_labels:
        node = (
            db.query(KgNode)
            .filter(KgNode.user_id == user_id, KgNode.label == label)
            .first()
        )
        if node is None:
            continue
        tag = (node.tag_path or node.label or "").lower()
        keywords = [w for w in tag.replace("_", " ").split() if len(w) > 3]
        if not keywords:
            continue
        if any(kw in lower for kw in keywords):
            add_edge(
                db,
                source_id=chunk_node.id,
                target_id=node.id,
                relation_type="aligns_with",
            )
            linked.append({"chunk_id": chunk_id, "concept": label})
    return linked


def extract_equation_nodes(
    db: Session,
    *,
    user_id: int | None,
    chapter: int,
    markdown: str,
    document_id: str = "mml_2021_deisenroth",
    max_sections: int = 4,
) -> list[int]:
    """Optional LLM pass: extract equation/definition nodes from a chapter markdown slice."""
    from backend.core.ollama_client import ollama_available, ollama_generate  # noqa: PLC0415
    from backend.hub.services.knowledge_graph import add_edge, upsert_node  # noqa: PLC0415
    from backend.models.knowledge_graph import KgNode  # noqa: PLC0415

    if not ollama_available() or not markdown.strip():
        return []

    ch_label = f"{document_id}.chapter_{chapter}"
    ch_node = (
        db.query(KgNode)
        .filter(KgNode.user_id == user_id, KgNode.label == ch_label)
        .first()
    )
    if ch_node is None:
        return []

    sample = markdown[:6000]
    prompt = f"""From this textbook chapter excerpt, list up to {max_sections} distinct equations or formal definitions.
Return JSON only: {{"items": [{{"label": "mml.ch{chapter}.eq_name", "title": "short name", "latex_or_text": "..."}}]}}

CHAPTER {chapter} EXCERPT:
{sample}"""

    raw = ollama_generate(prompt, timeout=90.0)
    if not raw:
        return []

    import json
    import re

    match = re.search(r"\{[\s\S]*\}", raw)
    if not match:
        return []
    try:
        data = json.loads(match.group())
    except json.JSONDecodeError:
        return []

    created: list[int] = []
    for item in (data.get("items") or [])[:max_sections]:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or "").strip()
        if not label:
            continue
        eq_node = upsert_node(
            db,
            user_id=user_id,
            label=label,
            node_type="equation",
            tag_path=str(item.get("title") or label)[:200],
            metadata={
                "chapter": chapter,
                "document_id": document_id,
                "latex_or_text": str(item.get("latex_or_text") or "")[:500],
            },
        )
        add_edge(db, source_id=ch_node.id, target_id=eq_node.id, relation_type="has_equation")
        created.append(eq_node.id)
    if created:
        db.commit()
    return created
