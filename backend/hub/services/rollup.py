"""Daily rollup for Life Clock — litmus ring from tracker + life log."""

from __future__ import annotations

import json
import math
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.models import DailyRollup, LifeDailyLog, MathAttempt, WearableDaily, WordProgress
from backend.models.timetable import TrackedSession

# Litmus palette — readable at a glance on the 24h ring
SEGMENT_COLORS = {
    "sleep": "#6366f1",  # indigo
    "productive": "#14b8a6",  # teal / green
    "study": "#14b8a6",
    "math": "#10b981",
    "distraction": "#f43f5e",  # rose — games / streaming / social
    "comms": "#f59e0b",  # amber — chat
    "break": "#8b5cf6",
    "other": "#64748b",  # slate — unclassified awake time
    "idle": "#334155",  # dark — gaps / not tracked
}

_DISTRACTION_CATS = frozenset(
    {
        "Gaming",
        "Video Streaming",
        "Video (YouTube)",
        "Live Streaming",
        "Social Media",
        "Social / Forum",
        "Entertainment",
        "Shopping",
        "Music / Media",
        "Food Delivery",
    }
)
_COMMS_CATS = frozenset({"Communication", "Professional Social", "Email / Calendar"})


def _today_local() -> date:
    from backend.planner.service import local_tz

    return datetime.now(local_tz()).date()


def _hour_fraction(dt: datetime, day: date) -> float:
    from backend.planner.service import local_tz

    local = dt.astimezone(local_tz()) if dt.tzinfo else dt.replace(tzinfo=UTC).astimezone(local_tz())
    if local.date() < day:
        return 0.0
    if local.date() > day:
        return 24.0
    return local.hour + local.minute / 60.0 + local.second / 3600.0


def _session_bucket(category: str | None, score: int, threshold: int) -> tuple[str, str]:
    cat = (category or "").strip()
    if cat in _DISTRACTION_CATS or score < 25:
        return "distraction", "Distraction"
    if cat in _COMMS_CATS:
        return "comms", "Comms"
    if score >= threshold:
        return "productive", "Productive"
    return "other", "Other"


# When sessions overlap in a bin, prefer focus over noise (litmus readability).
_TYPE_PRIORITY = {
    "sleep": 70,
    "productive": 60,
    "study": 60,
    "math": 60,
    "distraction": 50,
    "comms": 40,
    "break": 30,
    "relaxation": 30,
    "other": 20,
    "idle": 10,
    "untracked": 5,
}


def _merge_segments(raw: list[dict[str, Any]], *, min_gap_h: float = 3.0 / 60) -> list[dict[str, Any]]:
    if not raw:
        return []
    ordered = sorted(raw, key=lambda s: (s["startHour"], s["endHour"]))
    out: list[dict[str, Any]] = []
    for seg in ordered:
        if seg["endHour"] <= seg["startHour"]:
            continue
        if (
            out
            and out[-1]["type"] == seg["type"]
            and seg["startHour"] - out[-1]["endHour"] <= min_gap_h
        ):
            out[-1]["endHour"] = max(out[-1]["endHour"], seg["endHour"])
            continue
        out.append(dict(seg))
    return out


def _paint_timeline(
    raw: list[dict[str, Any]],
    *,
    bin_minutes: float = 5.0,
) -> list[dict[str, Any]]:
    """
    Collapse overlapping tracker sessions into non-overlapping litmus blocks.

    Desktop trackers often emit concurrent/overlapping rows; drawing each as an
    SVG arc produces the striped pink/teal mess on the life clock ring.
    """
    if not raw:
        return []
    bin_h = max(1.0 / 60, float(bin_minutes) / 60.0)
    n = int(round(24.0 / bin_h))
    weights: list[dict[str, float]] = [{} for _ in range(n)]
    templates: dict[str, dict[str, Any]] = {}

    for seg in raw:
        t = seg.get("type") or "other"
        h0 = float(seg["startHour"])
        h1 = float(seg["endHour"])
        if h1 <= h0:
            continue
        templates[t] = seg
        i0 = max(0, int(h0 / bin_h))
        i1 = min(n, int(math.ceil(h1 / bin_h - 1e-9)))
        for i in range(i0, i1):
            slot0 = i * bin_h
            slot1 = (i + 1) * bin_h
            overlap = min(h1, slot1) - max(h0, slot0)
            if overlap <= 0:
                continue
            weights[i][t] = weights[i].get(t, 0.0) + overlap

    bins: list[str | None] = []
    for w in weights:
        if not w:
            bins.append(None)
            continue
        winner = max(
            w.items(),
            key=lambda kv: (kv[1], _TYPE_PRIORITY.get(kv[0], 0)),
        )[0]
        bins.append(winner)

    out: list[dict[str, Any]] = []
    i = 0
    while i < n:
        t = bins[i]
        if t is None:
            i += 1
            continue
        j = i + 1
        while j < n and bins[j] == t:
            j += 1
        tmpl = templates.get(t) or {}
        out.append(
            {
                "label": tmpl.get("label") or t.title(),
                "startHour": i * bin_h,
                "endHour": j * bin_h,
                "color": tmpl.get("color") or SEGMENT_COLORS.get(t, SEGMENT_COLORS["other"]),
                "type": t,
            }
        )
        i = j
    return out


