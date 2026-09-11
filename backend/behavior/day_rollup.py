"""P5c: read enforcer-published data/productivity/behavior/day_rollup.json.

Study Python is a **reader** of native productive-minute rollups — not the SoftLand
brain. Missing or stale files fall back to the legacy Python scorer.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Any

from backend.paths import BEHAVIOR_DIR

log = logging.getLogger("calt.day_rollup")

_PATH = BEHAVIOR_DIR / "day_rollup.json"

# Enforcer publishes about every 15s; allow brief stalls before falling back.
DEFAULT_MAX_AGE_S = 120.0


def day_rollup_path() -> Path:
    return _PATH


def load_day_rollup(*, path: Path | None = None) -> dict[str, Any] | None:
    """Parse day_rollup.json. Returns None if missing or unreadable."""
    p = path if path is not None else _PATH
    try:
        if not p.is_file():
            return None
        raw = json.loads(p.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else None
    except Exception as exc:  # noqa: BLE001
        log.debug("load_day_rollup: %s", exc)
        return None


def _parse_updated_at(raw: str) -> datetime | None:
    s = (raw or "").strip()
    if not s:
        return None
    # Enforcer writes local wall time without tz: YYYY-MM-DDTHH:MM:SS
    try:
        if s.endswith("Z"):
            return datetime.fromisoformat(s.replace("Z", "+00:00"))
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def load_fresh_day_rollup(
    day: date | None = None,
    *,
    max_age_s: float = DEFAULT_MAX_AGE_S,
    path: Path | None = None,
    now: datetime | None = None,
) -> dict[str, Any] | None:
    """Return rollup when present, for ``day``, and not older than ``max_age_s``.

    For a past local date the enforcer mirror only holds *today*, so historical
    requests always miss and callers should keep the legacy scorer.
    """
    data = load_day_rollup(path=path)
    if not data:
        return None

    want = day or date.today()
    local_date = str(data.get("local_date") or "").strip()
    if local_date != want.isoformat():
        return None

    updated = _parse_updated_at(str(data.get("updated_at") or ""))
    if updated is None:
        return None

    # Treat naive stamps as local wall clock (matches enforcer IsoLocalNow).
    clock = now or datetime.now()
    if updated.tzinfo is not None:
        if clock.tzinfo is None:
            clock = clock.replace(tzinfo=updated.tzinfo)
        else:
            clock = clock.astimezone(updated.tzinfo)
        age = (clock - updated).total_seconds()
    else:
        if clock.tzinfo is not None:
            clock = clock.replace(tzinfo=None)
        age = (clock - updated).total_seconds()

    if age < 0:
        age = 0.0
    if age > float(max_age_s):
        return None

    try:
        mins = int(data.get("productive_minutes") or 0)
    except (TypeError, ValueError):
        return None
    if mins < 0:
        mins = 0

    try:
        secs = int(data.get("productive_seconds") or (mins * 60))
    except (TypeError, ValueError):
        secs = mins * 60
    if secs < 0:
        secs = 0

    out = dict(data)
    out["productive_minutes"] = mins
    out["productive_seconds"] = secs
    out["fresh"] = True
    out["age_s"] = age
    return out


def productive_minutes_from_rollup(
    day: date | None = None,
    *,
    max_age_s: float = DEFAULT_MAX_AGE_S,
) -> int | None:
    """Productive minutes when a fresh rollup exists; else None (use legacy)."""
    hit = load_fresh_day_rollup(day, max_age_s=max_age_s)
    if hit is None:
        return None
    return int(hit["productive_minutes"])


def productive_seconds_from_rollup(
    day: date | None = None,
    *,
    max_age_s: float = DEFAULT_MAX_AGE_S,
) -> int | None:
    """Productive seconds when a fresh rollup exists; else None (use legacy)."""
    hit = load_fresh_day_rollup(day, max_age_s=max_age_s)
    if hit is None:
        return None
    return int(hit["productive_seconds"])
