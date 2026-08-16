"""Persist full Zepp health snapshot → wearable_daily + Life Tracker + hub readings.

Manual health dumper (CALT Sync 4.0): field-aware merges, stale protection,
idempotent chunk replay, no JSON truncation corruption.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from backend.hub.services.ingest import insert_reading
from backend.hub.services.rollup import rebuild_daily_rollup
from backend.life.services.scoring import compute_life_score
from backend.models import LifeDailyLog, User
from backend.models.wearable_daily import WearableDaily, WearableIngestEvent

log = logging.getLogger("wearables.ingest")

MAX_PAYLOAD_CHARS = 200_000


class PayloadTooLarge(ValueError):
    """Reject oversize payloads instead of truncating JSON."""


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


def _parse_iso_dt(raw: Any) -> datetime | None:
    if raw is None:
        return None
    if isinstance(raw, datetime):
        dt = raw
    else:
        text = str(raw).strip()
        if not text:
            return None
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _sleep_is_valid(sleep: Any) -> bool:
    if not isinstance(sleep, dict):
        return False
    total = sleep.get("total_min")
    try:
        if total is not None and int(total) > 0:
            return True
    except (TypeError, ValueError):
        pass
    # Valid window even if total missing
    start = sleep.get("start_min")
    end = sleep.get("end_min")
    try:
        if start is not None and end is not None and int(end) > int(start) >= 0:
            return True
    except (TypeError, ValueError):
        pass
    stages = sleep.get("stages")
    return isinstance(stages, list) and len(stages) > 0


def _prefer_list(prior: Any, incoming: Any) -> Any:
    if not isinstance(incoming, list) or len(incoming) == 0:
        return prior if isinstance(prior, list) and prior else incoming
    if not isinstance(prior, list) or len(prior) == 0:
        return incoming
    return incoming if len(incoming) >= len(prior) else prior


def _merge_payload(prior: dict[str, Any], body: dict[str, Any]) -> dict[str, Any]:
    """Keep previously ingested dump keys when a chunk omits or invalidates them."""
    out: dict[str, Any] = dict(prior or {})
    for key, value in (body or {}).items():
        if value is None:
            continue
        if key == "sleep":
            if not _sleep_is_valid(value):
                continue
            prior_sleep = out.get("sleep") if isinstance(out.get("sleep"), dict) else {}
            merged_sleep = dict(prior_sleep)
            for sk, sv in value.items():
                if sv is None:
                    continue
                if sk in ("stages", "naps"):
                    merged_sleep[sk] = _prefer_list(merged_sleep.get(sk), sv)
                elif sk in ("total_min", "score", "deep_min", "nap_min"):
                    try:
                        if int(sv) <= 0 and _sleep_is_valid(prior_sleep):
                            continue
                    except (TypeError, ValueError):
                        pass
                    merged_sleep[sk] = sv
                elif sk in ("start_min", "end_min"):
                    try:
                        if int(sv) < 0 and _sleep_is_valid(prior_sleep):
                            continue
                    except (TypeError, ValueError):
                        pass
                    merged_sleep[sk] = sv
                else:
                    merged_sleep[sk] = sv
            out[key] = merged_sleep
            continue
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            merged = dict(out[key])
            for nested_key, nested_val in value.items():
                if nested_val is None:
                    continue
                if isinstance(nested_val, list):
                    merged[nested_key] = _prefer_list(merged.get(nested_key), nested_val)
                else:
                    merged[nested_key] = nested_val
            out[key] = merged
        elif isinstance(value, list):
            out[key] = _prefer_list(out.get(key), value)
        else:
            out[key] = value
    return out


def _mono_int(prior: int | None, incoming: int | None) -> int | None:
    if incoming is None:
        return prior
    if prior is None:
        return int(incoming)
    return max(int(prior), int(incoming))


def _mono_float(prior: float | None, incoming: float | None) -> float | None:
    if incoming is None:
        return prior
    if prior is None:
        return float(incoming)
    return max(float(prior), float(incoming))


def _resolve_replay_meta(body: dict[str, Any]) -> dict[str, Any]:
    meta = body.get("meta") if isinstance(body.get("meta"), dict) else {}
    chunk = meta.get("chunk") if isinstance(meta.get("chunk"), dict) else {}
    dump_id = meta.get("dump_id") or chunk.get("dump_id") or body.get("dump_id")
    chunk_id = meta.get("chunk_id") or chunk.get("chunk_id")
    checksum = meta.get("checksum") or chunk.get("checksum") or body.get("checksum")
    event_id = chunk_id or None
    if not event_id and dump_id:
        part = chunk.get("part") or 1
        event_id = f"{dump_id}:{part}"
    if not event_id and checksum:
        event_id = f"{body.get('local_date') or 'day'}:{checksum}"
    return {
        "dump_id": str(dump_id)[:80] if dump_id else None,
        "chunk_id": str(chunk_id)[:100] if chunk_id else None,
        "checksum": str(checksum)[:40] if checksum else None,
        "event_id": str(event_id)[:120] if event_id else None,
        "captured_at": _parse_iso_dt(body.get("captured_at") or meta.get("captured_at")),
    }


def _encode_payload(merged: dict[str, Any]) -> str:
    raw = json.dumps(merged, default=str)
    if len(raw) > MAX_PAYLOAD_CHARS:
        raise PayloadTooLarge(
            f"payload_json exceeds {MAX_PAYLOAD_CHARS} chars ({len(raw)}); reject instead of truncate"
        )
    return raw


def _safe_reading(
    db: Session,
    *,
    user_id: int,
    slug: str,
    value: float | None,
    source: str,
    client_event_id: str | None = None,
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
            client_event_id=client_event_id,
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


def _nap_minutes(sleep: dict[str, Any]) -> int:
    nap_min = 0
    explicit = sleep.get("nap_min")
    try:
        if explicit is not None:
            nap_min = max(0, int(explicit))
    except (TypeError, ValueError):
        nap_min = 0
    if nap_min:
        return nap_min
    for nap in sleep.get("naps") or []:
        if not isinstance(nap, dict):
            continue
        length = nap.get("length")
        if length is None:
            try:
                length = int(nap.get("stop") or 0) - int(nap.get("start") or 0)
            except (TypeError, ValueError):
                length = 0
        try:
            nap_min += max(0, int(length))
        except (TypeError, ValueError):
            pass
    return nap_min


def upsert_wearable_daily(
    db: Session,
    user: User,
    day: date,
    body: dict[str, Any],
    *,
    source: str = "mini_program",
) -> dict[str, Any]:
    """Store full snapshot + push mapped fields into Life Tracker + hub (central DB)."""
    replay = _resolve_replay_meta(body)
    event_id = replay["event_id"]

    if event_id:
        prior_event = (
            db.query(WearableIngestEvent)
            .filter(
                WearableIngestEvent.user_id == user.id,
                WearableIngestEvent.event_id == event_id,
            )
            .first()
        )
        if prior_event:
            row = (
                db.query(WearableDaily)
                .filter(WearableDaily.user_id == user.id, WearableDaily.local_date == day)
                .first()
            )
            life = (
                db.query(LifeDailyLog)
                .filter(LifeDailyLog.user_id == user.id, LifeDailyLog.date == day)
                .first()
            )
            return {
                "upserted": False,
                "duplicate": True,
                "replayed": True,
                "local_date": day.isoformat(),
                "sleep_hours": float(row.sleep_hours) if row and row.sleep_hours is not None else None,
                "sleep_quality": life.sleep_quality if life else None,
                "steps": row.steps if row else None,
                "exercise_minutes": life.exercise_minutes if life else None,
                "calories": row.calories if row else None,
                "distance_m": row.distance_m if row else None,
                "hr_last": row.hr_last if row else None,
                "spo2": row.spo2 if row else None,
                "stress": row.stress if row else None,
                "pai_today": row.pai_today if row else None,
                "stand_hours": row.stand_hours if row else None,
                "battery_pct": row.battery_pct if row else None,
                "sitting_min": None,
                "life_score": life.life_score if life else None,
                "outdoor_minutes": life.outdoor_minutes if life else None,
                "event_id": event_id,
            }

    # Size-check the incoming body before merge/storage
    incoming_raw = json.dumps(body or {}, default=str)
    if len(incoming_raw) > MAX_PAYLOAD_CHARS:
        raise PayloadTooLarge(
            f"ingest body exceeds {MAX_PAYLOAD_CHARS} chars ({len(incoming_raw)})"
        )

    sleep_in = body.get("sleep") if isinstance(body.get("sleep"), dict) else {}
    heart = body.get("heart") if isinstance(body.get("heart"), dict) else {}
    activity = body.get("activity") if isinstance(body.get("activity"), dict) else {}
    calorie = body.get("calorie") if isinstance(body.get("calorie"), dict) else {}
    distance = body.get("distance") if isinstance(body.get("distance"), dict) else {}
    spo2 = body.get("spo2") if isinstance(body.get("spo2"), dict) else {}
    stress = body.get("stress") if isinstance(body.get("stress"), dict) else {}
    pai = body.get("pai") if isinstance(body.get("pai"), dict) else {}
    stand = body.get("stand") if isinstance(body.get("stand"), dict) else {}
    battery = body.get("battery") if isinstance(body.get("battery"), dict) else {}
    fat_burn = body.get("fat_burn") if isinstance(body.get("fat_burn"), dict) else {}

    sleep_hours = normalize_sleep_hours(sleep_in.get("total_min")) if _sleep_is_valid(sleep_in) else None
    sleep_score = sleep_in.get("score") if _sleep_is_valid(sleep_in) else None
    sleep_deep = sleep_in.get("deep_min") if _sleep_is_valid(sleep_in) else None
    nap_min = _nap_minutes(sleep_in) if _sleep_is_valid(sleep_in) else 0
    if nap_min >= 10 and sleep_hours is not None:
        sleep_hours = round(min(16.0, sleep_hours + nap_min / 60.0), 2)
    elif nap_min >= 10 and sleep_hours is None:
        sleep_hours = round(min(16.0, nap_min / 60.0), 2)
    if sleep_hours is not None and sleep_hours <= 0:
        sleep_hours = None
    if sleep_score is not None:
        try:
            if int(sleep_score) <= 0 and sleep_hours is None:
                sleep_score = None
        except (TypeError, ValueError):
            sleep_score = None

    steps_i = int(activity["steps"]) if activity.get("steps") is not None else None
    kcal = int(calorie["kcal"]) if calorie.get("kcal") is not None else None
    dist_m = int(distance["meters"]) if distance.get("meters") is not None else None
    spo2_v = int(spo2["value"]) if spo2.get("value") is not None else None
    stress_v = int(stress["value"]) if stress.get("value") is not None else None
    src = ("zepp_" + source)[:40]

    row = (
        db.query(WearableDaily)
        .filter(WearableDaily.user_id == user.id, WearableDaily.local_date == day)
        .first()
    )
    if not row:
        row = WearableDaily(user_id=user.id, local_date=day)
        db.add(row)

    prior_payload: dict[str, Any] = {}
    if row.payload_json:
        try:
            prior_payload = json.loads(row.payload_json) or {}
        except json.JSONDecodeError:
            prior_payload = {}

    incoming_captured = replay["captured_at"]
    prior_captured = row.last_captured_at
    if prior_captured and prior_captured.tzinfo is None:
        prior_captured = prior_captured.replace(tzinfo=timezone.utc)
    stale = bool(
        incoming_captured
        and prior_captured
        and incoming_captured < prior_captured
    )

    merged_body = _merge_payload(prior_payload, body)
    # Re-derive sleep scalars from merged sleep when chunk omitted hours
    merged_sleep = merged_body.get("sleep") if isinstance(merged_body.get("sleep"), dict) else {}
    if sleep_hours is None and _sleep_is_valid(merged_sleep):
        sleep_hours = normalize_sleep_hours(merged_sleep.get("total_min"))
        nap2 = _nap_minutes(merged_sleep)
        if nap2 >= 10:
            base = sleep_hours or 0.0
            sleep_hours = round(min(16.0, base + nap2 / 60.0), 2)
        if sleep_score is None:
            sleep_score = merged_sleep.get("score")
        if sleep_deep is None:
            sleep_deep = merged_sleep.get("deep_min")

    row.source = source[:40]

    if sleep_hours is not None:
        # Never regress sleep hours (partial/zero/stale chunks keep prior)
        row.sleep_hours = _mono_float(
            float(row.sleep_hours) if row.sleep_hours is not None else None,
            float(sleep_hours),
        )
    if sleep_score is not None and (not stale or row.sleep_score is None):
        try:
            if int(sleep_score) > 0:
                row.sleep_score = int(sleep_score)
        except (TypeError, ValueError):
            pass
    if sleep_deep is not None and (not stale or row.sleep_deep_min is None):
        try:
            if int(sleep_deep) > 0:
                row.sleep_deep_min = int(sleep_deep)
        except (TypeError, ValueError):
            pass

    # Cumulative metrics: monotonic + stale-safe
    row.steps = _mono_int(row.steps, steps_i)
    if activity.get("target") is not None and (not stale or row.step_target is None):
        row.step_target = activity.get("target")
    row.calories = _mono_int(row.calories, kcal)
    if calorie.get("target") is not None and (not stale or row.calorie_target is None):
        row.calorie_target = calorie.get("target")
    row.distance_m = _mono_int(row.distance_m, dist_m)

    if heart.get("last") is not None and (not stale or row.hr_last is None):
        row.hr_last = heart.get("last")
    if heart.get("resting") is not None and (not stale or row.hr_resting is None):
        row.hr_resting = heart.get("resting")
    if spo2_v is not None and (not stale or row.spo2 is None):
        row.spo2 = spo2_v
    if stress_v is not None and (not stale or row.stress is None):
        row.stress = stress_v
    if pai.get("today") is not None:
        row.pai_today = _mono_float(
            float(row.pai_today) if row.pai_today is not None else None,
            float(pai["today"]),
        )
    if pai.get("total") is not None:
        row.pai_total = _mono_float(
            float(row.pai_total) if row.pai_total is not None else None,
            float(pai["total"]),
        )
    stand_h = stand.get("hours")
    if stand_h is not None:
        row.stand_hours = _mono_int(row.stand_hours, int(stand_h))
    if stand.get("target") is not None and (not stale or row.stand_target is None):
        row.stand_target = stand.get("target")
    if battery.get("pct") is not None and (not stale or row.battery_pct is None):
        row.battery_pct = battery.get("pct")

    row.payload_json = _encode_payload(merged_body)
    row.synced_at = datetime.now(timezone.utc)
    if incoming_captured and (not prior_captured or incoming_captured >= prior_captured):
        row.last_captured_at = incoming_captured
    if replay["dump_id"]:
        row.last_dump_id = replay["dump_id"]
    if replay["chunk_id"]:
        row.last_chunk_id = replay["chunk_id"]
    if replay["checksum"]:
        row.last_checksum = replay["checksum"]

    from backend.wearables.sitting import extract_sitting_minutes

    sitting_min = extract_sitting_minutes(merged_body)
    effective_sleep_h = float(row.sleep_hours) if row.sleep_hours is not None else None

    # --- Life Tracker (historical-day aware: keyed by wearable local_date) ---
    life = (
        db.query(LifeDailyLog)
        .filter(LifeDailyLog.user_id == user.id, LifeDailyLog.date == day)
        .first()
    )
    if not life:
        life = LifeDailyLog(user_id=user.id, date=day)
        db.add(life)

    if sleep_hours is not None and effective_sleep_h is not None:
        # Align life sleep with wearable row (already stale-protected)
        life.sleep_hours = effective_sleep_h
        if sleep_score is not None or merged_sleep.get("score") is not None:
            life.sleep_quality = score_to_quality(
                sleep_score if sleep_score is not None else merged_sleep.get("score")
            )

    if row.steps is not None:
        exercise = min(180, int(row.steps) // 100)
        if exercise > (life.exercise_minutes or 0):
            life.exercise_minutes = exercise

    if row.distance_m is not None:
        outdoor = min(180, int(row.distance_m) // 80)
        if outdoor > (life.outdoor_minutes or 0):
            life.outdoor_minutes = outdoor

    life_stress = stress_to_life(stress_v if isinstance(stress_v, (int, float)) else None)
    if life_stress is not None and (not stale or life.stress_level is None):
        life.stress_level = life_stress

    life.life_score = compute_life_score(**_life_score_payload(life))

    if event_id:
        db.add(
            WearableIngestEvent(
                user_id=user.id,
                event_id=event_id,
                local_date=day,
                dump_id=replay["dump_id"],
                chunk_id=replay["chunk_id"],
                checksum=replay["checksum"],
                captured_at=incoming_captured,
                accepted_at=datetime.now(timezone.utc),
            )
        )

    db.commit()
    db.refresh(row)
    db.refresh(life)

    # --- Hub readings (stable client_event_id → duplicate-safe) ---
    eid = event_id or f"day:{day.isoformat()}:{row.last_dump_id or 'na'}"

    def hub_id(slug: str) -> str:
        return f"zepp:{day.isoformat()}:{slug}:{eid}"[:120]

    _safe_reading(
        db, user_id=user.id, slug="sleep_hours", value=effective_sleep_h, source=src, client_event_id=hub_id("sleep_hours")
    )
    _safe_reading(
        db,
        user_id=user.id,
        slug="steps",
        value=float(row.steps) if row.steps is not None else None,
        source=src,
        client_event_id=hub_id("steps"),
    )
    _safe_reading(
        db,
        user_id=user.id,
        slug="calories",
        value=float(row.calories) if row.calories is not None else None,
        source=src,
        client_event_id=hub_id("calories"),
    )
    _safe_reading(
        db,
        user_id=user.id,
        slug="heart_rate",
        value=float(row.hr_last) if row.hr_last is not None else None,
        source=src,
        client_event_id=hub_id("heart_rate"),
    )
    _safe_reading(
        db,
        user_id=user.id,
        slug="spo2",
        value=float(row.spo2) if row.spo2 is not None else None,
        source=src,
        client_event_id=hub_id("spo2"),
    )
    _safe_reading(
        db,
        user_id=user.id,
        slug="stress",
        value=float(row.stress) if row.stress is not None else None,
        source=src,
        client_event_id=hub_id("stress"),
    )
    _safe_reading(
        db,
        user_id=user.id,
        slug="pai",
        value=float(row.pai_today) if row.pai_today is not None else None,
        source=src,
        client_event_id=hub_id("pai"),
    )
    _safe_reading(
        db,
        user_id=user.id,
        slug="distance_m",
        value=float(row.distance_m) if row.distance_m is not None else None,
        source=src,
        client_event_id=hub_id("distance_m"),
    )
    fat_m = fat_burn.get("minutes")
    _safe_reading(
        db,
        user_id=user.id,
        slug="fat_burn_min",
        value=float(fat_m) if fat_m is not None else None,
        source=src,
        client_event_id=hub_id("fat_burn_min"),
    )
    if row.hr_resting is not None:
        _safe_reading(
            db,
            user_id=user.id,
            slug="hr_resting",
            value=float(row.hr_resting),
            source=src,
            client_event_id=hub_id("hr_resting"),
        )
    if row.stand_hours is not None:
        _safe_reading(
            db,
            user_id=user.id,
            slug="stand_hours",
            value=float(row.stand_hours),
            source=src,
            client_event_id=hub_id("stand_hours"),
        )

    for d in (day - timedelta(days=1), day, day + timedelta(days=1)):
        try:
            rebuild_daily_rollup(db, user.id, d)
        except Exception as exc:  # noqa: BLE001
            log.warning("rebuild_daily_rollup failed day=%s: %s", d, exc)

    return {
        "upserted": True,
        "duplicate": False,
        "replayed": False,
        "stale_ignored": stale,
        "local_date": day.isoformat(),
        "sleep_hours": effective_sleep_h,
        "sleep_quality": life.sleep_quality,
        "steps": row.steps,
        "exercise_minutes": life.exercise_minutes,
        "calories": row.calories,
        "distance_m": row.distance_m,
        "hr_last": row.hr_last,
        "spo2": row.spo2,
        "stress": row.stress,
        "pai_today": row.pai_today,
        "stand_hours": row.stand_hours,
        "battery_pct": row.battery_pct,
        "sitting_min": sitting_min,
        "life_score": life.life_score,
        "outdoor_minutes": life.outdoor_minutes,
        "event_id": event_id,
        "dump_id": replay["dump_id"],
        "chunk_id": replay["chunk_id"],
    }


def sleep_load_scale_for_user(db: Session, user_id: int) -> tuple[float, dict[str, Any] | None]:
    """
    Soften planner load from last night's wearable sleep.

    ≥7h → 1.0 · 6–7h → 0.9 · 5–6h → 0.85 · <5h → 0.8
    """
    from backend.planner.service import local_tz

    today = datetime.now(local_tz()).date()
    row = (
        db.query(WearableDaily)
        .filter(WearableDaily.user_id == user_id, WearableDaily.local_date <= today)
        .order_by(WearableDaily.local_date.desc())
        .first()
    )
    if not row or row.sleep_hours is None:
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
    from backend.wearables.sitting import extract_sitting_minutes

    caps = None
    if isinstance(payload, dict):
        caps = payload.get("capabilities")

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
        "sitting_min": extract_sitting_minutes(payload) if isinstance(payload, dict) else None,
        "last_captured_at": row.last_captured_at.isoformat() if row.last_captured_at else None,
        "last_dump_id": row.last_dump_id,
        "last_chunk_id": row.last_chunk_id,
        "last_checksum": row.last_checksum,
        "capabilities": caps,
        "payload": payload,
    }