def _coalesce_micro_segments(
    segments: list[dict[str, Any]],
    *,
    min_minutes: float = 4.0,
) -> list[dict[str, Any]]:
    """Absorb flecks shorter than min_minutes into the previous block."""
    min_h = max(0.5 / 60, float(min_minutes) / 60.0)
    if not segments:
        return []
    ordered = sorted(segments, key=lambda s: (s["startHour"], s["endHour"]))
    out: list[dict[str, Any]] = []
    for seg in ordered:
        dur = float(seg["endHour"]) - float(seg["startHour"])
        if dur <= 0:
            continue
        if out and dur < min_h:
            out[-1]["endHour"] = max(out[-1]["endHour"], float(seg["endHour"]))
            continue
        if (
            out
            and out[-1]["type"] == seg["type"]
            and float(seg["startHour"]) - out[-1]["endHour"] <= min_h
        ):
            out[-1]["endHour"] = max(out[-1]["endHour"], float(seg["endHour"]))
            continue
        out.append(dict(seg))
    return out


def _fill_idle_gaps(segments: list[dict[str, Any]], *, until_hour: float) -> list[dict[str, Any]]:
    """Fill uncovered [0, until_hour) with idle so the ring reads as a full day so far.

    Sleep keeps its full timed window even when it extends past \"now\". Idle is
    never painted on top of sleep (that hid morning sleep under a grey wedge).
    """
    until = max(0.0, min(24.0, until_hour))
    sleep_segs = [s for s in segments if (s.get("type") or "") == "sleep"]
    awake = [s for s in segments if (s.get("type") or "") != "sleep"]
    sleep_clips = [
        (float(s["startHour"]), float(s["endHour"]))
        for s in sleep_segs
        if float(s["endHour"]) > float(s["startHour"])
    ]
    if until <= 0.05:
        return [*sleep_segs, *awake]

    def _idle_minus_sleep(a: float, b: float) -> list[tuple[float, float]]:
        pieces = [(a, b)]
        for ss, se in sleep_clips:
            nxt: list[tuple[float, float]] = []
            for x, y in pieces:
                if y <= ss or x >= se:
                    nxt.append((x, y))
                    continue
                if x < ss:
                    nxt.append((x, ss))
                if y > se:
                    nxt.append((se, y))
            pieces = [(x, y) for x, y in nxt if y - x >= 1 / 60]
        return pieces

    covered = _merge_segments(awake)
    filled: list[dict[str, Any]] = []
    cursor = 0.0
    for seg in covered:
        start = max(0.0, min(until, float(seg["startHour"])))
        end = max(0.0, min(until, float(seg["endHour"])))
        if start > cursor + 0.02:
            for a, b in _idle_minus_sleep(cursor, start):
                filled.append(
                    {
                        "label": "Idle / off",
                        "startHour": a,
                        "endHour": b,
                        "color": SEGMENT_COLORS["idle"],
                        "type": "idle",
                    }
                )
        if end > start:
            filled.append({**seg, "startHour": start, "endHour": end})
            cursor = max(cursor, end)
        elif float(seg["startHour"]) >= until:
            break
    if cursor < until - 0.02:
        for a, b in _idle_minus_sleep(cursor, until):
            filled.append(
                {
                    "label": "Idle / off",
                    "startHour": a,
                    "endHour": b,
                    "color": SEGMENT_COLORS["idle"],
                    "type": "idle",
                }
            )
    out = [*sleep_segs, *filled]
    out.sort(key=lambda s: (float(s["startHour"]), float(s["endHour"])))
    return out


