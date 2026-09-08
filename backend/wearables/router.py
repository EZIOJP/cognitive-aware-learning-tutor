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
    PayloadTooLarge,
    normalize_sleep_hours,
    score_to_quality,
    serialize_wearable_daily,
    upsert_wearable_daily,
)
from backend.wearables.day_stamp import resolve_ingest_day, tz_from_payload
from backend.wearables.health_connect_map import coerce_ingest_body, inventory_categories

_LIFE_WRITE_SOURCES = frozenset(
    {
        "mini_program",
        "zepp",
        "amazfit",
        "health_connect",
        "hc",
        "google_fit",
        "bridge_export",
        "zeppbridge",
    }
)

router = APIRouter(prefix="/api/wearables/zepp", tags=["wearables"])

_SYNC_STATE_PATH = ROOT / "data" / "wearables_last_sync.json"
_STATUS_CACHE: tuple[float, dict[str, Any]] | None = None
_STATUS_TTL_S = 20.0


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


class HeartIn(BaseModel):
    model_config = {"extra": "allow"}
    last: int | None = None
    resting: int | None = None
    today_min: list[Any] | None = None
    today_count: int | None = None
    daily_summary: Any | None = None
    afib: Any | None = None


class ActivityIn(BaseModel):
    model_config = {"extra": "allow"}
    steps: int | None = None
    target: int | None = None
    sitting_min: int | None = None
    sedentary_min: int | None = None


class CalorieIn(BaseModel):
    model_config = {"extra": "allow"}
    kcal: int | None = None
    target: int | None = None


class DistanceIn(BaseModel):
    model_config = {"extra": "allow"}
    meters: int | None = None


class Spo2In(BaseModel):
    model_config = {"extra": "allow"}
    value: int | None = None
    time: int | None = None
    retCode: int | None = None
    last_day_avg: int | None = None
    last_day: list[Any] | None = None
    last_few_hour: Any | None = None


class StressIn(BaseModel):
    model_config = {"extra": "allow"}
    value: int | None = None
    time: int | None = None
    today_by_hour: list[Any] | None = None
    last_week: list[Any] | None = None
    today_sample: list[Any] | None = None


class PaiIn(BaseModel):
    model_config = {"extra": "allow"}
    today: float | None = None
    total: float | None = None
    last_week: list[Any] | None = None


class StandIn(BaseModel):
    model_config = {"extra": "allow"}
    hours: int | None = None
    target: int | None = None


class SittingIn(BaseModel):
    model_config = {"extra": "allow"}
    minutes: int | None = None
    min: int | None = None
    sitting_min: int | None = None
    value: int | None = None


class BatteryIn(BaseModel):
    model_config = {"extra": "allow"}
    pct: int | None = None


class FatBurnIn(BaseModel):
    model_config = {"extra": "allow"}
    minutes: int | None = None
    target: int | None = None


class WeatherIn(BaseModel):
    model_config = {"extra": "allow"}
    city: str | None = None
    today_high: float | None = None
    today_low: float | None = None
    today_index: int | None = None
    sunrise: Any | None = None
    sunset: Any | None = None
    forecast_count: int | None = None


class DeviceIn(BaseModel):
    model_config = {"extra": "allow"}
    model: str | None = None
    os: str | None = Field(
        default=None,
        description="Zepp OS major version as sent by the watch (current: 6).",
        examples=["6"],
    )


class SleepIn(BaseModel):
    model_config = {"extra": "allow"}
    score: int | None = None
    total_min: int | None = None
    deep_min: int | None = None
    start_min: int | None = Field(
        default=None,
        description="Sleep onset as minutes from that calendar day's 00:00 (watch tz). May be used with end_min > 1440.",
    )
    end_min: int | None = Field(
        default=None,
        description="Sleep wake as minutes from onset-day 00:00 (watch tz). Overnight sleep can exceed 1440.",
    )
    stages: list[dict[str, Any]] = Field(default_factory=list)
    naps: list[dict[str, Any]] = Field(default_factory=list)
    nap_min: int | None = None
    sleeping_status: int | None = None


class TemperatureIn(BaseModel):
    model_config = {"extra": "allow"}
    value: float | None = None
    celsius: float | None = None
    available: bool | None = None


