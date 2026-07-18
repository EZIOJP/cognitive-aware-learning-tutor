"""Zepp / Amazfit wearables ingest + active plans for Mini Program sync."""

from __future__ import annotations

import json
import secrets
from datetime import date, datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.core.auth import ensure_solo_owner
from backend.db.session import get_db
from backend.models import LifeDailyLog, User
from backend.models.planner import PlannerBlock
from backend.models.wearable_daily import WearableDaily
from backend.paths import ROOT
from backend.planner.service import _utc, iso_utc, local_tz, serialize_block
from backend.wearables.ingest_service import (
    normalize_sleep_hours,
    score_to_quality,
    serialize_wearable_daily,
    upsert_wearable_daily,
)

router = APIRouter(prefix="/api/wearables/zepp", tags=["wearables"])

_SYNC_STATE_PATH = ROOT / "data" / "wearables_last_sync.json"


def _read_sync_state() -> dict[str, Any]:
    try:
        if _SYNC_STATE_PATH.is_file():
            return json.loads(_SYNC_STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _write_sync_state(patch: dict[str, Any]) -> dict[str, Any]:
    cur = _read_sync_state()
    cur.update(patch)
    cur["updated_at"] = datetime.now(timezone.utc).isoformat()
    try:
        _SYNC_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _SYNC_STATE_PATH.write_text(json.dumps(cur, indent=2), encoding="utf-8")
    except Exception:
        pass
    return cur


def _expected_ingest_key() -> str:
    settings = get_settings()
    key = (getattr(settings, "wearables_ingest_key", None) or "").strip()
    if key:
        return key
    return "calt-local-wearables"


def require_wearable_key(
    authorization: str | None = Header(default=None),
    x_calt_wearable_key: str | None = Header(default=None, alias="X-CALT-Wearable-Key"),
) -> None:
    expected = _expected_ingest_key()
    provided = (x_calt_wearable_key or "").strip()
    if not provided and authorization:
        parts = authorization.split(None, 1)
        if len(parts) == 2 and parts[0].lower() == "bearer":
            provided = parts[1].strip()
    if not provided or not secrets.compare_digest(provided, expected):
        raise HTTPException(status_code=401, detail="Invalid wearable ingest key")


def _owner(db: Session) -> User:
    return ensure_solo_owner(db)


# --- schemas (extra fields accepted via model_extra / nested dicts) --------


class SleepIn(BaseModel):
    score: int | None = None
    total_min: int | None = None
    deep_min: int | None = None
    start_min: int | None = None
    end_min: int | None = None
    stages: list[dict[str, Any]] = Field(default_factory=list)
    naps: list[dict[str, Any]] = Field(default_factory=list)
    sleeping_status: int | None = None


class HeartIn(BaseModel):
    last: int | None = None
    resting: int | None = None


class ActivityIn(BaseModel):
    steps: int | None = None
    target: int | None = None


class CalorieIn(BaseModel):
    kcal: int | None = None
    target: int | None = None


class DistanceIn(BaseModel):
    meters: int | None = None


class Spo2In(BaseModel):
    value: int | None = None
    time: int | None = None
    retCode: int | None = None
    last_day_avg: int | None = None


class StressIn(BaseModel):
    value: int | None = None
    time: int | None = None
    today_by_hour: list[int] | None = None


class PaiIn(BaseModel):
    today: float | None = None
    total: float | None = None
    last_week: list[float] | None = None


class StandIn(BaseModel):
    hours: int | None = None
    target: int | None = None


class BatteryIn(BaseModel):
    pct: int | None = None


class DeviceIn(BaseModel):
    model: str | None = None
    os: str | None = None


class WearableIngestBody(BaseModel):
    schema_version: int = Field(default=1, alias="schema")
    source: str = "mini_program"
    device: DeviceIn | None = None
    captured_at: str | None = None
    local_date: str | None = None
    sleep: SleepIn | None = None
    heart: HeartIn | None = None
    activity: ActivityIn | None = None
    calorie: CalorieIn | None = None
    distance: DistanceIn | None = None
    spo2: Spo2In | None = None
    stress: StressIn | None = None
    pai: PaiIn | None = None
    stand: StandIn | None = None
    battery: BatteryIn | None = None
    meta: dict[str, Any] = Field(default_factory=dict)

    model_config = {"populate_by_name": True}


# Re-export helpers used by tests
def upsert_sleep_from_wearable(db, user, day, sleep, *, source_device="zepp_mini_program"):
    """Test helper — maps SleepIn into full upsert."""
    body = {
        "sleep": sleep.model_dump() if hasattr(sleep, "model_dump") else sleep,
    }
    return upsert_wearable_daily(db, user, day, body, source=source_device.replace("zepp_", ""))


def upsert_activity_from_wearable(db, user, day, activity, *, source_device="zepp_mini_program"):
    body = {
        "activity": activity.model_dump() if hasattr(activity, "model_dump") else activity,
    }
    return upsert_wearable_daily(db, user, day, body, source=source_device.replace("zepp_", ""))


@router.get("/health")
def wearable_health(_: None = Depends(require_wearable_key)):
    return {"ok": True, "service": "wearables.zepp", "last_sync": _read_sync_state()}


@router.get("/status")
def wearable_sync_status(
    db: Session = Depends(get_db),
    _: None = Depends(require_wearable_key),
):
    state = _read_sync_state()
    user = _owner(db)
    day = date.today()
    if state.get("last_local_date"):
        try:
            day = date.fromisoformat(str(state["last_local_date"])[:10])
        except ValueError:
            pass
    life = (
        db.query(LifeDailyLog)
        .filter(LifeDailyLog.user_id == user.id, LifeDailyLog.date == day)
        .first()
    )
    wrow = (
        db.query(WearableDaily)
        .filter(WearableDaily.user_id == user.id, WearableDaily.local_date == day)
        .first()
    )
    steps = state.get("last_steps")
    exercise_est = None
    if isinstance(steps, (int, float)) and steps is not None:
        exercise_est = min(180, int(steps) // 100)

    applied = None
    if life:
        applied = {
            "date": day.isoformat(),
            "sleep_hours": life.sleep_hours,
            "sleep_quality": life.sleep_quality,
            "exercise_minutes": life.exercise_minutes,
            "outdoor_minutes": life.outdoor_minutes,
            "stress_level": life.stress_level,
            "life_score": life.life_score,
        }

    authentic = {
        "watch_ingest": bool(state.get("last_is_watch") or state.get("last_source") == "mini_program"),
        "wrote_life": bool(state.get("last_wrote_life")),
        "plans_from_watch": bool(state.get("last_plans_from_watch")),
        "verdict": (
            "authentic_watch"
            if (
                (state.get("last_is_watch") or state.get("last_source") == "mini_program")
                and state.get("last_wrote_life")
            )
            else "plans_only_watch"
            if state.get("last_plans_from_watch")
            else "web_or_test"
            if state.get("last_source") in ("web_test",) or state.get("last_wrote_life") is False
            else "unknown"
        ),
    }

    return {
        "ok": True,
        "reachable": True,
        "last_sync": state or None,
        "applied_to_life": applied,
        "wearable_day": serialize_wearable_daily(wrow),
        "authentic": authentic,
        "estimates": {
            "steps_to_exercise": "floor(steps / 100) minutes, capped at 180",
            "exercise_from_last_steps": exercise_est,
            "distance_to_outdoor": "floor(meters / 80) minutes, capped at 180",
            "stress_to_life": "Amazfit stress / 20 → Life 1–5",
            "sleep_quality": "watch score 0–100 → quality 1–5",
        },
        "storage": {
            "wearable_daily": "SQLite wearable_daily (full snapshot)",
            "life_daily_log": "sleep, exercise, outdoor, stress, life_score",
            "hub_readings": "sleep_hours, steps, calories, heart_rate, spo2, stress, pai, distance_m",
            "sync_mirror": "data/wearables_last_sync.json",
        },
    }


@router.get("/today")
def wearable_today(
    db: Session = Depends(get_db),
    _: None = Depends(require_wearable_key),
):
    user = _owner(db)
    row = (
        db.query(WearableDaily)
        .filter(WearableDaily.user_id == user.id, WearableDaily.local_date == date.today())
        .first()
    )
    return {"ok": True, "day": serialize_wearable_daily(row)}


@router.post("")
@router.post("/")
def ingest_zepp(
    body: WearableIngestBody,
    db: Session = Depends(get_db),
    _: None = Depends(require_wearable_key),
):
    user = _owner(db)
    day = date.today()
    if body.local_date:
        try:
            day = date.fromisoformat(body.local_date[:10])
        except ValueError as e:
            raise HTTPException(status_code=400, detail="Invalid local_date") from e

    apply_to_life = (body.source or "").strip().lower() in ("mini_program", "zepp", "amazfit")
    payload = {
        "sleep": body.sleep.model_dump() if body.sleep else None,
        "heart": body.heart.model_dump() if body.heart else None,
        "activity": body.activity.model_dump() if body.activity else None,
        "calorie": body.calorie.model_dump() if body.calorie else None,
        "distance": body.distance.model_dump() if body.distance else None,
        "spo2": body.spo2.model_dump() if body.spo2 else None,
        "stress": body.stress.model_dump() if body.stress else None,
        "pai": body.pai.model_dump() if body.pai else None,
        "stand": body.stand.model_dump() if body.stand else None,
        "battery": body.battery.model_dump() if body.battery else None,
        "device": body.device.model_dump() if body.device else None,
        "meta": body.meta,
        "captured_at": body.captured_at,
    }
    # drop Nones for cleaner JSON
    payload = {k: v for k, v in payload.items() if v is not None}

    applied = None
    if apply_to_life and payload:
        applied = upsert_wearable_daily(db, user, day, payload, source=body.source)

    sleep_hours = (applied or {}).get("sleep_hours")
    if sleep_hours is None and body.sleep:
        sleep_hours = normalize_sleep_hours(body.sleep.total_min)
    steps_val = (applied or {}).get("steps")
    if steps_val is None and body.activity:
        steps_val = body.activity.steps

    _write_sync_state(
        {
            "last_ingest_at": datetime.now(timezone.utc).isoformat(),
            "last_source": body.source,
            "last_is_watch": apply_to_life,
            "last_wrote_life": bool(apply_to_life and applied),
            "last_local_date": day.isoformat(),
            "last_sleep_hours": sleep_hours,
            "last_sleep_quality": (applied or {}).get("sleep_quality")
            or (score_to_quality(body.sleep.score) if body.sleep else None),
            "last_steps": steps_val,
            "last_step_target": body.activity.target if body.activity else None,
            "last_calories": (applied or {}).get("calories")
            or (body.calorie.kcal if body.calorie else None),
            "last_distance_m": (applied or {}).get("distance_m")
            or (body.distance.meters if body.distance else None),
            "last_hr": (applied or {}).get("hr_last") or (body.heart.last if body.heart else None),
            "last_spo2": (applied or {}).get("spo2") or (body.spo2.value if body.spo2 else None),
            "last_stress": (applied or {}).get("stress")
            or (body.stress.value if body.stress else None),
            "last_pai": (applied or {}).get("pai_today")
            or (body.pai.today if body.pai else None),
            "last_stand": (applied or {}).get("stand_hours")
            or (body.stand.hours if body.stand else None),
            "last_battery": (applied or {}).get("battery_pct")
            or (body.battery.pct if body.battery else None),
            "last_exercise_minutes": (applied or {}).get("exercise_minutes"),
            "last_event": "ingest",
        }
    )

    return {
        "ok": True,
        "schema": body.schema_version,
        "source": body.source,
        "local_date": day.isoformat(),
        "wrote_life_tracker": bool(apply_to_life and applied),
        "applied": applied,
        "received_keys": sorted(payload.keys()),
        "last_sync": _read_sync_state(),
    }


@router.get("/plans")
def active_plans(
    horizon_hours: int = Query(24, ge=1, le=168),
    include_done: bool = Query(False),
    client: str = Query("unknown"),
    db: Session = Depends(get_db),
    _: None = Depends(require_wearable_key),
):
    user = _owner(db)
    now = datetime.now(timezone.utc)
    tz = local_tz()
    local_now = now.astimezone(tz)
    day_start_local = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    window_end = now + timedelta(hours=horizon_hours)
    window_start = _utc(day_start_local)

    q = (
        db.query(PlannerBlock)
        .filter(
            PlannerBlock.user_id == user.id,
            PlannerBlock.end_at >= window_start,
            PlannerBlock.start_at <= window_end,
        )
        .order_by(PlannerBlock.start_at.asc())
    )
    plans = []
    for b in q.all():
        if not include_done and b.status in ("cancelled", "done"):
            continue
        if b.status == "rolled":
            continue
        ser = serialize_block(b)
        plans.append(
            {
                "id": ser["id"],
                "title": ser["title"],
                "category": ser["category"],
                "start_at": ser["start_at"],
                "end_at": ser["end_at"],
                "status": ser["status"],
                "source": "study"
                if (b.category or "").lower() not in ("break", "personal")
                else "other",
                "planned_minutes": ser["planned_minutes"],
            }
        )

    client_norm = (client or "unknown").strip().lower()
    from_watch = client_norm in ("mini_program", "zepp", "amazfit")
    soft_day = _soft_day_payload(db, user)
    _write_sync_state(
        {
            "last_plans_at": now.isoformat(),
            "last_plan_count": len(plans),
            "last_plans_client": client_norm,
            "last_plans_from_watch": from_watch,
            "last_event": "plans",
        }
    )
    return {
        "schema": 1,
        "generated_at": iso_utc(now),
        "horizon_hours": horizon_hours,
        "client": client_norm,
        "authentic_watch": from_watch,
        "plans": plans,
        "soft_day": soft_day,
        "last_sync": _read_sync_state(),
    }


class PlanSnoozeBody(BaseModel):
    minutes: int = Field(15, ge=5, le=120)


def _soft_day_payload(db: Session, user: User) -> dict[str, Any]:
    try:
        from backend.wearables.ingest_service import sleep_load_scale_for_user

        scale, meta = sleep_load_scale_for_user(db, user.id)
        scale = float(scale or 1.0)
        hours = (meta or {}).get("sleep_hours")
        return {
            "active": scale < 0.95,
            "load_scale": scale,
            "label": "Soft day" if scale < 0.95 else "Full load",
            "reason": f"sleep {hours}h" if hours is not None else "",
            "sleep_hours": hours,
        }
    except Exception:
        return {"active": False, "load_scale": 1.0, "label": "Full load", "reason": ""}


@router.get("/calendar")
def wearable_calendar(
    days: int = Query(2, ge=1, le=14),
    client: str = Query("unknown"),
    db: Session = Depends(get_db),
    _: None = Depends(require_wearable_key),
):
    """Planner blocks as calendar-style day agenda for the watch."""
    from backend.planner.service import local_day_bounds_utc

    user = _owner(db)
    now = datetime.now(timezone.utc)
    tz = local_tz()
    local_now = now.astimezone(tz)
    day0 = local_now.date()
    soft_day = _soft_day_payload(db, user)

    by_day: list[dict[str, Any]] = []
    for i in range(days):
        d = day0 + timedelta(days=i)
        start_utc, end_utc = local_day_bounds_utc(d)
        rows = (
            db.query(PlannerBlock)
            .filter(
                PlannerBlock.user_id == user.id,
                PlannerBlock.start_at < end_utc,
                PlannerBlock.end_at > start_utc,
                PlannerBlock.status.notin_(("cancelled", "rolled")),
            )
            .order_by(PlannerBlock.start_at.asc())
            .all()
        )
        events = []
        for b in rows:
            ser = serialize_block(b)
            events.append(
                {
                    "id": ser["id"],
                    "title": ser["title"],
                    "category": ser["category"],
                    "start_at": ser["start_at"],
                    "end_at": ser["end_at"],
                    "status": ser["status"],
                    "planned_minutes": ser["planned_minutes"],
                    "color": ser.get("color"),
                }
            )
        by_day.append(
            {
                "date": d.isoformat(),
                "weekday": d.strftime("%a").lower(),
                "is_today": i == 0,
                "events": events,
                "event_count": len(events),
            }
        )

    next_up = None
    for day in by_day:
        for ev in day["events"]:
            if ev["status"] in ("done", "cancelled"):
                continue
            try:
                end = datetime.fromisoformat(str(ev["end_at"]).replace("Z", "+00:00"))
                if end.tzinfo is None:
                    end = end.replace(tzinfo=timezone.utc)
                if end >= now:
                    next_up = {**ev, "day": day["date"]}
                    break
            except Exception:
                continue
        if next_up:
            break

    _write_sync_state(
        {
            "last_calendar_at": now.isoformat(),
            "last_calendar_days": days,
            "last_calendar_events": sum(d["event_count"] for d in by_day),
            "last_event": "calendar",
        }
    )
    return {
        "schema": 1,
        "generated_at": iso_utc(now),
        "days": by_day,
        "next_up": next_up,
        "soft_day": soft_day,
        "client": (client or "unknown").strip().lower(),
    }


def _get_plan_block(db: Session, user_id: int, block_id: int) -> PlannerBlock:
    block = (
        db.query(PlannerBlock)
        .filter(PlannerBlock.id == block_id, PlannerBlock.user_id == user_id)
        .first()
    )
    if not block:
        raise HTTPException(status_code=404, detail="Plan block not found")
    return block


@router.post("/plans/{block_id}/start")
def wearable_plan_start(
    block_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_wearable_key),
):
    user = _owner(db)
    block = _get_plan_block(db, user.id, block_id)
    block.status = "in_progress"
    db.commit()
    db.refresh(block)
    return {"ok": True, "block": serialize_block(block)}


@router.post("/plans/{block_id}/complete")
def wearable_plan_complete(
    block_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_wearable_key),
):
    from backend.planner.service import complete_block

    user = _owner(db)
    block = _get_plan_block(db, user.id, block_id)
    complete_block(block, minutes_spent=None)
    db.commit()
    db.refresh(block)
    return {"ok": True, "block": serialize_block(block)}


@router.post("/plans/{block_id}/snooze")
def wearable_plan_snooze(
    block_id: int,
    body: PlanSnoozeBody | None = None,
    db: Session = Depends(get_db),
    _: None = Depends(require_wearable_key),
):
    user = _owner(db)
    block = _get_plan_block(db, user.id, block_id)
    mins = (body.minutes if body else 15) or 15
    delta = timedelta(minutes=mins)
    block.start_at = block.start_at + delta
    block.end_at = block.end_at + delta
    if block.status == "in_progress":
        block.status = "scheduled"
    db.commit()
    db.refresh(block)
    return {"ok": True, "snoozed_minutes": mins, "block": serialize_block(block)}
