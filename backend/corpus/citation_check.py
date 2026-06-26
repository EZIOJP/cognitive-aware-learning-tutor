"""Verify quiz/drill citations resolve to corpus chunks."""

from __future__ import annotations

from typing import Any

from backend.corpus.registry import get_chunk


def verify_quiz_citations(
    questions: list[dict[str, Any]],
    allowed_chunk_ids: set[str] | None = None,
) -> dict[str, Any]:
    missing: list[str] = []
    invalid: list[str] = []
    for q in questions:
        cid = str(q.get("source_chunk_id") or "").strip()
        if not cid:
            continue
        if allowed_chunk_ids is not None and cid not in allowed_chunk_ids:
            invalid.append(cid)
            q["source_chunk_id"] = ""
            q["citation"] = ""
            continue
        if get_chunk(cid) is None:
            missing.append(cid)
            q["source_chunk_id"] = ""
            q["citation"] = ""
    return {"missing": missing, "invalid": invalid, "checked": len(questions)}