class WearableIngestBody(BaseModel):
    schema_version: int = Field(
        default=1,
        alias="schema",
        description="Payload schema. 2 = watch clock stamps (local_date, tz_offset_min, captured_at) + chunk meta.",
    )
    source: str = "mini_program"
    device: DeviceIn | None = None
    captured_at: str | None = Field(
        default=None,
        description="ISO-8601 instant from the watch clock, not the phone.",
    )
    local_date: str | None = Field(
        default=None,
        description="Watch calendar day YYYY-MM-DD. Phone/PC must not overwrite this.",
        examples=["2026-08-18"],
    )
    tz_offset_min: int | None = Field(
        default=None,
        description="Watch offset east of UTC in minutes (JS: -Date.getTimezoneOffset()). IST = 330.",
        examples=[330],
    )
    sleep: SleepIn | None = None
    heart: HeartIn | None = None
    activity: ActivityIn | None = None
    calorie: CalorieIn | None = None
    distance: DistanceIn | None = None
    spo2: Spo2In | None = None
    stress: StressIn | None = None
    pai: PaiIn | None = None
    stand: StandIn | None = None
    sitting: SittingIn | None = None
    battery: BatteryIn | None = None
    fat_burn: FatBurnIn | None = None
    temperature: TemperatureIn | None = None
    weather: WeatherIn | None = None
    meta_device: dict[str, Any] = Field(default_factory=dict)
    capabilities: dict[str, Any] = Field(default_factory=dict)
    dump: str | None = None
    dump_id: str | None = None
    checksum: str | None = None
    meta: dict[str, Any] = Field(default_factory=dict)

    model_config = {"populate_by_name": True, "extra": "allow"}


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
    import time

    from backend.behavior.time_fmt import optional_hours_label, optional_minutes_label
    from backend.planner.service import local_tz

    global _STATUS_CACHE
    now = time.monotonic()
    if _STATUS_CACHE is not None and (now - _STATUS_CACHE[0]) < _STATUS_TTL_S:
        return _STATUS_CACHE[1]

    state = _read_sync_state()
    user = _owner(db)
    # Prefer host-local today from central DB — not JSON mirror date
    day = datetime.now(local_tz()).date()
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
    # If no wearable row today, fall back to latest wearable day for status card
    if not wrow:
        wrow = (
            db.query(WearableDaily)
            .filter(WearableDaily.user_id == user.id)
            .order_by(WearableDaily.local_date.desc())
            .first()
        )
    steps = (wrow.steps if wrow else None) or state.get("last_steps")
    exercise_est = None
    if isinstance(steps, (int, float)) and steps is not None:
        exercise_est = min(180, int(steps) // 100)

    applied = None
    if life:
        applied = {
            "date": day.isoformat(),
            "sleep_hours": life.sleep_hours,
            "sleep_label": optional_hours_label(life.sleep_hours),
            "sleep_quality": life.sleep_quality,
            "exercise_minutes": life.exercise_minutes,
            "exercise_label": optional_minutes_label(life.exercise_minutes),
            "outdoor_minutes": life.outdoor_minutes,
            "outdoor_label": optional_minutes_label(life.outdoor_minutes),
            "stress_level": life.stress_level,
            "life_score": life.life_score,
        }
    elif wrow:
        applied = {
            "date": wrow.local_date.isoformat(),
            "sleep_hours": wrow.sleep_hours,
            "sleep_label": optional_hours_label(wrow.sleep_hours),
            "sleep_quality": None,
            "exercise_minutes": None,
            "exercise_label": None,
            "outdoor_minutes": None,
            "outdoor_label": None,
            "stress_level": None,
            "life_score": None,
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

    raw_payload: dict[str, Any] = {}
    if wrow and wrow.payload_json:
        try:
            parsed = json.loads(wrow.payload_json)
            if isinstance(parsed, dict):
                raw_payload = parsed
        except json.JSONDecodeError:
            raw_payload = {}
    categories = inventory_categories(raw_payload)

    payload = {
        "ok": True,
        "reachable": True,
        "last_sync": state or None,
        "applied_to_life": applied,
        "wearable_day": serialize_wearable_daily(wrow),
        "categories": categories,
        "authentic": authentic,
        "estimates": {
            "steps_to_exercise": "floor(steps / 100) minutes, capped at 180",
            "exercise_from_last_steps": exercise_est,
            "distance_to_outdoor": "floor(meters / 80) minutes, capped at 180",
            "stress_to_life": "Amazfit stress / 20 → Life 1–5",
            "sleep_quality": "watch score 0–100 → quality 1–5",
        },
        "storage": {
            "wearable_daily": "SQLite wearable_daily (full snapshot + raw categories)",
            "life_daily_log": "sleep, exercise, outdoor, stress, life_score",
            "hub_readings": "sleep_hours, steps, calories, heart_rate, spo2, stress, pai, distance_m, hrv, temperature",
            "sync_mirror": "data/wearables_last_sync.json",
            "ingest_sources": sorted(_LIFE_WRITE_SOURCES),
        },
    }
    _STATUS_CACHE = (time.monotonic(), payload)
    return payload


@router.get("/today")
def wearable_today(
    db: Session = Depends(get_db),
    _: None = Depends(require_wearable_key),
):
    from backend.planner.service import local_tz

    user = _owner(db)
    day = datetime.now(local_tz()).date()
    row = (
        db.query(WearableDaily)
        .filter(WearableDaily.user_id == user.id, WearableDaily.local_date == day)
        .first()
    )
    return {"ok": True, "day": serialize_wearable_daily(row)}


@router.get("/day/{local_date}")
def wearable_day(
    local_date: str,
    db: Session = Depends(get_db),
    _: None = Depends(require_wearable_key),
):
    user = _owner(db)
    try:
        day = date.fromisoformat(local_date[:10])
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid local_date") from e
    row = (
        db.query(WearableDaily)
        .filter(WearableDaily.user_id == user.id, WearableDaily.local_date == day)
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
    from backend.planner.service import local_tz

    user = _owner(db)
    host_today = datetime.now(local_tz()).date()
    # Preserve extras (hrv, workouts, HC records, bridge daily, …) then normalize.
    raw_in = body.model_dump(by_alias=True, exclude_none=False)
    coerced = coerce_ingest_body(raw_in)
    source = str(coerced.get("source") or body.source or "mini_program").strip()
    source_l = source.lower()

    day = resolve_ingest_day(
        {
            "local_date": coerced.get("local_date") or body.local_date,
            "source": source,
            "meta": coerced.get("meta") if isinstance(coerced.get("meta"), dict) else (body.meta or {}),
        },
        host_today=host_today,
    )

    apply_to_life = source_l in _LIFE_WRITE_SOURCES
    meta = dict(coerced.get("meta") or body.meta or {})
    tz_off = meta.get("tz_offset_min")
    if tz_off is None:
        tz_off = coerced.get("tz_offset_min")
    if tz_off is None:
        tz_off = body.tz_offset_min
    if tz_off is not None:
        meta["tz_offset_min"] = tz_off
    watch_local = coerced.get("local_date") or body.local_date
    if watch_local and not meta.get("watch_local_date"):
        meta["watch_local_date"] = str(watch_local)[:10]
    dump_id = coerced.get("dump_id") or body.dump_id
    checksum = coerced.get("checksum") or body.checksum
    if dump_id and not meta.get("dump_id"):
        meta["dump_id"] = dump_id
    if checksum and not meta.get("checksum"):
        meta["checksum"] = checksum
    # Manual dump / chunk identity validation (soft — missing is OK for web tests)
    chunk = meta.get("chunk") if isinstance(meta.get("chunk"), dict) else {}
    if chunk:
        part = chunk.get("part")
        total = chunk.get("total")
        if part is not None and total is not None:
            try:
                if int(part) < 1 or int(total) < 1 or int(part) > int(total):
                    raise HTTPException(status_code=400, detail="Invalid chunk part/total")
            except (TypeError, ValueError) as e:
                raise HTTPException(status_code=400, detail="Invalid chunk part/total") from e

    # Start from coerced dump (includes hrv/workouts/…), overlay known fields.
    payload: dict[str, Any] = {
        k: v
        for k, v in coerced.items()
        if v is not None and k not in ("health_connect_records", "records", "daily")
    }
    payload.update(
        {
            "dump": coerced.get("dump") or body.dump,
            "dump_id": dump_id or meta.get("dump_id"),
            "checksum": checksum or meta.get("checksum"),
            "meta": meta,
            "captured_at": coerced.get("captured_at") or body.captured_at,
            "local_date": day.isoformat(),
            "tz_offset_min": tz_off,
            "source": source,
        }
    )
    payload = {k: v for k, v in payload.items() if v is not None}

    applied = None
    if apply_to_life and payload:
        try:
            applied = upsert_wearable_daily(db, user, day, payload, source=source)
        except PayloadTooLarge as e:
            raise HTTPException(status_code=413, detail=str(e)) from e

    from backend.behavior.time_fmt import optional_hours_label, optional_minutes_label
    from backend.wearables.sitting import extract_sitting_minutes

    sleep_hours = (applied or {}).get("sleep_hours")
    if sleep_hours is None and body.sleep:
        sleep_hours = normalize_sleep_hours(body.sleep.total_min)
    steps_val = (applied or {}).get("steps")
    if steps_val is None and body.activity:
        steps_val = body.activity.steps
    sitting_min = (applied or {}).get("sitting_min")
    if sitting_min is None:
        sitting_min = extract_sitting_minutes(payload)
    exercise_min = (applied or {}).get("exercise_minutes")
    outdoor_min = (applied or {}).get("outdoor_minutes")
    try:
        tz_echo = int(tz_off) if tz_off is not None else None
    except (TypeError, ValueError):
        tz_echo = None
    watch_local = meta.get("watch_local_date") or (body.local_date[:10] if body.local_date else None)
    progress = None
    if chunk:
        progress = {
            "part": chunk.get("part"),
            "total": chunk.get("total"),
            "name": chunk.get("name") or chunk.get("id"),
        }

    duplicate = bool((applied or {}).get("duplicate") or (applied or {}).get("replayed"))
    try:
        from backend.behavior.comms_health import note_watch_ingest

        note_watch_ingest(source=str(source or "mini_program"))
    except Exception:
        pass
    _write_sync_state(
        {
            "last_ingest_at": datetime.now(timezone.utc).isoformat(),
            "last_source": source,
            "last_is_watch": apply_to_life and source_l in ("mini_program", "zepp", "amazfit"),
            "last_wrote_life": bool(apply_to_life and applied and not duplicate),
            "last_local_date": day.isoformat(),
            "last_watch_local_date": watch_local,
            "last_tz_offset_min": tz_echo,
            "last_captured_at": body.captured_at,
            "last_sleep_hours": sleep_hours,
            "last_sleep_label": optional_hours_label(sleep_hours),
            "last_sleep_score": int(body.sleep.score)
            if body.sleep and body.sleep.score is not None
            else None,
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
            "last_sitting_min": sitting_min,
            "last_sitting_label": optional_minutes_label(sitting_min),
            "last_battery": (applied or {}).get("battery_pct")
            or (body.battery.pct if body.battery else None),
            "last_exercise_minutes": exercise_min,
            "last_exercise_label": optional_minutes_label(exercise_min),
            "last_outdoor_minutes": outdoor_min,
            "last_outdoor_label": optional_minutes_label(outdoor_min),
            "last_dump_id": (applied or {}).get("dump_id") or meta.get("dump_id"),
            "last_chunk_id": (applied or {}).get("chunk_id") or meta.get("chunk_id"),
            "last_chunk_part": chunk.get("part") if chunk else None,
            "last_chunk_total": chunk.get("total") if chunk else None,
            "last_event_id": (applied or {}).get("event_id"),
            "last_duplicate": duplicate,
            "last_manual_dump": bool(meta.get("manual_dump")),
            "last_event": "ingest_replay" if duplicate else "ingest",
        }
    )

    return {
        "ok": True,
        "schema": body.schema_version,
        "source": source,
        "local_date": day.isoformat(),
        "watch_local_date": watch_local,
        "tz_offset_min": tz_echo,
        "captured_at": coerced.get("captured_at") or body.captured_at,
        "progress": progress,
        "categories": inventory_categories(payload),
        "sleep_hours": sleep_hours,
        "sleep_label": optional_hours_label(sleep_hours),
        "sitting_min": sitting_min,
        "sitting_label": optional_minutes_label(sitting_min),
        "wrote_life_tracker": bool(apply_to_life and applied),
        "duplicate": duplicate,
        "replayed": duplicate,
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

        # Sleep from wearable (today's sync covers last night ending this morning)
        from backend.models import WearableDaily
        from backend.planner.service import iso_utc as _iso
        from backend.wearables.sleep_window import parse_sleep_dict, sleep_datetimes

        for wd_day in (d, d - timedelta(days=1)):
            wd = (
                db.query(WearableDaily)
                .filter(
                    WearableDaily.user_id == user.id,
                    WearableDaily.local_date == wd_day,
                    WearableDaily.sleep_hours.isnot(None),
                    WearableDaily.sleep_hours > 0,
                )
                .first()
            )
            if not wd:
                continue
            sleep = parse_sleep_dict(wd.payload_json)
            window = sleep_datetimes(
                local_date=wd.local_date,
                sleep=sleep
                or {"total_min": int(float(wd.sleep_hours) * 60)},
                tz=tz_from_payload(wd.payload_json),
            )
            if not window:
                continue
            s_dt, e_dt = window
            # Only include if overlaps this calendar day
            if e_dt <= start_utc or s_dt >= end_utc:
                continue
            # Avoid duplicate if both today and yesterday rows cover same window
            if any(ev.get("id") == f"sleep:{wd.local_date.isoformat()}" for ev in events):
                continue
            events.append(
                {
                    "id": f"sleep:{wd.local_date.isoformat()}",
                    "title": f"Sleep ({float(wd.sleep_hours):.1f}h)",
                    "category": "sleep",
                    "start_at": _iso(s_dt),
                    "end_at": _iso(e_dt),
                    "status": "done",
                    "planned_minutes": int(float(wd.sleep_hours) * 60),
                    "color": "#6366f1",
                }
            )

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
        events.sort(key=lambda e: str(e.get("start_at") or ""))
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
