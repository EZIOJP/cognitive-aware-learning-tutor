"""Morning plan confirm — required after Bible before the SPA fully opens.

Plan confirm is only valid inside a local-day window:
  start = max(bible_completed_at, MORNING_PLAN_START)  # default 05:00
  end   = MORNING_PLAN_EOD                             # default 23:59
"""

from __future__ import annotations

import json
import os
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any

from backend.paths import ROOT
from backend.planner.service import local_tz

_STORE = ROOT / "data" / "planner_morning_confirm.json"

_DEFAULT_START = "05:00"
_DEFAULT_EOD = "23:59"
_HHMM_RE = re.compile(r"^(\d{1,2}):(\d{2})$")


class PlanWindowError(ValueError):
    """Confirm attempted outside the allowed plan window."""

    def __init__(self, message: str, *, window: dict[str, Any] | None = None):
        super().__init__(message)
        self.window = window or {}


class GoalsRequiredError(ValueError):
    """Confirm rejected because morning goals string is empty / too short."""


GOALS_MIN_LEN = 3


def goals_text_ok(goals: str | None) -> bool:
    """True when goals string is non-empty after strip (min ~3 chars)."""
    return len((goals or "").strip()) >= GOALS_MIN_LEN


def assert_goals_present(goals: str | None) -> str:
    text = (goals or "").strip()
    if len(text) < GOALS_MIN_LEN:
        raise GoalsRequiredError("Goals required")
    return text


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


def is_plan_confirmed(user_id: int, day: date | None = None) -> bool:
    return bool(_load().get(_key(user_id, day)))


def parse_hhmm(raw: str | None, *, default: str) -> tuple[int, int]:
    """Parse ``HH:MM`` (24h). Falls back to *default* on bad input."""
    text = (raw or "").strip() or default
    m = _HHMM_RE.match(text)
    if not m:
        m = _HHMM_RE.match(default)
        assert m is not None
    hour = max(0, min(23, int(m.group(1))))
    minute = max(0, min(59, int(m.group(2))))
    return hour, minute


def plan_start_hhmm() -> str:
    h, m = parse_hhmm(os.environ.get("MORNING_PLAN_START"), default=_DEFAULT_START)
    return f"{h:02d}:{m:02d}"


def plan_eod_hhmm() -> str:
    h, m = parse_hhmm(os.environ.get("MORNING_PLAN_EOD"), default=_DEFAULT_EOD)
    return f"{h:02d}:{m:02d}"


def _aware(dt: datetime) -> datetime:
    tz = local_tz()
    if dt.tzinfo is None:
        return dt.replace(tzinfo=tz)
    return dt.astimezone(tz)


def parse_iso_local(raw: str | None) -> datetime | None:
    if not raw or not isinstance(raw, str):
        return None
    text = raw.strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        return _aware(datetime.fromisoformat(text))
    except ValueError:
        return None


def _clock_on_day(day: date, hh: int, mm: int, *, end_of_minute: bool = False) -> datetime:
    tz = local_tz()
    if end_of_minute:
        return datetime(day.year, day.month, day.day, hh, mm, 59, 999999, tzinfo=tz)
    return datetime(day.year, day.month, day.day, hh, mm, 0, 0, tzinfo=tz)


def plan_window_bounds(
    day: date | None = None,
    *,
    bible_completed_at: datetime | str | None = None,
) -> tuple[datetime, datetime]:
    """Return (window_start, window_end) in local time for *day*.

    ``window_start`` = max(bible_completed_at, MORNING_PLAN_START on day).
    When bible is not yet done / no timestamp, start is the clock start only.
    ``window_end`` = MORNING_PLAN_EOD on day (inclusive through that minute).
    """
    d = day or datetime.now(local_tz()).date()
    sh, sm = parse_hhmm(os.environ.get("MORNING_PLAN_START"), default=_DEFAULT_START)
    eh, em = parse_hhmm(os.environ.get("MORNING_PLAN_EOD"), default=_DEFAULT_EOD)
    clock_start = _clock_on_day(d, sh, sm)
    window_end = _clock_on_day(d, eh, em, end_of_minute=True)

    completed: datetime | None
    if isinstance(bible_completed_at, datetime):
        completed = _aware(bible_completed_at)
    else:
        completed = parse_iso_local(bible_completed_at)

    if completed is not None and completed.date() == d:
        window_start = max(completed, clock_start)
    else:
        window_start = clock_start
    return window_start, window_end


