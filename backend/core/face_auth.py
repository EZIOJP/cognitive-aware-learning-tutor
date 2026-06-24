"""Face auth helpers — cosine similarity for enrolled embeddings."""

from __future__ import annotations

import json
import math


def parse_embedding(raw: str | None) -> list[float] | None:
    if not raw:
        return None
    try:
        vec = json.loads(raw)
        if isinstance(vec, list) and vec and all(isinstance(x, (int, float)) for x in vec):
            return [float(x) for x in vec]
    except (json.JSONDecodeError, TypeError):
        return None
    return None


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def embedding_to_json(vec: list[float]) -> str:
    return json.dumps([round(x, 6) for x in vec])
