"""Persist full Zepp health snapshot → wearable_daily + Life Tracker + hub readings."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from backend.hub.services.ingest import insert_reading
from backend.hub.services.rollup import rebuild_daily_rollup
from backend.life.services.scoring import compute_life_score
from backend.models import LifeDailyLog, User
from backend.models.wearable_daily import WearableDaily


def score_to_quality(score: int | None) -> int:
    if score is None:
        return 3
    return max(1, min(5, int(round(score / 20)) or 1))


def stress_to_life(stress: int | None) -> int | None:
    """Map Amazfit stress (~1–100) → Life Tracker 1–5."""
    if stress is None:
        return None
    s = max(0, int(stress))
    if s <= 0:
        return None
    return max(1, min(5, int(round(s / 20)) or 1))


def normalize_sleep_hours(total_min: int | None) -> float | None:
    if total_min is None:
        return None
    return round(max(0.0, min(16.0, float(total_min) / 60.0)), 2)


def _safe_reading(
    db: Session,
    *,
    user_id: int,
    slug: str,
    value: float | None,
    source: str,
) -> bool:
    if value is None:
        return False
    try:
        insert_reading(
            db,
            user_id=user_id,
            slug=slug,
            value_numeric=float(value),
            source_device=source[:40],
        )
        return True
    except Exception:
        return False


def _life_score_payload(row: LifeDailyLog) -> dict[str, Any]:
    defaults = {
        "sleep_hours": 0.0,
        "sleep_quality": 3,
        "exercise_minutes": 0,
        "water_glasses": 0,
        "meals_healthy": 0,
        "study_minutes": 0,
        "tasks_completed": 0,
        "deep_work_blocks": 0,
        "screen_time_hours": 0.0,
        "social_media_minutes": 0,
        "outdoor_minutes": 0,
        "mood_score": 3,
        "stress_level": 3,
        "meditation_minutes": 0,
    }
    out = {}
    for key, default in defaults.items():
        val = getattr(row, key, default)
        out[key] = default if val is None else val
    return out


def upsert_wearable_daily(
    db: Session,
    user: User,
    day: date,
    body: dict[str, Any],
    *,
    source: str = "mini_program",
) -> dict[str, Any]:
    """Store full snapshot + push mapped fields into Life Tracker / hub."""
    sleep = body.get("sleep") or {}
    heart = body.get("heart") or {}
    activity = body.get("activity") or {}
    calorie = body.get("calorie") or {}
    distance = body.get("distance") or {}
    spo2 = body.get("spo2") or {}
    stress = body.get("stress") or {}
    pai = body.get("pai") or {}
    stand = body.get("stand") or {}
    battery = body.get("battery") or {}

    sleep_hours = normalize_sleep_hours(sleep.get("total_min"))
    steps = activity.get("steps")
    steps_i = int(steps) if steps is not None else None
    kcal = calorie.get("kcal")
    dist_m = distance.get("meters")
    spo2_v = spo2.get("value")
    stress_v = stress.get("value")
    src = ("zepp_" + source)[:40]

    row = (
        db.query(WearableDaily)
        .filter(WearableDaily.user_id == user.id, WearableDaily.local_date == day)
        .first()
    )
    if not row:
        row = WearableDaily(user_id=user.id, local_date=day)
        db.add(row)

    row.source = source[:40]
    row.sleep_hours = sleep_hours
    row.sleep_score = sleep.get("score")
    row.sleep_deep_min = sleep.get("deep_min")
    row.steps = steps_i
    row.step_target = activity.get("target")
    row.calories = int(kcal) if kcal is not None else None
    row.calorie_target = calorie.get("target")
    row.distance_m = int(dist_m) if dist_m is not None else None
    row.hr_last = heart.get("last")
    row.hr_resting = heart.get("resting")
    row.spo2 = int(spo2_v) if spo2_v is not None else None
    row.stress = int(stress_v) if stress_v is not None else None
    row.pai_today = float(pai["today"]) if pai.get("today") is not None else None
    row.pai_total = float(pai["total"]) if pai.get("total") is not None else None
    row.stand_hours = stand.get("hours")
    row.stand_target = stand.get("target")
    row.battery_pct = battery.get("pct")
    row.payload_json = json.dumps(body, default=str)[:100_000]
    row.synced_at = datetime.now(timezone.utc)

    # --- Life Tracker ---
    life = (
        db.query(LifeDailyLog)
        .filter(LifeDailyLog.user_id == user.id, LifeDailyLog.date == day)
        .first()
    )
    if not life:
        life = LifeDailyLog(user_id=user.id, date=day)
        db.add(life)

    if sleep_hours is not None:
        life.sleep_hours = sleep_hours
        life.sleep_quality = score_to_quality(sleep.get("score"))

    if steps_i is not None:
        exercise = min(180, steps_i // 100)
        if exercise > (life.exercise_minutes or 0):
            life.exercise_minutes = exercise

    if dist_m is not None:
        # ~80m ≈ 1 outdoor minute (cap 180)
        outdoor = min(180, int(dist_m) // 80)
        if outdoor > (life.outdoor_minutes or 0):
            life.outdoor_minutes = outdoor

    life_stress = stress_to_life(stress_v if isinstance(stress_v, (int, float)) else None)
    if life_stress is not None:
        life.stress_level = life_stress

    life.life_score = compute_life_score(**_life_score_payload(life))
    db.commit()
    db.refresh(row)
    db.refresh(life)

    # --- Hub readings ---
    _safe_reading(db, user_id=user.id, slug="sleep_hours", value=sleep_hours, source=src)
    _safe_reading(db, user_id=user.id, slug="steps", value=float(steps_i) if steps_i is not None else None, source=src)
    _safe_reading(db, user_id=user.id, slug="calories", value=float(kcal) if kcal is not None else None, source=src)
    _safe_reading(db, user_id=user.id, slug="heart_rate", value=float(heart["last"]) if heart.get("last") is not None else None, source=src)
    _safe_reading(db, user_id=user.id, slug="spo2", value=float(spo2_v) if spo2_v is not None else None, source=src)
    _safe_reading(db, user_id=user.id, slug="stress", value=float(stress_v) if stress_v is not None else None, source=src)
    _safe_reading(db, user_id=user.id, slug="pai", value=float(pai["today"]) if pai.get("today") is not None else None, source=src)
    _safe_reading(db, user_id=user.id, slug="distance_m", value=float(dist_m) if dist_m is not None else None, source=src)

    try:
        rebuild_daily_rollup(db, user.id, day)
    except Exception:
        pass

    return {
        "upserted": True,
        "local_date": day.isoformat(),
        "sleep_hours": sleep_hours,
        "sleep_quality": life.sleep_quality,
        "steps": steps_i,
        "exercise_minutes": life.exercise_minutes,
        "calories": row.calories,
        "distance_m": row.distance_m,
        "hr_last": row.hr_last,
        "spo2": row.spo2,
        "stress": row.stress,
        "pai_today": row.pai_today,
        "stand_hours": row.stand_hours,
        "battery_pct": row.battery_pct,
        "life_score": life.life_score,
        "outdoor_minutes": life.outdoor_minutes,
    }


def sleep_load_scale_for_user(db: Session, user_id: int) -> tuple[float, dict[str, Any] | None]:
    """
    Soften planner load from last night's wearable sleep.

    ≥7h → 1.0 · 6–7h → 0.9 · 5–6h → 0.85 · <5h → 0.8
    """
    today = date.today()
    row = (
        db.query(WearableDaily)
        .filter(WearableDaily.user_id == user_id, WearableDaily.local_date <= today)
        .order_by(WearableDaily.local_date.desc())
        .first()
    )
    if not row or row.sleep_hours is None:
        # fallback Life Tracker
        life = (
            db.query(LifeDailyLog)
            .filter(LifeDailyLog.user_id == user_id, LifeDailyLog.date <= today)
            .order_by(LifeDailyLog.date.desc())
            .first()
        )
        if not life or not life.sleep_hours:
            return 1.0, None
        hours = float(life.sleep_hours)
        meta = {"source": "life_daily_log", "sleep_hours": hours, "date": life.date.isoformat()}
    else:
        hours = float(row.sleep_hours)
        meta = {
            "source": "wearable_daily",
            "sleep_hours": hours,
            "sleep_score": row.sleep_score,
            "date": row.local_date.isoformat(),
        }

    if hours >= 7.0:
        scale = 1.0
    elif hours >= 6.0:
        scale = 0.9
    elif hours >= 5.0:
        scale = 0.85
    else:
        scale = 0.8
    meta["sleep_load_scale"] = scale
    return scale, meta


def serialize_wearable_daily(row: WearableDaily | None) -> dict[str, Any] | None:
    if not row:
        return None
    payload = None
    if row.payload_json:
        try:
            payload = json.loads(row.payload_json)
        except Exception:
            payload = None
    return {
        "local_date": row.local_date.isoformat(),
        "source": row.source,
        "synced_at": row.synced_at.isoformat() if row.synced_at else None,
        "sleep_hours": row.sleep_hours,
        "sleep_score": row.sleep_score,
        "sleep_deep_min": row.sleep_deep_min,
        "steps": row.steps,
        "step_target": row.step_target,
        "calories": row.calories,
        "calorie_target": row.calorie_target,
        "distance_m": row.distance_m,
        "hr_last": row.hr_last,
        "hr_resting": row.hr_resting,
        "spo2": row.spo2,
        "stress": row.stress,
        "pai_today": row.pai_today,
        "pai_total": row.pai_total,
        "stand_hours": row.stand_hours,
        "stand_target": row.stand_target,
        "battery_pct": row.battery_pct,
        "payload": payload,
    }
