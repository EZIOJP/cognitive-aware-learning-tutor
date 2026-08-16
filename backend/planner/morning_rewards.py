"""Minimal morning unlock rewards — Bible +10, Plan +10 per local day."""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

from backend.paths import ROOT
from backend.planner.service import local_tz

_STORE = ROOT / "data" / "morning_rewards.json"

BIBLE_POINTS = 10
PLAN_POINTS = 10

AWARDS = {
    "bible": {"points": BIBLE_POINTS, "label": "Bible +10"},
    "plan": {"points": PLAN_POINTS, "label": "Plan +10"},
}


def _path() -> Path:
    _STORE.parent.mkdir(parents=True, exist_ok=True)
    return _STORE


def _load() -> dict[str, Any]:
    p = _path()
    if not p.is_file():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _save(data: dict[str, Any]) -> None:
    _path().write_text(json.dumps(data, indent=2), encoding="utf-8")


def _key(user_id: int, day: date | None = None) -> str:
    d = day or datetime.now(local_tz()).date()
    return f"{int(user_id)}:{d.isoformat()}"


def _empty_day(user_id: int, day: date) -> dict[str, Any]:
    return {
        "day": day.isoformat(),
        "user_id": int(user_id),
        "awards": {},
        "total_points": 0,
    }


def _day_record(user_id: int, day: date | None = None) -> dict[str, Any]:
    d = day or datetime.now(local_tz()).date()
    data = _load()
    raw = data.get(_key(user_id, d))
    if not isinstance(raw, dict):
        return _empty_day(user_id, d)
    awards = raw.get("awards") if isinstance(raw.get("awards"), dict) else {}
    return {
        "day": d.isoformat(),
        "user_id": int(user_id),
        "awards": dict(awards),
        "total_points": int(raw.get("total_points") or 0),
    }


def _write_day(user_id: int, day: date, record: dict[str, Any]) -> None:
    data = _load()
    k = _key(user_id, day)
    data[k] = record
    # Prune older than ~14 days for this user
    prefix = f"{int(user_id)}:"
    keep: dict[str, Any] = {}
    for key, val in data.items():
        if not key.startswith(prefix):
            keep[key] = val
            continue
        try:
            dd = date.fromisoformat(key.split(":", 1)[1])
        except ValueError:
            continue
        if (day - dd).days <= 14:
            keep[key] = val
    keep[k] = record
    _save(keep)


def grant(user_id: int, kind: str, day: date | None = None) -> dict[str, Any]:
    """Grant a fixed morning award once per day. Idempotent."""
    try:
        from backend.behavior.demo_clock import assert_not_demo_writes

        assert_not_demo_writes()
    except RuntimeError:
        d = day or datetime.now(local_tz()).date()
        return summary(user_id, d)
    except Exception:
        pass
    kind = (kind or "").strip().lower()
    if kind not in AWARDS:
        raise ValueError(f"unknown award kind: {kind}")
    d = day or datetime.now(local_tz()).date()
    rec = _day_record(user_id, d)
    awards = rec["awards"]
    if kind in awards and awards[kind].get("granted"):
        return summary(user_id, d)
    meta = AWARDS[kind]
    awards[kind] = {
        "granted": True,
        "points": int(meta["points"]),
        "label": meta["label"],
        "granted_at": datetime.now(local_tz()).isoformat(),
    }
    rec["awards"] = awards
    rec["total_points"] = sum(
        int(a.get("points") or 0) for a in awards.values() if a.get("granted")
    )
    _write_day(user_id, d, rec)
    return summary(user_id, d)


def maybe_grant_bible(user_id: int) -> dict[str, Any]:
    """If today's chapter goal is met, grant Bible reward (once)."""
    from backend.bible import store as bible_store

    if bible_store.chapter_goal_met(user_id):
        return grant(user_id, "bible")
    return summary(user_id)


def grant_plan(user_id: int) -> dict[str, Any]:
    return grant(user_id, "plan")


def summary(user_id: int, day: date | None = None) -> dict[str, Any]:
    """Payload for morning.rewards on distraction-gate."""
    d = day or datetime.now(local_tz()).date()
    rec = _day_record(user_id, d)
    awards_out: dict[str, Any] = {}
    for kind, meta in AWARDS.items():
        got = rec["awards"].get(kind) or {}
        awards_out[kind] = {
            "points": int(meta["points"]),
            "label": meta["label"],
            "granted": bool(got.get("granted")),
            "granted_at": got.get("granted_at"),
        }
    return {
        "day": d.isoformat(),
        "awards": awards_out,
        "total_points": int(rec.get("total_points") or 0),
        "bible_points": BIBLE_POINTS,
        "plan_points": PLAN_POINTS,
    }
