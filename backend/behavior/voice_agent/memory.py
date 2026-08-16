"""Voice agent durable + session memory (JSON under data/voice_agent/)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.paths import ROOT

_DIR = ROOT / "data" / "voice_agent"
_MAX_TURNS = 12


def _ensure_dir() -> Path:
    _DIR.mkdir(parents=True, exist_ok=True)
    return _DIR


def session_path(user_id: int) -> Path:
    return _ensure_dir() / f"session_{int(user_id)}.json"


def memory_path(user_id: int) -> Path:
    return _ensure_dir() / f"memory_{int(user_id)}.json"


def _read(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _write(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def load_turns(user_id: int) -> list[dict[str, str]]:
    raw = _read(session_path(user_id)).get("turns") or []
    out: list[dict[str, str]] = []
    for t in raw:
        if isinstance(t, dict) and t.get("role") and t.get("content"):
            out.append({"role": str(t["role"]), "content": str(t["content"])})
    return out[-_MAX_TURNS:]


def append_turn(user_id: int, role: str, content: str) -> list[dict[str, str]]:
    turns = load_turns(user_id)
    turns.append({"role": role, "content": content.strip()})
    turns = turns[-_MAX_TURNS:]
    _write(
        session_path(user_id),
        {"turns": turns, "updated_at": datetime.now(timezone.utc).isoformat()},
    )
    return turns


def load_facts(user_id: int) -> dict[str, str]:
    raw = _read(memory_path(user_id)).get("facts") or {}
    if not isinstance(raw, dict):
        return {}
    return {str(k): str(v) for k, v in raw.items() if str(k).strip()}


def memory_get(user_id: int, key: str | None = None) -> str:
    facts = load_facts(user_id)
    if key:
        return facts.get(key, "")
    if not facts:
        return "(empty)"
    return "\n".join(f"{k}: {v}" for k, v in sorted(facts.items()))


def memory_set(user_id: int, key: str, value: str) -> str:
    key = (key or "").strip()
    if not key:
        return "error: empty key"
    facts = load_facts(user_id)
    facts[key] = (value or "").strip()
    _write(
        memory_path(user_id),
        {"facts": facts, "updated_at": datetime.now(timezone.utc).isoformat()},
    )
    return f"saved {key}"
