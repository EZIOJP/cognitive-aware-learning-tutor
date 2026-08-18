"""Resolve Zepp sleep start/end into absolute bouts, then clip per calendar day.

Zepp Sleep.getInfo() reports startTime/endTime as minutes from 00:00 of the
*sleep onset* day (same base). endTime may exceed 1440 when sleep crosses
midnight. Wearable `local_date` is usually the wake / sync day.

Model
-----
1. Build absolute [start_dt, end_dt] by trying onset anchors (wake day and
   wake day − 1) and picking the fit that matches total_min and prefers wake
   on `local_date`.
2. For any calendar day D, clip that bout to D → 0..1 ring wedge(s).
   Overnight sleep naturally paints evening on D−1 and morning on D.
3. Duration-only (no start/end) → stats only, no invented bedtime wedge.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta, time
from typing import Any
from zoneinfo import ZoneInfo

from backend.planner.service import local_tz


def _as_int(v: Any) -> int | None:
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def parse_sleep_dict(payload: dict[str, Any] | str | None) -> dict[str, Any]:
    if payload is None:
        return {}
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            return {}
    if not isinstance(payload, dict):
        return {}
    sleep = payload.get("sleep")
    return sleep if isinstance(sleep, dict) else {}


def _normalize_offsets(
    start_min: int | None,
    end_min: int | None,
    total_min: int,
) -> tuple[int, int] | None:
    """Fill missing start/end from total when possible; fix wrap-around."""
    if start_min is not None and end_min is not None and end_min >= 0:
        if end_min < start_min and total_min > 0:
            end_min = start_min + total_min
        return start_min, end_min
    if start_min is not None and total_min > 0:
        return start_min, start_min + total_min
    if end_min is not None and end_min >= 0 and total_min > 0:
        return end_min - total_min, end_min
    return None


def _window_on_anchor(
    anchor: date,
    start_min: int,
    end_min: int,
    total_min: int,
    tz: ZoneInfo,
) -> tuple[datetime, datetime] | None:
    start_dt = datetime.combine(anchor, time.min, tzinfo=tz) + timedelta(minutes=start_min)
    end_dt = datetime.combine(anchor, time.min, tzinfo=tz) + timedelta(minutes=end_min)
    if end_dt <= start_dt and total_min > 0:
        end_dt = start_dt + timedelta(minutes=total_min)
    if end_dt <= start_dt:
        return None
    return start_dt, end_dt


def _score_window(
    *,
    start_dt: datetime,
    end_dt: datetime,
    local_date: date,
    total_min: int,
) -> float | None:
    """Higher is better. None = reject."""
    dur_min = (end_dt - start_dt).total_seconds() / 60.0
    if dur_min < 5 or dur_min > 16 * 60:
        return None
    if total_min > 0 and abs(dur_min - total_min) > 45:
        return None

    start_d = start_dt.date()
    end_d = end_dt.date()
    score = 0.0

    # Prefer wake on the wearable sync / wake day
    if end_d == local_date:
        score += 20.0
    elif end_d == local_date - timedelta(days=1):
        score += 4.0  # rare: record attributed early
    else:
        score -= 8.0

    # Overnight: bedtime previous evening, wake today
    if start_d == local_date - timedelta(days=1) and end_d == local_date:
        score += 12.0
    # Same calendar day (nap or after-midnight-only sleep)
    elif start_d == local_date and end_d == local_date:
        score += 10.0
    # Started and ended yesterday (nap yesterday still on that row)
    elif start_d == end_d == local_date - timedelta(days=1):
        score += 3.0

    # Mild preference for evening bedtimes on overnight bouts
    if start_d < end_d and start_dt.hour >= 18:
        score += 2.0
    if start_d < end_d and 0 <= start_dt.hour < 12:
        score += 1.0  # fell asleep after midnight, still overnight

    # Duration closeness bonus
    if total_min > 0:
        score += max(0.0, 5.0 - abs(dur_min - total_min) / 10.0)

    return score


def sleep_datetimes(
    *,
    local_date: date,
    sleep: dict[str, Any] | None,
    tz: ZoneInfo | None = None,
) -> tuple[datetime, datetime] | None:
    """
    Convert Zepp start_min/end_min (+ total_min) into aware local datetimes.

    Tries onset anchors on `local_date` and `local_date - 1`, scores by
    duration fit + wake-day preference. No fixed \"sleep starts at midnight\".
    """
    tz = tz or local_tz()
    sleep = sleep or {}
    start_min = _as_int(sleep.get("start_min"))
    end_min = _as_int(sleep.get("end_min"))
    total_min = _as_int(sleep.get("total_min")) or 0

    if total_min <= 0 and (start_min is None or end_min is None or (end_min is not None and end_min < 0)):
        return None

    offsets = _normalize_offsets(start_min, end_min if end_min is not None and end_min >= 0 else None, total_min)
    if offsets is None:
        return None
    start_off, end_off = offsets
    if total_min <= 0:
        total_min = max(0, end_off - start_off)

    best: tuple[float, datetime, datetime] | None = None
    for anchor in (local_date, local_date - timedelta(days=1)):
        window = _window_on_anchor(anchor, start_off, end_off, total_min, tz)
        if not window:
            continue
        start_dt, end_dt = window
        score = _score_window(
            start_dt=start_dt,
            end_dt=end_dt,
            local_date=local_date,
            total_min=total_min,
        )
        if score is None:
            continue
        if best is None or score > best[0]:
            best = (score, start_dt, end_dt)

    if best is None:
        return None
    return best[1], best[2]


def _score_nap_window(
    *,
    start_dt: datetime,
    end_dt: datetime,
    local_date: date,
    total_min: int,
) -> float | None:
    """Score nap placements. Prefer ending on wearable wake day; reject wild futures."""
    dur_min = (end_dt - start_dt).total_seconds() / 60.0
    if dur_min < 10 or dur_min > 12 * 60:
        return None
    if total_min > 0 and abs(dur_min - total_min) > 30:
        return None

    start_d = start_dt.date()
    end_d = end_dt.date()
    # Reject naps that land entirely after the wake day (common mis-anchor for ≥1440 offsets)
    if start_d > local_date:
        return None

    score = 0.0
    if end_d == local_date:
        score += 20.0
    elif end_d == local_date - timedelta(days=1):
        score += 4.0
    else:
        score -= 12.0

    if start_d == end_d == local_date:
        score += 10.0
    elif start_d == local_date - timedelta(days=1) and end_d == local_date:
        score += 8.0
    elif start_d == end_d == local_date - timedelta(days=1):
        score += 3.0

    if total_min > 0:
        score += max(0.0, 5.0 - abs(dur_min - total_min) / 10.0)
    return score


def nap_datetimes(
    *,
    local_date: date,
    sleep: dict[str, Any] | None,
    tz: ZoneInfo | None = None,
) -> list[tuple[datetime, datetime]]:
    """Zepp getNap() entries — minute offsets; try wake-day and wake-day−1 anchors.

    Large start/stop values (≥1440) are often relative to the sleep-onset day, not
    the wearable sync day. Scoring prefers naps that end on ``local_date``.
    """
    tz = tz or local_tz()
    sleep = sleep or {}
    out: list[tuple[datetime, datetime]] = []
    raw = sleep.get("naps") or []
    if not isinstance(raw, list):
        return out
    for nap in raw:
        if not isinstance(nap, dict):
            continue
        start_m = _as_int(nap.get("start") if nap.get("start") is not None else nap.get("start_min"))
        stop_m = _as_int(
            nap.get("stop")
            if nap.get("stop") is not None
            else nap.get("end_min")
            if nap.get("end_min") is not None
            else nap.get("end")
        )
        length = _as_int(nap.get("length")) or 0
        if start_m is None:
            continue
        if stop_m is None or stop_m <= start_m:
            if length > 0:
                stop_m = start_m + length
            else:
                continue
        total_min = length if length > 0 else max(0, stop_m - start_m)
        best: tuple[float, datetime, datetime] | None = None
        for anchor in (local_date, local_date - timedelta(days=1)):
            window = _window_on_anchor(anchor, start_m, stop_m, total_min, tz)
            if not window:
                continue
            start_dt, end_dt = window
            score = _score_nap_window(
                start_dt=start_dt,
                end_dt=end_dt,
                local_date=local_date,
                total_min=total_min,
            )
            if score is None:
                continue
            if best is None or score > best[0]:
                best = (score, start_dt, end_dt)
        if best is None:
            continue
        out.append((best[1], best[2]))
    return out


def sleep_bouts(
    *,
    local_date: date,
    sleep: dict[str, Any] | None,
    tz: ZoneInfo | None = None,
) -> list[tuple[datetime, datetime]]:
    """Main overnight/day sleep + naps as absolute windows."""
    tz = tz or local_tz()
    bouts: list[tuple[datetime, datetime]] = []
    main = sleep_datetimes(local_date=local_date, sleep=sleep, tz=tz)
    if main:
        bouts.append(main)
    bouts.extend(nap_datetimes(local_date=local_date, sleep=sleep, tz=tz))
    # Merge overlaps
    if not bouts:
        return []
    bouts.sort(key=lambda w: w[0])
    merged: list[tuple[datetime, datetime]] = [bouts[0]]
    for s, e in bouts[1:]:
        ps, pe = merged[-1]
        if s <= pe + timedelta(minutes=1):
            merged[-1] = (ps, max(pe, e))
        else:
            merged.append((s, e))
    return merged


def hours_on_calendar_day(
    day: date,
    start_dt: datetime,
    end_dt: datetime,
    *,
    tz: ZoneInfo | None = None,
) -> tuple[float, float] | None:
    """Clip [start_dt, end_dt] to `day` → (startHour, endHour) in [0, 24]."""
    tz = tz or local_tz()
    if start_dt.tzinfo is None:
        start_dt = start_dt.replace(tzinfo=tz)
    if end_dt.tzinfo is None:
        end_dt = end_dt.replace(tzinfo=tz)
    day_start = datetime.combine(day, time.min, tzinfo=tz)
    day_end = day_start + timedelta(days=1)
    s = max(start_dt.astimezone(tz), day_start)
    e = min(end_dt.astimezone(tz), day_end)
    if e <= s:
        return None
    return (
        (s - day_start).total_seconds() / 3600.0,
        (e - day_start).total_seconds() / 3600.0,
    )


def ring_clips_for_bout(
    day: date,
    start_dt: datetime,
    end_dt: datetime,
    *,
    tz: ZoneInfo | None = None,
) -> list[dict[str, Any]]:
    """
    Clips to paint on the life-clock for `day`.

    True calendar intersection only: overnight sleep paints evening on the bed
    day and morning on the wake day. Never wraps yesterday's bedtime onto
    today's evening sector (that corrupted \"tonight\").
    """
    clipped = hours_on_calendar_day(day, start_dt, end_dt, tz=tz)
    if not clipped:
        return []
    return [
        {
            "startHour": clipped[0],
            "endHour": clipped[1],
            "crossesMidnight": False,
        }
    ]


def partition_around_sleep(
    start: datetime,
    end: datetime,
    sleep_bouts_list: list[tuple[datetime, datetime]],
) -> list[tuple[datetime, datetime, bool]]:
    """Split [start, end] into pieces marked idle-during-sleep (True) or awake (False)."""
    if end <= start:
        return []
    if not sleep_bouts_list:
        return [(start, end, False)]

    sleeps = sorted(sleep_bouts_list, key=lambda w: w[0])
    pieces: list[tuple[datetime, datetime, bool]] = []
    cursor = start
    for ss, se in sleeps:
        if se <= cursor:
            continue
        if ss >= end:
            break
        a = max(ss, start)
        b = min(se, end)
        if a > cursor:
            pieces.append((cursor, a, False))
        if b > a:
            pieces.append((a, b, True))
        cursor = max(cursor, b)
    if cursor < end:
        pieces.append((cursor, end, False))
    return [(a, b, idle) for a, b, idle in pieces if b > a]


def subtract_intervals(
    base: list[tuple[datetime, datetime]],
    cutouts: list[tuple[datetime, datetime]],
) -> list[tuple[datetime, datetime]]:
    """Return base intervals with cutouts removed (wall-clock)."""
    if not base:
        return []
    if not cutouts:
        return list(base)
    out: list[tuple[datetime, datetime]] = []
    for a, b in base:
        pieces = [(a, b)]
        for cs, ce in cutouts:
            nxt: list[tuple[datetime, datetime]] = []
            for x, y in pieces:
                if y <= cs or x >= ce:
                    nxt.append((x, y))
                    continue
                if x < cs:
                    nxt.append((x, cs))
                if y > ce:
                    nxt.append((ce, y))
            pieces = [(x, y) for x, y in nxt if y > x]
        out.extend(pieces)
    return out


def sleep_bouts_for_user_day(
    db: Any,
    user_id: int,
    day: date,
    *,
    pad_days: int = 1,
) -> list[tuple[datetime, datetime]]:
    """Load merged sleep bouts from WearableDaily rows near ``day``."""
    from backend.models.wearable_daily import WearableDaily
    from backend.wearables.day_stamp import tz_from_payload

    bouts: list[tuple[datetime, datetime]] = []
    try:
        for offset in range(-pad_days, pad_days + 1):
            d = day + timedelta(days=offset)
            wd = (
                db.query(WearableDaily)
                .filter(WearableDaily.user_id == user_id, WearableDaily.local_date == d)
                .first()
            )
            if wd is None:
                continue
            sleep = parse_sleep_dict(getattr(wd, "payload_json", None))
            sm, em = sleep.get("start_min"), sleep.get("end_min")
            naps = sleep.get("naps") or []
            if sm is None and (em is None or em == -1) and not naps:
                continue
            local_d = getattr(wd, "local_date", None) or d
            bouts.extend(
                sleep_bouts(
                    local_date=local_d,
                    sleep=sleep,
                    tz=tz_from_payload(getattr(wd, "payload_json", None)),
                )
            )
    except Exception:  # noqa: BLE001 — FakeDb / incomplete row in unit tests
        return []
    if not bouts:
        return []
    bouts.sort(key=lambda w: w[0])
    merged: list[tuple[datetime, datetime]] = [bouts[0]]
    for s, e in bouts[1:]:
        ps, pe = merged[-1]
        if s <= pe + timedelta(minutes=1):
            merged[-1] = (ps, max(pe, e))
        else:
            merged.append((s, e))
    return merged


def resolve_sleep_for_day(
    *,
    day: date,
    sleep_hours: float | None,
    sleep_payload: dict[str, Any] | str | None,
    wearable_local_date: date | None = None,
) -> dict[str, Any]:
    """
    Build display fields for one calendar day from one wearable row's bouts.

    `clips` = true calendar intersection (stats).
    `ring_clips` = same day clips for paint (no wake-day overnight wrap).
    """
    if isinstance(sleep_payload, dict) and (
        "total_min" in sleep_payload or "start_min" in sleep_payload or "naps" in sleep_payload
    ):
        sleep = sleep_payload
    else:
        sleep = parse_sleep_dict(sleep_payload)

    anchor = wearable_local_date or day
    bouts = sleep_bouts(local_date=anchor, sleep=sleep)
    hours = float(sleep_hours or 0)
    if hours <= 0 and sleep.get("total_min"):
        try:
            hours = max(0.0, float(sleep["total_min"]) / 60.0)
        except (TypeError, ValueError):
            hours = 0.0

    cal_clips: list[tuple[float, float]] = []
    ring: list[dict[str, Any]] = []
    first_window: tuple[datetime, datetime] | None = None
    for start_dt, end_dt in bouts:
        clipped = hours_on_calendar_day(day, start_dt, end_dt)
        if clipped:
            if first_window is None:
                first_window = (start_dt, end_dt)
            cal_clips.append(clipped)
        ring.extend(ring_clips_for_bout(day, start_dt, end_dt))

    def _merge_cal(clips: list[tuple[float, float]]) -> list[tuple[float, float]]:
        if not clips:
            return []
        clips = sorted(clips)
        merged: list[tuple[float, float]] = []
        for s, e in clips:
            if not merged or s > merged[-1][1] + 1 / 60:
                merged.append((s, e))
            else:
                merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        return merged

    cal_clips = _merge_cal(cal_clips)

    if cal_clips or ring:
        paint = ring if ring else [
            {"startHour": s, "endHour": e, "crossesMidnight": False} for s, e in cal_clips
        ]
        start_h = float(paint[0]["startHour"])
        end_h = float(paint[0]["endHour"])
        return {
            "sleep_minutes": int(round(sum((e - s) * 60 for s, e in cal_clips))),
            "startHour": start_h,
            "endHour": end_h,
            "clips": [{"startHour": s, "endHour": e} for s, e in cal_clips],
            "ring_clips": paint,
            "start_at": first_window[0] if first_window else None,
            "end_at": first_window[1] if first_window else None,
            "has_timed_window": bool(paint),
        }

    if hours > 0 and (wearable_local_date is None or wearable_local_date == day):
        return {
            "sleep_minutes": int(round(hours * 60)),
            "startHour": 0.0,
            "endHour": 0.0,
            "clips": [],
            "ring_clips": [],
            "start_at": None,
            "end_at": None,
            "has_timed_window": False,
        }
    return {
        "sleep_minutes": 0,
        "startHour": 0.0,
        "endHour": 0.0,
        "clips": [],
        "ring_clips": [],
        "start_at": None,
        "end_at": None,
        "has_timed_window": False,
    }


def _as_aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def _parse_session_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return _as_aware(value)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value) / (1000.0 if value > 1e12 else 1.0), tz=UTC)
    s = str(value).strip()
    if not s:
        return None
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return _as_aware(datetime.fromisoformat(s))
    except ValueError:
        return None


def clip_session_dicts_against_sleep(
    sessions: list[dict[str, Any]],
    sleep_bouts_list: list[tuple[datetime, datetime]],
    *,
    min_awake_sec: float = 45.0,
) -> list[dict[str, Any]]:
    """Drop/split desktop·extension·SPA pieces that fall inside sleep windows.

    Sleep rows (wearable_sleep / category Sleep) pass through unchanged.
    Fully-covered Cursor/idle blocks disappear so the calendar shows Sleep.
    """
    if not sessions:
        return []
    if not sleep_bouts_list:
        return list(sessions)

    sleeps = [(_as_aware(a), _as_aware(b)) for a, b in sleep_bouts_list if b > a]
    out: list[dict[str, Any]] = []
    for sess in sessions:
        src = str(sess.get("source") or "").lower()
        cat = str(sess.get("category") or "").lower()
        app = str(sess.get("app_name") or "").lower()
        if src == "wearable_sleep" or cat == "sleep" or app == "amazfit":
            out.append(sess)
            continue
        start = _parse_session_dt(sess.get("start_time"))
        end = _parse_session_dt(sess.get("end_time"))
        if start is None or end is None or end <= start:
            out.append(sess)
            continue
        awake = [
            (a, b)
            for a, b, idle in partition_around_sleep(start, end, sleeps)
            if not idle and (b - a).total_seconds() >= min_awake_sec
        ]
        if not awake:
            continue
        sid = str(sess.get("session_id") or "sess")
        for i, (a, b) in enumerate(awake):
            piece = dict(sess)
            piece["start_time"] = a.isoformat()
            piece["end_time"] = b.isoformat()
            if len(awake) > 1 or (a, b) != (start, end):
                piece["session_id"] = f"{sid}:awake{i}"
            out.append(piece)
    return out


def stamp_sessions_nonproductive_during_sleep(
    db: Any,
    user_id: int,
    *,
    day: date | None = None,
    commit: bool = True,
    min_overlap_sec: float = 120.0,
) -> dict[str, Any]:
    """Mark tracked sessions that mostly overlap sleep as non-productive in DB."""
    from backend.models.timetable import TrackedSession
    from backend.planner.service import local_day_bounds_utc, local_tz

    day_date = day or datetime.now(local_tz()).date()
    start, end = local_day_bounds_utc(day_date)
    sleeps = sleep_bouts_for_user_day(db, user_id, day_date, pad_days=1)
    rows = (
        db.query(TrackedSession)
        .filter(
            TrackedSession.user_id == user_id,
            TrackedSession.source.in_(("desktop_tracker", "extension", "calt_spa")),
            TrackedSession.start_time < end,
            TrackedSession.end_time > start,
        )
        .all()
    )
    stamped = 0
    samples: list[dict[str, Any]] = []
    for row in rows:
        if not row.start_time or not row.end_time:
            continue
        a, b = _as_aware(row.start_time), _as_aware(row.end_time)
        pieces = partition_around_sleep(a, b, sleeps)
        sleep_sec = sum((e - s).total_seconds() for s, e, idle in pieces if idle)
        total = (b - a).total_seconds()
        if sleep_sec < min_overlap_sec:
            continue
        if total > 0 and sleep_sec / total < 0.35 and sleep_sec < 30 * 60:
            continue
        if row.override_productive is False and (row.category_source or "") == "sleep_overwrite":
            continue
        row.override_productive = False
        row.category_source = "sleep_overwrite"
        stamped += 1
        if len(samples) < 12:
            samples.append(
                {
                    "session_id": row.session_id,
                    "app_name": row.app_name,
                    "window_title": (row.window_title or "")[:80],
                    "sleep_overlap_min": round(sleep_sec / 60, 1),
                    "start": a.isoformat(),
                    "end": b.isoformat(),
                }
            )
    if commit and stamped:
        db.commit()
    return {
        "day": day_date.isoformat(),
        "scanned": len(rows),
        "stamped": stamped,
        "samples": samples,
        "sleep_bouts": len(sleeps),
    }
