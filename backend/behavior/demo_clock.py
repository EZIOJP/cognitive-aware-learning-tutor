"""Demo clock — time-travel for gate demos without writing fake data.

When enabled, ``now_local()`` returns a frozen wall-clock. Gate / bible day keys
read real rows for that calendar day. Demo mode must not invent productive
minutes or mutate plan/bible/rewards.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Any

from backend.paths import ROOT
from backend.planner.service import local_tz

log = logging.getLogger("calt.demo_clock")

_STATE_PATH = ROOT / "data" / "demo_clock.json"


def _empty() -> dict[str, Any]:
    return {"enabled": False, "now_iso": None}


def _load() -> dict[str, Any]:
    if not _STATE_PATH.is_file():
        return _empty()
    try:
        raw = json.loads(_STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _empty()
    if not isinstance(raw, dict):
        return _empty()
    return {
        "enabled": bool(raw.get("enabled")),
        "now_iso": raw.get("now_iso"),
    }


def _save(data: dict[str, Any]) -> None:
    _STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _STATE_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def is_demo() -> bool:
    data = _load()
    return bool(data.get("enabled") and data.get("now_iso"))


def now_local() -> datetime:
    """Wall clock for gates — real time unless demo is on."""
    tz = local_tz()
    data = _load()
    if data.get("enabled") and data.get("now_iso"):
        try:
            raw = str(data["now_iso"]).replace("Z", "+00:00")
            dt = datetime.fromisoformat(raw)
            if dt.tzinfo is None:
                return dt.replace(tzinfo=tz)
            return dt.astimezone(tz)
        except ValueError:
            log.warning("demo_clock bad now_iso; falling back to real time")
    return datetime.now(tz)


def now_utc() -> datetime:
    from datetime import UTC

    return now_local().astimezone(UTC)


def status() -> dict[str, Any]:
    data = _load()
    real = datetime.now(local_tz())
    demo_on = bool(data.get("enabled") and data.get("now_iso"))
    demo_now = now_local() if demo_on else None
    return {
        "enabled": demo_on,
        "now_iso": demo_now.isoformat() if demo_now else None,
        "day": demo_now.date().isoformat() if demo_now else None,
        "real_now_iso": real.isoformat(),
        "real_day": real.date().isoformat(),
        "read_only": True,
        "note": (
            "Demo only shifts the clock. Productive minutes and bible/plan "
            "come from real data for that day. No writes while demo is on."
        ),
    }


def set_clock(*, enabled: bool, now_iso: str | None) -> dict[str, Any]:
    if not enabled:
        _save(_empty())
        return status()
    if not now_iso or not str(now_iso).strip():
        raise ValueError("now_iso required when enabling demo clock")
    raw = str(now_iso).strip().replace("Z", "+00:00")
    dt = datetime.fromisoformat(raw)
    tz = local_tz()
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=tz)
    else:
        dt = dt.astimezone(tz)
    _save({"enabled": True, "now_iso": dt.isoformat()})
    return status()


def clear() -> dict[str, Any]:
    _save(_empty())
    return status()


def list_real_days(db, *, user_id: int, limit: int = 24) -> list[dict[str, Any]]:
    """Calendar days that already have planner blocks and/or tracked sessions."""
    from collections import Counter

    from backend.models.planner import PlannerBlock
    from backend.models.timetable import TrackedSession
    from backend.planner.service import local_tz as ltz

    tz = ltz()
    counts: Counter[str] = Counter()
    sources: dict[str, set[str]] = {}

    def _bump(day_s: str, src: str) -> None:
        counts[day_s] += 1
        sources.setdefault(day_s, set()).add(src)

    for start, in (
        db.query(PlannerBlock.start_at)
        .filter(PlannerBlock.user_id == user_id)
        .order_by(PlannerBlock.start_at.desc())
        .limit(2000)
        .all()
    ):
        if not start:
            continue
        if start.tzinfo is None:
            local = start.replace(tzinfo=tz)
        else:
            local = start.astimezone(tz)
        _bump(local.date().isoformat(), "planner")

    for start, in (
        db.query(TrackedSession.start_time)
        .filter(TrackedSession.user_id == user_id)
        .order_by(TrackedSession.start_time.desc())
        .limit(8000)
        .all()
    ):
        if not start:
            continue
        if start.tzinfo is None:
            local = start.replace(tzinfo=tz)
        else:
            local = start.astimezone(tz)
        _bump(local.date().isoformat(), "tracked")

    out: list[dict[str, Any]] = []
    for day_s, n in counts.most_common():
        out.append(
            {
                "day": day_s,
                "events": int(n),
                "sources": sorted(sources.get(day_s) or []),
            }
        )
        if len(out) >= limit:
            break
    out.sort(key=lambda r: r["day"], reverse=True)
    return out[:limit]


def assert_not_demo_writes() -> None:
    """Call before morning confirm / auto-plan / rewards grants."""
    if is_demo():
        raise RuntimeError("Demo mode is read-only — disable demo clock before writing")