def _fmt_clock(dt: datetime) -> str:
    return dt.strftime("%H:%M")


def _human_until(end: datetime) -> str:
    """Short label for UI — midnight vs clock time."""
    if end.hour == 23 and end.minute == 59:
        return "midnight"
    return _fmt_clock(end)


def evaluate_plan_window(
    *,
    bible_done: bool,
    bible_completed_at: datetime | str | None = None,
    now: datetime | None = None,
    day: date | None = None,
) -> dict[str, Any]:
    """Plan-window status for UI hints.

    Soft planning: after Bible is done, confirm is always available (edit/confirm
    anytime). ``phase`` still notes typical morning start / EOD for gentle copy —
    it does **not** lock the Confirm CTA.
    """
    tz = local_tz()
    now_local = _aware(now) if now is not None else datetime.now(tz)
    d = day or now_local.date()
    start, end = plan_window_bounds(d, bible_completed_at=bible_completed_at)
    start_hhmm = plan_start_hhmm()
    eod_hhmm = plan_eod_hhmm()

    if not bible_done:
        phase = "awaiting_bible"
        confirm_available = False
        reason = "Finish today’s Bible chapter before confirming the plan."
    elif now_local < start:
        # Soft: clock start is a hint only — confirm anytime after Bible.
        phase = "before_start"
        confirm_available = True
        reason = (
            f"Typical morning start is {_fmt_clock(start)} — "
            "you can edit and confirm the plan anytime."
        )
    elif now_local > end:
        phase = "after_eod"
        confirm_available = True
        reason = (
            f"Past usual end ({eod_hhmm}). Soft-land won’t force plan — "
            "you can still edit or confirm if you want."
        )
    else:
        phase = "open"
        confirm_available = True
        reason = f"Confirm when ready · usual window until {_human_until(end)}."

    completed_iso: str | None = None
    if isinstance(bible_completed_at, datetime):
        completed_iso = _aware(bible_completed_at).isoformat()
    else:
        parsed = parse_iso_local(bible_completed_at)
        if parsed is not None:
            completed_iso = parsed.isoformat()

    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "start_hhmm": start_hhmm,
        "eod_hhmm": eod_hhmm,
        "start_clock": _fmt_clock(start),
        "end_clock": _fmt_clock(end),
        "end_label": _human_until(end),
        "phase": phase,
        "confirm_available": confirm_available,
        "reason": reason,
        "bible_completed_at": completed_iso,
        "soft": True,
    }


