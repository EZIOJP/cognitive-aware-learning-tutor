from __future__ import annotations

from typing import Any

CURATED_FIELDS = ("answer", "solution_steps", "hint", "explanation")


def _is_nonempty(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict, tuple, set)):
        return len(value) > 0
    return True


def merge_question(existing: dict | None, incoming: dict) -> dict:
    """Fill-empty-only merge keyed by caller via (source, source_id)."""
    if not existing:
        return dict(incoming)
    out = dict(incoming)
    for key in ("id", "source", "source_id"):
        if _is_nonempty(existing.get(key)):
            out[key] = existing[key]
    for field in CURATED_FIELDS:
        if _is_nonempty(existing.get(field)):
            out[field] = existing[field]
        elif field not in out or not _is_nonempty(out.get(field)):
            if field in existing:
                out[field] = existing[field]
    # Preserve existing free tags; incoming may add later in map step
    ex_tags = existing.get("tags")
    in_tags = incoming.get("tags")
    if isinstance(ex_tags, list) or isinstance(in_tags, list):
        merged: list[str] = []
        for t in list(ex_tags or []) + list(in_tags or []):
            s = str(t)
            if s and s not in merged:
                merged.append(s)
        out["tags"] = merged
    return out
