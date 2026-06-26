"""Golden-set retrieval benchmark."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.corpus.retrieve import hybrid_retrieve


def run_benchmark(golden_path: Path, *, top_k: int = 5) -> dict[str, Any]:
    items = json.loads(golden_path.read_text(encoding="utf-8"))
    hits_total = 0
    queries = 0
    details: list[dict[str, Any]] = []

    for item in items:
        query = item["query"]
        expected = set(item.get("expected_chunk_ids") or [])
        expected_subjects = item.get("subject_tags")
        hits = hybrid_retrieve(query, subject_tags=expected_subjects, top_k=top_k)
        got = {h["chunk_id"] for h in hits}
        overlap = len(expected & got) if expected else int(bool(hits))
        hits_total += overlap
        queries += 1
        details.append({
            "query": query,
            "expected": list(expected),
            "retrieved": [h["chunk_id"] for h in hits],
            "overlap": overlap,
        })

    recall_at_k = hits_total / max(1, sum(len(i.get("expected_chunk_ids") or [1]) for i in items))
    misses = [d for d in details if d["overlap"] == 0 and d.get("expected")]
    return {
        "queries": queries,
        "recall_at_k": round(recall_at_k, 4),
        "top_k": top_k,
        "details": details,
        "misses": misses,
    }