def _segments_from_tracker(db: Session, user_id: int, day: date) -> tuple[list[dict[str, Any]], int]:
    """Real wall-clock segments from desktop tracker + productive minutes.

    Productive seconds exclude overlap with wearable sleep (PC left on overnight).
    """
    from backend.behavior.category_scores import load_score_map
    from backend.behavior.productivity_policy import load_policy_dict, resolve_session_score
    from backend.models import User
    from backend.planner.service import local_day_bounds_utc
    from backend.timetable.tracker_query import tracker_user_ids
    from backend.wearables.sleep_window import (
        partition_around_sleep,
        sleep_bouts_for_user_day,
    )

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        return [], 0

    start, end = local_day_bounds_utc(day)
    sessions = (
        db.query(TrackedSession)
        .filter(
            TrackedSession.user_id.in_(tracker_user_ids(db, user)),
            TrackedSession.start_time < end,
            TrackedSession.end_time > start,
        )
        .all()
    )
    if not sessions:
        return [], 0

    scores = load_score_map(db)
    policy = load_policy_dict(db, user_id)
    threshold = int(policy.get("threshold") or 60)
    sleeps = sleep_bouts_for_user_day(db, user_id, day, pad_days=1)

    raw: list[dict[str, Any]] = []
    productive_seconds = 0.0
    for sess in sessions:
        if not sess.start_time or not sess.end_time:
            continue
        score = resolve_session_score(sess, scores, policy)
        bucket, label = _session_bucket(sess.category, score, threshold)
        # Clip tracker span against sleep before painting / scoring
        a = sess.start_time if sess.start_time.tzinfo else sess.start_time.replace(tzinfo=UTC)
        b = sess.end_time if sess.end_time.tzinfo else sess.end_time.replace(tzinfo=UTC)
        awake_spans = (
            [(x, y) for x, y, idle in partition_around_sleep(a, b, sleeps) if not idle]
            if sleeps
            else [(a, b)]
        )
        for x, y in awake_spans:
            h0 = _hour_fraction(x, day)
            h1 = _hour_fraction(y, day)
            if h1 <= h0:
                continue
            h0 = max(0.0, min(24.0, h0))
            h1 = max(0.0, min(24.0, h1))
            if h1 - h0 < 0.5 / 60:
                continue
            raw.append(
                {
                    "label": label,
                    "startHour": h0,
                    "endHour": h1,
                    "color": SEGMENT_COLORS[bucket],
                    "type": bucket,
                }
            )
            if score >= threshold:
                productive_seconds += (h1 - h0) * 3600.0

    merged = _coalesce_micro_segments(_paint_timeline(raw, bin_minutes=5.0), min_minutes=4.0)
    return merged, int(productive_seconds // 60)


def rebuild_daily_rollup(db: Session, user_id: int, day: date) -> DailyRollup:
    """Build or refresh cached rollup for Life Clock + dashboard."""
    from backend.planner.service import local_tz

    life = (
        db.query(LifeDailyLog)
        .filter(LifeDailyLog.user_id == user_id, LifeDailyLog.date == day)
        .first()
    )

    day_start = datetime.combine(day, datetime.min.time()).replace(tzinfo=UTC)
    day_end = day_start + timedelta(days=1)

    math_count = (
        db.query(func.count(MathAttempt.id))
        .filter(
            MathAttempt.user_id == user_id,
            MathAttempt.created_at >= day_start,
            MathAttempt.created_at < day_end,
        )
        .scalar()
        or 0
    )

    vocab_events = (
        db.query(func.count(WordProgress.id))
        .filter(
            WordProgress.user_id == user_id,
            WordProgress.updated_at >= day_start,
            WordProgress.updated_at < day_end,
            WordProgress.times_asked > 0,
        )
        .scalar()
        or 0
    )

    sleep_hours = 0.0
    sleep_payload: dict | str | None = None
    wearable_anchor: date | None = None

    wd_today = (
        db.query(WearableDaily)
        .filter(WearableDaily.user_id == user_id, WearableDaily.local_date == day)
        .first()
    )
    wd_yest = (
        db.query(WearableDaily)
        .filter(WearableDaily.user_id == user_id, WearableDaily.local_date == day - timedelta(days=1))
        .first()
    )
    wd_tomorrow = (
        db.query(WearableDaily)
        .filter(WearableDaily.user_id == user_id, WearableDaily.local_date == day + timedelta(days=1))
        .first()
    )

    def _wd_ok(wd: WearableDaily | None) -> bool:
        return bool(wd and wd.sleep_hours is not None and float(wd.sleep_hours) > 0)

    # Wearable timed sleep only — never invent from life-log hours alone
    if _wd_ok(wd_today):
        sleep_hours = float(wd_today.sleep_hours)
        sleep_payload = wd_today.payload_json
        wearable_anchor = wd_today.local_date

    # Soft-fill life ONLY on the wearable's own local_date — never copy last night onto "today"
    if sleep_hours > 0 and wearable_anchor is not None and wearable_anchor == day:
        if not life:
            life = LifeDailyLog(user_id=user_id, date=day)
            db.add(life)
        if not life.sleep_hours or float(life.sleep_hours) <= 0:
            life.sleep_hours = sleep_hours
            if wd_today and wd_today.sleep_score is not None:
                from backend.wearables.ingest_service import score_to_quality

                life.sleep_quality = score_to_quality(wd_today.sleep_score)

    from backend.wearables.sleep_window import resolve_sleep_for_day

    # Timed wedges from today / yesterday / tomorrow wearable rows (overnight + naps).
    sleep_clips: list[tuple[float, float, bool]] = []
    sleep_minutes = 0
    for wd in (wd_today, wd_yest, wd_tomorrow):
        if not _wd_ok(wd):
            continue
        view = resolve_sleep_for_day(
            day=day,
            sleep_hours=float(wd.sleep_hours),
            sleep_payload=wd.payload_json,
            wearable_local_date=wd.local_date,
        )
        if not view.get("has_timed_window"):
            continue
        # Stats: calendar intersection only (no double-count of bedtime visual)
        sleep_minutes += int(view.get("sleep_minutes") or 0)
        # Paint: ring_clips (may wrap overnight bedtime→wake)
        raw_clips = view.get("ring_clips") or view.get("clips") or []
        if raw_clips:
            for c in raw_clips:
                start_h = float(c.get("startHour") or 0.0)
                end_h = float(c.get("endHour") or 0.0)
                crosses = bool(c.get("crossesMidnight"))
                if crosses or end_h > start_h:
                    sleep_clips.append((start_h, end_h, crosses))
        else:
            start_h = float(view.get("startHour") or 0.0)
            end_h = float(view.get("endHour") or 0.0)
            if end_h > start_h:
                sleep_clips.append((start_h, end_h, False))

    # sleep_clips entries are (start, end, crossesMidnight)
    paint_segs: list[dict[str, Any]] = []
    if sleep_clips:
        for s, e, crosses in sleep_clips:
            paint_segs.append(
                {
                    "label": "Sleep",
                    "startHour": s,
                    "endHour": e,
                    "color": SEGMENT_COLORS["sleep"],
                    "type": "sleep",
                    "crossesMidnight": crosses,
                }
            )
    elif sleep_hours > 0 and wearable_anchor == day:
        sleep_minutes = int(round(sleep_hours * 60))
    else:
        if not sleep_minutes:
            sleep_minutes = 0

    study_minutes = life.study_minutes if life else 0

    tracker_segs, tracker_productive = _segments_from_tracker(db, user_id, day)

    segments: list[dict[str, Any]] = list(paint_segs)

    # Flat hour ranges for clipping awake activity (expand wrap into two ranges)
    sleep_ranges: list[tuple[float, float]] = []
    for seg in paint_segs:
        s0 = float(seg["startHour"])
        e0 = float(seg["endHour"])
        if seg.get("crossesMidnight"):
            sleep_ranges.append((s0, 24.0))
            sleep_ranges.append((0.0, e0))
        elif e0 > s0:
            sleep_ranges.append((s0, e0))

    def _clip_awake_against_sleep(s0: float, e0: float) -> list[tuple[float, float]]:
        """Return awake intervals after cutting out all sleep ranges."""
        pieces = [(s0, e0)]
        for sleep_start, sleep_end in sleep_ranges:
            nxt: list[tuple[float, float]] = []
            for a, b in pieces:
                if b <= sleep_start or a >= sleep_end:
                    nxt.append((a, b))
                    continue
                if a < sleep_start:
                    nxt.append((a, sleep_start))
                if b > sleep_end:
                    nxt.append((sleep_end, b))
            pieces = [(a, b) for a, b in nxt if b - a >= 1 / 60]
        return pieces

    if tracker_segs:
        # Prefer real tracker timeline; clip awake segments that overlap sleep
        for seg in tracker_segs:
            s0 = float(seg["startHour"])
            e0 = float(seg["endHour"])
            if e0 <= s0:
                continue
            for a, b in _clip_awake_against_sleep(s0, e0):
                segments.append({**seg, "startHour": a, "endHour": b})
        segments.sort(key=lambda s: (float(s["startHour"]), float(s["endHour"])))
        now_local = datetime.now(local_tz())
        until = 24.0
        if now_local.date() == day:
            until = now_local.hour + now_local.minute / 60.0 + now_local.second / 3600.0
        segments = _fill_idle_gaps(segments, until_hour=until)
        productive_minutes = tracker_productive
    else:
        # Legacy stacked blocks when tracker has no data yet
        cursor = segments[0]["endHour"] if segments else 0.0
        if study_minutes > 0:
            hours = study_minutes / 60.0
            segments.append(
                {
                    "label": "Study",
                    "startHour": cursor,
                    "endHour": min(24.0, cursor + hours),
                    "color": SEGMENT_COLORS["study"],
                    "type": "study",
                }
            )
            cursor = min(24.0, cursor + hours)
        if math_count > 0:
            hours = min(2.0, math_count * 0.25)
            segments.append(
                {
                    "label": "Math",
                    "startHour": cursor,
                    "endHour": min(24.0, cursor + hours),
                    "color": SEGMENT_COLORS["math"],
                    "type": "math",
                }
            )
        productive_minutes = study_minutes + (life.exercise_minutes if life else 0)

    stats = {
        "life_score": life.life_score if life else 0,
        "math_attempts": math_count,
        "vocab_events": vocab_events,
        "tracker_productive_minutes": tracker_productive,
        "source": "tracker" if tracker_segs else "life_log",
    }

    rollup = (
        db.query(DailyRollup)
        .filter(DailyRollup.user_id == user_id, DailyRollup.date == day)
        .first()
    )
    if not rollup:
        rollup = DailyRollup(user_id=user_id, date=day)
        db.add(rollup)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            rollup = (
                db.query(DailyRollup)
                .filter(DailyRollup.user_id == user_id, DailyRollup.date == day)
                .first()
            )
            if rollup is None:
                raise

    rollup.segments_json = json.dumps(segments)
    rollup.productive_minutes = int(productive_minutes)
    rollup.sleep_minutes = sleep_minutes
    rollup.vocab_events = vocab_events
    rollup.math_attempts = math_count
    rollup.stats_json = json.dumps(stats)
    db.commit()
    db.refresh(rollup)
    return rollup


def daily_payload(rollup: DailyRollup, life: LifeDailyLog | None) -> dict:
    from backend.behavior.time_fmt import optional_minutes_label
    from backend.planner.service import local_tz

    now = datetime.now(local_tz())
    current_hour = now.hour + now.minute / 60 + now.second / 3600
    segments = json.loads(rollup.segments_json or "[]")

    return {
        "date": rollup.date.isoformat(),
        "segments": segments,
        "productive_minutes": rollup.productive_minutes,
        "productive_label": optional_minutes_label(rollup.productive_minutes),
        "sleep_minutes": rollup.sleep_minutes,
        "sleep_label": optional_minutes_label(rollup.sleep_minutes),
        "vocab_events": rollup.vocab_events,
        "math_attempts": rollup.math_attempts,
        "stats": json.loads(rollup.stats_json or "{}"),
        "life_score": life.life_score if life else 0,
        "time_left_hours": max(0, 24 - current_hour),
        "percent_elapsed": round((current_hour / 24) * 100, 1),
        "current_hour": current_hour,
    }
