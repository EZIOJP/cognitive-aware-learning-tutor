"""Temporary study-mode nudge after distraction alerts."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from backend.paths import ROOT

_NUDGE_PATH = ROOT / "data" / "behavior" / "study_mode_nudge.json"
_DEFAULT_MIN = 90


def study_nudge_until(*, path: Path | None = None) -> datetime | None:
    store = path if path is not None else _NUDGE_PATH
    try:
        if not store.is_file():
            return None
        raw = json.loads(store.read_text(encoding="utf-8"))
        until_s = raw.get("until") if isinstance(raw, dict) else None
        if not until_s:
            return None
        until = datetime.fromisoformat(str(until_s))
        if until.tzinfo is None:
            until = until.replace(tzinfo=timezone.utc)
        if until <= datetime.now(timezone.utc):
            try:
                store.unlink()
            except OSError:
                pass
            return None
        return until
    except Exception:
        return None


def study_nudge_active(*, now: datetime | None = None) -> bool:
    _ = now
    return study_nudge_until() is not None


def arm_study_mode_nudge(
    *,
    minutes: int | None = None,
    reason: str = "",
    path: Path | None = None,
) -> dict[str, Any]:
    """Force study browser mode for N minutes (clears free override)."""
    from backend.behavior.browser_gate_policy import clear_free_override

    clear_free_override()
    mins = minutes if minutes is not None else int(
        os.environ.get("STUDY_MODE_NUDGE_MINUTES") or _DEFAULT_MIN
    )
    mins = max(15, min(mins, 8 * 60))
    dt = datetime.now(timezone.utc)
    until = dt + timedelta(minutes=mins)
    store = path if path is not None else _NUDGE_PATH
    payload = {
        "until": until.isoformat(),
        "minutes": mins,
        "reason": (reason or "")[:120],
        "armed_at": dt.isoformat(),
    }
    store.parent.mkdir(parents=True, exist_ok=True)
    store.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def clear_study_mode_nudge(*, path: Path | None = None) -> None:
    store = path if path is not None else _NUDGE_PATH
    try:
        if store.is_file():
            store.unlink()
    except OSError:
        pass
