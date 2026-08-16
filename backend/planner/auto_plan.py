"""Auto-draft today's planner after morning Bible (routines + light focus seeds).

Confirm remains compulsory by default (``MORNING_AUTO_PLAN_CONFIRM=0``).
Set ``MORNING_AUTO_PLAN_CONFIRM=1`` to auto-confirm only inside the plan window.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from backend.models.planner import PlannerBlock
from backend.models.user import User
from backend.paths import ROOT
from backend.planner.service import (
    _minutes_between,
    _utc,
    end_from_start_and_minutes,
    local_day_bounds_utc,
    local_tz,
    wall_clock_on_date,
)

log = logging.getLogger(__name__)

AUTO_DRAFT_STATE_PATH = ROOT / "data" / "planner_auto_draft.json"

_DEFAULT_STUDY_TITLES = (
    ("Deep work — study", "Study / Reading"),
    ("Scaler / coding practice", "Coding Practice"),
)


def _env_on(name: str, default: str = "1") -> bool:
    return os.environ.get(name, default).strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def morning_auto_plan_enabled() -> bool:
    return _env_on("MORNING_AUTO_PLAN", "1")


def morning_auto_plan_confirm() -> bool:
    """When True, confirm plan automatically after a successful draft (inside window only)."""
    return _env_on("MORNING_AUTO_PLAN_CONFIRM", "0")


def _path() -> Path:
    AUTO_DRAFT_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    return AUTO_DRAFT_STATE_PATH


def _load_state() -> dict[str, Any]:
    p = _path()
    if not p.is_file():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _save_state(data: dict[str, Any]) -> None:
    _path().write_text(json.dumps(data, indent=2), encoding="utf-8")


def _key(user_id: int, day: date) -> str:
    return f"{int(user_id)}:{day.isoformat()}"


def _empty_summary(day: date | None = None) -> dict[str, Any]:
    d = day or datetime.now(local_tz()).date()
    return {
        "drafted": False,
        "day": d.isoformat(),
        "titles": [],
        "created": 0,
        "confirmed": False,
        "reason": None,
    }


def auto_plan_summary(user_id: int, day: date | None = None) -> dict[str, Any]:
    """Payload fragment for morning.auto_plan (tracker / Jarvis / UI)."""
    d = day or datetime.now(local_tz()).date()
    raw = _load_state().get(_key(user_id, d))
    if not isinstance(raw, dict):
        return _empty_summary(d)
    titles = raw.get("titles") if isinstance(raw.get("titles"), list) else []
    return {
        "drafted": bool(raw.get("drafted")),
        "day": d.isoformat(),
        "titles": [str(t) for t in titles][:12],
        "created": int(raw.get("created") or 0),
        "confirmed": bool(raw.get("confirmed")),
        "reason": raw.get("reason"),
        "drafted_at": raw.get("drafted_at"),
    }


def _blocks_today(db: Session, user_id: int, day: date) -> list[PlannerBlock]:
    start, end = local_day_bounds_utc(day)
    return (
        db.query(PlannerBlock)
        .filter(
            PlannerBlock.user_id == user_id,
            PlannerBlock.start_at < end,
            PlannerBlock.end_at > start,
        )
        .order_by(PlannerBlock.start_at)
        .all()
    )


def _record_draft(
    user_id: int,
    day: date,
    *,
    titles: list[str],
    created: int,
    confirmed: bool = False,
    reason: str | None = None,
) -> dict[str, Any]:
    data = _load_state()
    entry = {
        "drafted": True,
        "day": day.isoformat(),
        "user_id": int(user_id),
        "titles": titles[:12],
        "created": int(created),
        "confirmed": bool(confirmed),
        "reason": reason,
        "drafted_at": datetime.now(local_tz()).isoformat(),
    }
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
    keep[_key(user_id, day)] = entry
    _save_state(keep)
    return {
        "drafted": True,
        "day": day.isoformat(),
        "titles": titles[:12],
        "created": int(created),
        "confirmed": bool(confirmed),
        "reason": reason,
        "drafted_at": entry["drafted_at"],
    }


def _peak_hours_yesterday(db: Session, user_id: int, day: date) -> list[int]:
    """Lightweight peak hours from last few days of productivity export."""
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if user is None:
            return []
        from backend.planner.week_export import build_productivity_week_export

        # End on yesterday so we don't lean on incomplete today
        end = day - timedelta(days=1)
        payload = build_productivity_week_export(db, user, days=7, end_day=end)
        peaks = (payload.get("summary") or {}).get("peak_hours") or []
        out: list[int] = []
        for h in peaks:
            try:
                hi = int(h)
            except (TypeError, ValueError):
                continue
            if 6 <= hi <= 22:
                out.append(hi)
        return out[:3]
    except Exception as exc:  # noqa: BLE001
        log.debug("auto_plan peak hours failed: %s", exc)
        return []


def _seed_study_blocks(
    db: Session,
    user_id: int,
    day: date,
    *,
    peak_hours: list[int],
) -> list[PlannerBlock]:
    """Add up to two study blocks in free gaps near peak hours (no LLM)."""
    from backend.planner.routines import _has_overlap

    hours = peak_hours or [10, 15]
    created: list[PlannerBlock] = []
    for i, hour in enumerate(hours[:2]):
        title, category = _DEFAULT_STUDY_TITLES[i % len(_DEFAULT_STUDY_TITLES)]
        start_local = wall_clock_on_date(day, f"{hour:02d}:00")
        end_local = end_from_start_and_minutes(start_local, 50)
        start_at, end_at = _utc(start_local), _utc(end_local)
        if _has_overlap(db, user_id, start_at, end_at):
            # Try +1h once
            start_local = wall_clock_on_date(day, f"{min(22, hour + 1):02d}:00")
            end_local = end_from_start_and_minutes(start_local, 50)
            start_at, end_at = _utc(start_local), _utc(end_local)
            if _has_overlap(db, user_id, start_at, end_at):
                continue
        minutes = _minutes_between(start_at, end_at)
        block = PlannerBlock(
            user_id=user_id,
            title=title,
            category=category,
            start_at=start_at,
            end_at=end_at,
            planned_minutes=minutes,
            remaining_minutes=minutes,
            status="scheduled",
        )
        db.add(block)
        created.append(block)
    if created:
        db.commit()
        for b in created:
            db.refresh(b)
    return created


def _maybe_speak_drafted(titles: list[str]) -> None:
    try:
        from backend.behavior.voice_agent.dialogues import speak

        # Queued TTS worker serializes; force only bypasses rate gap (not overlap).
        speak("plan_auto_drafted", force=True, blocks=str(len(titles)))
    except Exception as exc:  # noqa: BLE001
        log.debug("plan_auto_drafted speak failed: %s", exc)


def _maybe_speak_plan_exists(titles: list[str]) -> None:
    try:
        from backend.behavior.voice_agent.dialogues import speak

        speak(
            "plan_exists_ask",
            force=True,
            blocks=str(len(titles)),
        )
    except Exception as exc:  # noqa: BLE001
        log.debug("plan_exists_ask speak failed: %s", exc)


def _maybe_auto_confirm(
    user_id: int,
    *,
    bible_done: bool,
    bible_completed_at: datetime | str | None,
    now: datetime | None,
) -> bool:
    if not morning_auto_plan_confirm():
        return False
    try:
        from backend.planner import morning_plan as mp

        # Auto-confirm skips goals check (env flag); UI confirm still requires goals.
        mp.confirm_plan_today(
            user_id,
            bible_done=bible_done,
            bible_completed_at=bible_completed_at,
            now=now,
            require_goals=False,
        )
        return True
    except Exception as exc:  # noqa: BLE001
        log.debug("auto confirm skipped: %s", exc)
        return False


def auto_draft_day_plan(
    db: Session,
    user_id: int,
    *,
    day: date | None = None,
    bible_done: bool = True,
    bible_completed_at: datetime | str | None = None,
    now: datetime | None = None,
    speak: bool = True,
    add_more: bool = False,
) -> dict[str, Any]:
    """Draft today's plan from routines + light yesterday peak seeds.

    Idempotent per user/day. Does not clobber an existing day plan
    (any planner blocks already on the calendar) unless *add_more* is True
    (then routines/seeds fill gaps with skip_overlaps). Confirm stays required
    unless ``MORNING_AUTO_PLAN_CONFIRM=1`` and the plan window is open.
    """
    tz = local_tz()
    if now is None:
        now_local = datetime.now(tz)
    elif now.tzinfo is None:
        now_local = now.replace(tzinfo=tz)
    else:
        now_local = now.astimezone(tz)
    d = day or now_local.date()

    if not morning_auto_plan_enabled():
        return {
            "ok": True,
            "skipped": True,
            "reason": "disabled",
            "created": 0,
            "titles": [],
            "auto_plan": _empty_summary(d),
            "confirmed": False,
        }

    existing_state = _load_state().get(_key(user_id, d))
    if (
        not add_more
        and isinstance(existing_state, dict)
        and existing_state.get("drafted")
    ):
        summary = auto_plan_summary(user_id, d)
        return {
            "ok": True,
            "skipped": True,
            "reason": "already_drafted",
            "created": 0,
            "titles": list(summary.get("titles") or []),
            "auto_plan": summary,
            "confirmed": bool(summary.get("confirmed")),
        }

    existing_blocks = _blocks_today(db, user_id, d)
    if existing_blocks and not add_more:
        titles = [str(b.title or "Block") for b in existing_blocks]
        # Existing calendar ≠ confirmed morning plan. User must Confirm explicitly.
        confirmed = False
        try:
            from backend.planner import morning_plan as mp

            confirmed = bool(mp.is_plan_confirmed(user_id, d))
        except Exception:
            confirmed = False

        summary = _record_draft(
            user_id,
            d,
            titles=titles,
            created=0,
            confirmed=confirmed,
            reason="plan_exists",
        )
        summary["drafted"] = True
        if speak and not confirmed:
            _maybe_speak_plan_exists(titles)
        return {
            "ok": True,
            "skipped": True,
            "reason": "plan_exists",
            "created": 0,
            "titles": titles[:12],
            "auto_plan": summary,
            "confirmed": confirmed,
            "ask": None if confirmed else "add_or_confirm",
        }

    from backend.planner.routines import apply_routines

    routine_blocks = apply_routines(db, user_id, target_date=d, skip_overlaps=True)
    peaks = _peak_hours_yesterday(db, user_id, d)
    study_blocks = _seed_study_blocks(db, user_id, d, peak_hours=peaks)

    all_created = list(routine_blocks) + list(study_blocks)
    # Re-read day for complete title list
    day_blocks = _blocks_today(db, user_id, d)
    titles = [str(b.title or "Block") for b in day_blocks]

    confirmed = _maybe_auto_confirm(
        user_id,
        bible_done=bible_done,
        bible_completed_at=bible_completed_at,
        now=now_local,
    )
    reason = "add_more" if add_more else None
    auto_plan = _record_draft(
        user_id,
        d,
        titles=titles,
        created=len(all_created),
        confirmed=confirmed,
        reason=reason,
    )
    if speak and all_created:
        _maybe_speak_drafted(titles)

    return {
        "ok": True,
        "skipped": False,
        "reason": reason,
        "created": len(all_created),
        "titles": titles[:12],
        "auto_plan": auto_plan,
        "confirmed": confirmed,
        "blocks": [{"id": b.id, "title": b.title} for b in all_created],
    }


def maybe_auto_draft_after_bible(
    user_id: int,
    *,
    bible_done: bool = True,
    bible_completed_at: datetime | str | None = None,
) -> dict[str, Any] | None:
    """Open a DB session and draft if Bible is done. Soft-fail safe for store hooks."""
    if not bible_done or not morning_auto_plan_enabled():
        return None
    try:
        from backend.db.base import SessionLocal

        db = SessionLocal()
        try:
            return auto_draft_day_plan(
                db,
                user_id,
                bible_done=True,
                bible_completed_at=bible_completed_at,
            )
        finally:
            db.close()
    except Exception as exc:  # noqa: BLE001
        log.warning("maybe_auto_draft_after_bible failed: %s", exc)
        return None
