"""Earned free-day credits for the desktop productivity gate.

Four qualifying days (daily productive goal plus Bible chapter) earn one
stackable credit. A credit can unlock the existing FREE mode until midnight.
The tracker keeps recording sessions; this only changes enforcement.

Bonus credits can be granted (dev/admin) without inventing fake qualifying days.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from backend.bible import store as bible_store
from backend.bible.paths import bible_dir
from backend.planner.service import local_tz

QUALIFYING_DAYS_PER_REWARD = 4
CONFIRM_PHRASE = "REWARD"


def _today() -> str:
    return datetime.now(local_tz()).date().isoformat()


def _path(user_id: int):
    return bible_dir() / f"reward_days_{user_id}.json"


def _load(user_id: int) -> dict[str, Any]:
    raw = bible_store._read_json(
        _path(user_id),
        {"qualified_dates": [], "used_dates": [], "granted": 0},
    )
    qualified = sorted({str(day) for day in raw.get("qualified_dates", []) if str(day)})
    used = sorted({str(day) for day in raw.get("used_dates", []) if str(day)})
    try:
        granted = max(0, int(raw.get("granted") or 0))
    except (TypeError, ValueError):
        granted = 0
    return {"qualified_dates": qualified, "used_dates": used, "granted": granted}


def _save(user_id: int, data: dict[str, Any]) -> None:
    bible_store._write_json(
        _path(user_id),
        {
            "qualified_dates": sorted(set(str(d) for d in data.get("qualified_dates", []) if str(d))),
            "used_dates": sorted(set(str(d) for d in data.get("used_dates", []) if str(d))),
            "granted": max(0, int(data.get("granted") or 0)),
        },
    )


def status(user_id: int) -> dict[str, Any]:
    data = _load(user_id)
    qualified = data["qualified_dates"]
    used = data["used_dates"]
    granted = int(data["granted"])
    earned = len(qualified) // QUALIFYING_DAYS_PER_REWARD
    spent = len(used)
    available = max(0, earned + granted - spent)
    day = bible_store.load_day(user_id)
    return {
        "qualifying_days": len(qualified),
        "qualifying_days_per_reward": QUALIFYING_DAYS_PER_REWARD,
        "days_to_next_reward": QUALIFYING_DAYS_PER_REWARD
        - (len(qualified) % QUALIFYING_DAYS_PER_REWARD),
        "earned": earned,
        "granted": granted,
        "spent": spent,
        "available": available,
        "active_today": bool(day.get("reward_day")),
        "confirm_phrase": CONFIRM_PHRASE,
    }


def grant_credits(user_id: int, count: int = 3) -> dict[str, Any]:
    """Bank bonus reward-day credits (does not invent qualifying history)."""
    n = int(count)
    if n <= 0:
        raise ValueError("count must be positive")
    data = _load(user_id)
    data["granted"] = int(data["granted"]) + n
    _save(user_id, data)
    return status(user_id)


def record_qualifying_day(user_id: int, *, qualified: bool) -> dict[str, Any]:
    """Idempotently record today's completed day; never count reward days."""
    if not qualified or bible_store.load_day(user_id).get("reward_day"):
        return status(user_id)
    data = _load(user_id)
    today = _today()
    if today not in data["qualified_dates"]:
        data["qualified_dates"].append(today)
        data["qualified_dates"].sort()
        _save(user_id, data)
    return status(user_id)


def claim_reward_day(user_id: int, *, confirm: str, already_unlocked: bool) -> dict[str, Any]:
    if (confirm or "").strip().upper() != CONFIRM_PHRASE:
        raise ValueError(f"Type {CONFIRM_PHRASE} to use an earned reward day")
    day = bible_store.load_day(user_id)
    if day.get("reward_day"):
        return {**status(user_id), "ok": True, "message": "Reward day is already active until midnight"}
    if already_unlocked:
        raise ValueError("Today is already unlocked; save the reward day for another day")

    current = status(user_id)
    if int(current["available"]) <= 0:
        raise ValueError(
            f"Complete {current['days_to_next_reward']} more qualifying day(s) to earn a reward day"
        )

    data = _load(user_id)
    data["used_dates"].append(_today())
    data["used_dates"] = sorted(set(data["used_dates"]))
    _save(user_id, data)
    day["reward_day"] = True
    bible_store.save_day(user_id, day)
    # Belt-and-suspenders: also arm tray free-override until midnight so the
    # browser gate resolves mode=free even if clients cache poorly.
    try:
        from datetime import timedelta

        from backend.behavior.browser_gate_policy import set_free_override

        now = datetime.now(local_tz())
        end = now.replace(hour=23, minute=59, second=59, microsecond=0)
        if end <= now:
            end = now + timedelta(minutes=60)
        mins = max(5, int((end - now).total_seconds() // 60))
        set_free_override(minutes=mins, now=now)
    except Exception:
        pass
    return {**status(user_id), "ok": True, "message": "Reward day active — free mode until midnight"}
