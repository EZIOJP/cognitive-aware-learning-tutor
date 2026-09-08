"""Require daily Study Loop (bite) after morning plan — SoftLand next=study.

File store so it can be flipped without a migration. Default OFF (paused).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.paths import ROOT
from backend.quiz.atomic_io import atomic_write_text
from backend.quiz.importance import _file_lock

STORE_PATH = ROOT / "data" / "quiz" / "study_loop_gate.json"
# User asked to pause SoftLand study forcing — default off until re-enabled.
DEFAULT_ENABLED = False


def empty_store() -> dict[str, Any]:
    return {"schema_version": 1, "enabled": DEFAULT_ENABLED}


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
    if "enabled" not in data:
        data["enabled"] = DEFAULT_ENABLED
    return data


def is_required(*, path: Path | None = None) -> bool:
    """True when unfinished daily bite should force morning.next=study."""
    return bool(load_store(path).get("enabled"))


def set_enabled(enabled: bool, *, path: Path | None = None) -> dict[str, Any]:
    p = path or STORE_PATH
    lock = p.with_suffix(p.suffix + ".lock")
    with _file_lock(lock):
        store = load_store(p)
        store["enabled"] = bool(enabled)
        store["schema_version"] = 1
        p.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(p, json.dumps(store, indent=2, ensure_ascii=False) + "\n")
        return {"enabled": bool(store["enabled"])}


def serialize(*, path: Path | None = None) -> dict[str, Any]:
    st = load_store(path)
    return {
        "enabled": bool(st.get("enabled")),
        "default_enabled": DEFAULT_ENABLED,
        "path": str(STORE_PATH.as_posix()),
    }
