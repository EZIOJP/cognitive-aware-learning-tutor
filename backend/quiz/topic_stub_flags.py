"""Per-topic stub flags for Daily Bite C eligibility. Not derived from body text after backfill."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from backend.paths import ROOT
from backend.quiz.atomic_io import atomic_write_text
from backend.quiz.importance import _file_lock

STORE_PATH = ROOT / "data" / "quiz" / "topic_stub_flags.json"
GENERATOR_PLACEHOLDER = "TODO: fill notes"


def empty_store() -> dict[str, Any]:
    return {"schema_version": 1, "backfilled": False, "tags": {}}


def load_store(path: Path | None = None) -> dict[str, Any]:
    p = path or STORE_PATH
    if not p.is_file():
        return empty_store()
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return empty_store()
    if not isinstance(data, dict):
        return empty_store()
    data.setdefault("schema_version", 1)
    data.setdefault("backfilled", False)
    data.setdefault("tags", {})
    return data


def _save(store: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, json.dumps(store, indent=2, ensure_ascii=False) + "\n")


def is_stub(tag_id: str, store: dict[str, Any] | None = None) -> bool:
    st = store or load_store()
    row = (st.get("tags") or {}).get(tag_id)
    if row is None:
        return False
    return bool(row.get("stub"))


def set_stub(tag_id: str, stub: bool, *, path: Path | None = None, overwrite_false: bool = True) -> dict[str, Any]:
    p = path or STORE_PATH
    tid = (tag_id or "").strip()
    if not tid:
        raise ValueError("tag required")
    lock = p.with_suffix(p.suffix + ".lock")
    with _file_lock(lock):
        store = load_store(p)
        tags = store.setdefault("tags", {})
        existing = tags.get(tid) or {}
        if existing.get("stub") is False and stub and not overwrite_false:
            return existing
        now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        row = {"stub": bool(stub), "updated_at": now}
        tags[tid] = row
        _save(store, p)
        return row


def mark_real_edit(tag_id: str, *, path: Path | None = None) -> None:
    set_stub(tag_id, False, path=path, overwrite_false=True)


def body_looks_like_generator_stub(body: str) -> bool:
    text = (body or "").strip()
    return not text or text == GENERATOR_PLACEHOLDER


def backfill_from_read_cards(
    cards: list[dict[str, Any]],
    *,
    path: Path | None = None,
) -> dict[str, Any]:
    """One-shot: set stub true only for empty/placeholder bodies. Never re-derive after."""
    p = path or STORE_PATH
    lock = p.with_suffix(p.suffix + ".lock")
    with _file_lock(lock):
        store = load_store(p)
        if store.get("backfilled"):
            return store
        tags = store.setdefault("tags", {})
        now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        for card in cards:
            tid = str(card.get("tag") or "").strip()
            if not tid or tid in tags:
                continue
            body = str(card.get("body_markdown") or "")
            tags[tid] = {
                "stub": body_looks_like_generator_stub(body),
                "updated_at": now,
            }
        store["backfilled"] = True
        _save(store, p)
        return store
