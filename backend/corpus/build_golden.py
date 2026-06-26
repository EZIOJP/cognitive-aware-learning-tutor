"""Build or refresh golden Q&A fixture from live hybrid retrieval."""

from __future__ import annotations

import json
from pathlib import Path

from backend.corpus.paths import ROOT
from backend.corpus.retrieve import hybrid_retrieve

DEFAULT_FIXTURE = ROOT / "tests" / "fixtures" / "mml_golden_qa.json"

DEFAULT_QUERIES = [
    {
        "query": "What is an eigenvalue?",
        "subject_tags": ["linear_algebra"],
    },
    {
        "query": "matrix vector product linear transformation",
        "subject_tags": ["linear_algebra"],
    },
    {
        "query": "numpy array indexing",
        "subject_tags": ["lecture"],
    },
    {
        "query": "Gaussian elimination systems of equations",
        "subject_tags": ["linear_algebra"],
    },
]


def build_golden_fixture(
    *,
    fixture_path: Path | None = None,
    top_k: int = 5,
) -> dict:
    path = fixture_path or DEFAULT_FIXTURE
    items = []
    for entry in DEFAULT_QUERIES:
        hits = hybrid_retrieve(
            entry["query"],
            subject_tags=entry.get("subject_tags"),
            top_k=top_k,
        )
        expected = [h["chunk_id"] for h in hits[:3]]
        items.append(
            {
                "query": entry["query"],
                "subject_tags": entry.get("subject_tags") or [],
                "expected_chunk_ids": expected,
            }
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(items, indent=2) + "\n", encoding="utf-8")
    return {"fixture": str(path), "items": len(items), "queries": items}


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description="Refresh mml_golden_qa.json from corpus retrieval")
    p.add_argument("--fixture", default=str(DEFAULT_FIXTURE))
    p.add_argument("--top-k", type=int, default=5)
    args = p.parse_args()
    report = build_golden_fixture(fixture_path=Path(args.fixture), top_k=args.top_k)
    print(json.dumps(report, indent=2))
