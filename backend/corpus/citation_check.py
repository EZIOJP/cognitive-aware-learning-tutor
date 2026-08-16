"""Citation check stubs — no corpus registry."""

from __future__ import annotations

from typing import Any


def verify_quiz_citations(
    questions: list[dict[str, Any]],
    allowed_chunk_ids: set[str] | None = None,
) -> dict[str, Any]:
    return {"missing": [], "invalid": [], "checked": len(questions or [])}