def assert_plan_confirm_allowed(
    *,
    bible_done: bool,
    bible_completed_at: datetime | str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Raise PlanWindowError if confirm is not allowed right now."""
    if not bible_done:
        raise PlanWindowError(
            "Finish today's Bible chapter before confirming the plan.",
            window=evaluate_plan_window(
                bible_done=False,
                bible_completed_at=bible_completed_at,
                now=now,
            ),
        )
    window = evaluate_plan_window(
        bible_done=True,
        bible_completed_at=bible_completed_at,
        now=now,
    )
    if not window["confirm_available"]:
        raise PlanWindowError(str(window["reason"]), window=window)
    return window


def confirm_plan_today(
    user_id: int,
    *,
    bible_done: bool = True,
    bible_completed_at: datetime | str | None = None,
    now: datetime | None = None,
    skip_window_check: bool = False,
    goals: str | None = None,
    require_goals: bool = True,
) -> dict[str, Any]:
    """Mark today's plan as reviewed/confirmed. Idempotent. Grants Plan +10 once.

    Rejects outside the plan window unless *skip_window_check* (tests only).
    Rejects when *require_goals* and goals string is empty / shorter than
    ``GOALS_MIN_LEN`` (Goals required).
    """
    try:
        from backend.behavior.demo_clock import assert_not_demo_writes

        assert_not_demo_writes()
    except RuntimeError as exc:
        raise PlanWindowError(str(exc)) from exc
    except Exception:
        pass

    goals_text = ""
    if require_goals:
        goals_text = assert_goals_present(goals)
    else:
        goals_text = (goals or "").strip()

    if not skip_window_check:
        assert_plan_confirm_allowed(
            bible_done=bible_done,
            bible_completed_at=bible_completed_at,
            now=now,
        )

    data = _load()
    day = (_aware(now) if now is not None else datetime.now(local_tz())).date()
    k = _key(user_id, day)
    data[k] = {
        "confirmed_at": datetime.now(local_tz()).isoformat(),
        "day": day.isoformat(),
        "user_id": int(user_id),
        "goals": goals_text[:2000] if goals_text else "",
    }
    # Prune older than ~14 days for this user
    prefix = f"{int(user_id)}:"
    keep: dict[str, Any] = {}
    for key, val in data.items():
        if not key.startswith(prefix):
            keep[key] = val
            continue
        try:
            d = date.fromisoformat(key.split(":", 1)[1])
        except ValueError:
            continue
        if (day - d).days <= 14:
            keep[key] = val
    keep[k] = data[k]
    _save(keep)
    rewards: dict[str, Any] | None = None
    try:
        from backend.planner import morning_rewards as mr

        rewards = mr.grant_plan(user_id)
    except Exception:
        rewards = None
    out: dict[str, Any] = {
        "ok": True,
        "day": day.isoformat(),
        "confirmed": True,
        "goals_ok": bool(goals_text),
    }
    if rewards is not None:
        out["morning_rewards"] = rewards
    return out


def count_blocks_today(db, user_id: int, day: date | None = None) -> int:
    from backend.models.planner import PlannerBlock
    from backend.planner.service import local_day_bounds_utc

    day = day or datetime.now(local_tz()).date()
    start, end = local_day_bounds_utc(day)
    return (
        db.query(PlannerBlock)
        .filter(
            PlannerBlock.user_id == user_id,
            PlannerBlock.start_at < end,
            PlannerBlock.end_at > start,
        )
        .count()
    )


def morning_hint_for(
    next_step: str,
    *,
    plan_window: dict[str, Any] | None = None,
    rewards_total: int = 0,
    morning_on: bool = True,
) -> str:
    """Dynamic hint string for gate / tracker / UI."""
    pw = plan_window or {}
    phase = str(pw.get("phase") or "")
    if next_step == "bible":
        return "Finish today’s Bible chapter (+10), then confirm plan/goals (+10)."
    if next_step == "plan":
        if phase == "before_start":
            return str(
                pw.get("reason")
                or (
                    f"Typical morning starts at {pw.get('start_clock') or plan_start_hhmm()} — "
                    "edit and confirm anytime."
                )
            )
        end_label = pw.get("end_label") or _human_until(
            parse_iso_local(pw.get("end")) or datetime.now(local_tz())
        )
        return (
            f"Review goals & plan on Productivity, then Confirm (+10) when ready. "
            f"Usual window until {end_label}."
        )
    if morning_on:
        if phase == "after_eod":
            return str(
                pw.get("reason")
                or (
                    f"Past usual end ({pw.get('eod_hhmm') or plan_eod_hhmm()}). "
                    "Day is open — confirm still optional."
                )
            )
        return f"Morning complete — {rewards_total} pts today."
    return "Morning gate off."
