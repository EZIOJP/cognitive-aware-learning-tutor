"""Per-hour 2D calendar slices for planner overlay (lanes + merge groups).

Pure functions: take already-collected overlay sessions, return hour_slices.
Mirrors frontend mergeForCalendar keys/gaps so session_group_id stays aligned.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable
from zoneinfo import ZoneInfo

# Match src/components/productivity/planVsActualUtils.ts
CALENDAR_MERGE_GAP_SEC = 900
CALENDAR_MIN_DISPLAY_SEC = 120

_IGNORED_APP_NEEDLES = (
    "move mouse",
    "movemouse",
    "caffeine",
    "dontsleep",
    "lockapp",
    "steamwebhelper",
)

_BROWSER_TITLE_SUFFIXES = (
    # Match end of title; don't require a specific dash character
    (re.compile(r"Zen\s*Browser\s*$", re.I), "zen"),
    (re.compile(r"Microsoft\s*Edge\s*$", re.I), "msedge"),
    (re.compile(r"Google\s*Chrome\s*$", re.I), "chrome"),
    (re.compile(r"\bBrave\s*$", re.I), "brave"),
    (re.compile(r"\bFirefox\s*$", re.I), "firefox"),
)


def _app_from_window_title(title: str | None) -> str | None:
    t = (title or "").strip()
    if not t:
        return None
    for rx, app in _BROWSER_TITLE_SUFFIXES:
        if rx.search(t):
            return app
    return None


def _effective_app_name(session: dict[str, Any]) -> str:
    """Prefer browser from window title when exe conflicts (tracker mis-attribution)."""
    raw = (session.get("app_name") or "").strip()
    implied = _app_from_window_title(session.get("window_title"))
    if not implied:
        return raw
    if not raw:
        return implied
    a = raw.lower().removesuffix(".exe").removesuffix(".app")
    if a == implied or implied in a or a in implied:
        return raw
    return implied


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _is_ignored_app(app_name: str | None, title: str | None) -> bool:
    hay = f"{app_name or ''} {title or ''}".strip().lower()
    if not hay:
        return False
    return any(n in hay for n in _IGNORED_APP_NEEDLES)


def _is_sleep(session: dict[str, Any]) -> bool:
    cat = (session.get("category") or "").strip().lower()
    src = (session.get("source") or "").strip().lower()
    app = (session.get("app_name") or "").strip().lower()
    return cat == "sleep" or src == "wearable_sleep" or app == "amazfit"


def _merge_key(session: dict[str, Any]) -> str:
    app = _effective_app_name(session).strip().lower()
    if app:
        return f"app:{app}"
    cat = (session.get("category") or "Other").strip().lower()
    return f"cat:{cat}"


def _display_label(session: dict[str, Any]) -> str:
    if _is_sleep(session):
        return "Sleep"
    app = _effective_app_name(session).strip()
    if app:
        if app.lower().endswith(".exe"):
            app = app[:-4]
        if app.lower().endswith(".app"):
            app = app[:-4]
        return app
    return (session.get("category") or "Activity").strip() or "Activity"


def _effective_category(session: dict[str, Any]) -> str:
    raw = (session.get("app_name") or "").strip()
    implied = _app_from_window_title(session.get("window_title"))
    title = session.get("window_title") or ""
    if implied and raw:
        a = raw.lower().removesuffix(".exe").removesuffix(".app")
        if a != implied and implied not in a and a not in implied:
            if re.search(r"netflix|youtube|hulu|disney|prime\s*video|\bwatch\b|rookie|twitch", title, re.I):
                return "Video Streaming"
            return "Other (Browser)"
    return (session.get("category") or "Other").strip() or "Other"


def _source_tag(session: dict[str, Any]) -> str:
    if _is_sleep(session):
        return "sleep"
    return "desktop"


@dataclass
class _MergedRun:
    session_group_id: str
    source: str
    app_or_label: str
    category: str
    start: datetime
    end: datetime
    session_ids: list[str]
    merge_key: str


def _merge_sessions(
    sessions: Iterable[dict[str, Any]],
    *,
    max_gap_sec: int,
    min_display_sec: int | None,
) -> list[_MergedRun]:
    items: list[tuple[datetime, datetime, dict[str, Any]]] = []
    for s in sessions:
        start = _parse_iso(s.get("start_time"))
        end = _parse_iso(s.get("end_time"))
        if not start or not end or end <= start:
            continue
        if _is_ignored_app(s.get("app_name"), s.get("window_title")):
            continue
        items.append((start, end, s))
    items.sort(key=lambda t: t[0])

    out: list[_MergedRun] = []
    # Last run per merge key (for continuity), plus full timeline for intervening checks.
    last_by_key: dict[str, _MergedRun] = {}
    for start, end, s in items:
        key = _merge_key(s)
        sid = str(s.get("session_id") or "")
        prev = last_by_key.get(key)
        if prev is not None:
            gap = (start - prev.end).total_seconds()
            # Contiguous / tiny gap / overlap with same app — merge into one whole block.
            # Do NOT bridge across other apps (that inflates duration and mixes detail).
            if gap <= max_gap_sec or start <= prev.end:
                # Do NOT bridge across other apps (that inflates duration / mixes detail).
                intervening = False
                for other in out:
                    if other.merge_key == key:
                        continue
                    if other.start < start and other.end > prev.end:
                        intervening = True
                        break
                if not intervening:
                    prev.end = max(prev.end, end)
                    if sid and sid not in prev.session_ids:
                        prev.session_ids.append(sid)
                    continue
        group_id = f"{key}|{start.astimezone(timezone.utc).isoformat()}"
        run = _MergedRun(
            session_group_id=group_id,
            source=_source_tag(s),
            app_or_label=_display_label(s),
            category=_effective_category(s),
            start=start,
            end=end,
            session_ids=[sid] if sid else [],
            merge_key=key,
        )
        out.append(run)
        last_by_key[key] = run

    if min_display_sec is not None:
        out = [m for m in out if (m.end - m.start).total_seconds() >= min_display_sec]
    return out


def merge_for_hour_slices(sessions: list[dict[str, Any]]) -> list[_MergedRun]:
    """Sleep separate from desktop; same gaps/filters as calendar merge."""
    sleep = [s for s in sessions if _is_sleep(s)]
    rest = [s for s in sessions if not _is_sleep(s)]
    merged_rest = _merge_sessions(
        rest, max_gap_sec=CALENDAR_MERGE_GAP_SEC, min_display_sec=CALENDAR_MIN_DISPLAY_SEC
    )
    merged_sleep = _merge_sessions(sleep, max_gap_sec=CALENDAR_MERGE_GAP_SEC, min_display_sec=None)
    combined = merged_rest + merged_sleep
    combined.sort(key=lambda m: m.start)
    return combined


@dataclass
class _HourSeg:
    session_group_id: str
    source: str
    app_or_label: str
    category: str
    start_min: int
    end_min: int
    session_ids: list[str]
    lane_index: int = -1

    @property
    def duration_min(self) -> int:
        return max(0, self.end_min - self.start_min)


def _overlaps(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    return a_start < b_end and b_start < a_end


def _clip_run_to_hour(run: _MergedRun, hour_start: datetime) -> _HourSeg | None:
    hour_end = hour_start + timedelta(hours=1)
    start = max(run.start, hour_start)
    end = min(run.end, hour_end)
    if end <= start:
        return None
    start_min = int((start - hour_start).total_seconds() // 60)
    # Exclusive upper bound in [1, 60]; if ends exactly on hour, end_min = 60
    end_delta = (end - hour_start).total_seconds() / 60.0
    end_min = int(end_delta) if end_delta == int(end_delta) else int(end_delta) + 1
    end_min = max(start_min + 1, min(60, end_min))
    start_min = max(0, min(59, start_min))
    if end_min <= start_min:
        end_min = min(60, start_min + 1)
    return _HourSeg(
        session_group_id=run.session_group_id,
        source=run.source,
        app_or_label=run.app_or_label if run.source != "sleep" else "Sleep",
        category=run.category if run.source != "sleep" else "Sleep",
        start_min=start_min,
        end_min=end_min,
        session_ids=list(run.session_ids),
    )


def _lane_free(
    occupied: list[tuple[int, int, int]],
    lane: int,
    start_min: int,
    end_min: int,
) -> bool:
    for o_start, o_end, o_lane in occupied:
        if o_lane == lane and _overlaps(start_min, end_min, o_start, o_end):
            return False
    return True


def _assign_lanes(segments: list[_HourSeg], pins: dict[str, int]) -> dict[str, int]:
    """Assign lane_index in-place. Returns pin map for next hour."""
    if not segments:
        return {}

    sleep_segs = [s for s in segments if s.source == "sleep"]
    desk_segs = [s for s in segments if s.source != "sleep"]
    sleep_reserved = bool(sleep_segs)
    min_desk_lane = 1 if sleep_reserved else 0

    occupied: list[tuple[int, int, int]] = []

    for seg in sleep_segs:
        seg.lane_index = 0
        occupied.append((seg.start_min, seg.end_min, 0))

    desk_segs.sort(key=lambda s: (s.start_min, s.session_group_id))

    for seg in desk_segs:
        preferred = pins.get(seg.session_group_id)
        assigned = None
        if preferred is not None:
            lane = preferred
            if sleep_reserved and lane == 0:
                lane = min_desk_lane
            if lane >= min_desk_lane and _lane_free(occupied, lane, seg.start_min, seg.end_min):
                assigned = lane
        if assigned is None:
            lane = min_desk_lane
            while not _lane_free(occupied, lane, seg.start_min, seg.end_min):
                lane += 1
            assigned = lane
        seg.lane_index = assigned
        occupied.append((seg.start_min, seg.end_min, assigned))

    next_pins: dict[str, int] = {}
    for seg in segments:
        if seg.lane_index >= 0:
            next_pins[seg.session_group_id] = seg.lane_index
    return next_pins


def _resolve_tz(tz_name: str | None = None, tzinfo: Any = None):
    if tzinfo is not None:
        return tzinfo
    if tz_name:
        try:
            return ZoneInfo(tz_name)
        except Exception:
            pass
    local = datetime.now().astimezone().tzinfo
    return local or timezone.utc


def _iter_local_hours(runs: list[_MergedRun]) -> list[tuple[str, int, datetime]]:
    """Unique (date_str, hour, hour_start_local) covering all runs."""
    if not runs:
        return []
    earliest = min(r.start for r in runs)
    latest = max(r.end for r in runs)
    cursor = earliest.replace(minute=0, second=0, microsecond=0)
    hours: list[tuple[str, int, datetime]] = []
    while cursor < latest:
        hours.append((cursor.date().isoformat(), cursor.hour, cursor))
        cursor = cursor + timedelta(hours=1)
    return hours


def compute_hour_slices(
    sessions: list[dict[str, Any]],
    *,
    tz_name: str | None = None,
    tzinfo: Any = None,
) -> list[dict[str, Any]]:
    """Build hour_slices for overlay response from serialized sessions."""
    tz = _resolve_tz(tz_name, tzinfo)
    runs = merge_for_hour_slices(sessions)
    local_runs: list[_MergedRun] = []
    for r in runs:
        local_runs.append(
            _MergedRun(
                session_group_id=r.session_group_id,
                source=r.source,
                app_or_label=r.app_or_label,
                category=r.category,
                start=r.start.astimezone(tz),
                end=r.end.astimezone(tz),
                session_ids=r.session_ids,
                merge_key=r.merge_key,
            )
        )

    hours = _iter_local_hours(local_runs)
    pins: dict[str, int] = {}
    prev_hour_start: datetime | None = None
    slices: list[dict[str, Any]] = []

    for date_str, hour, hour_start in hours:
        if prev_hour_start is not None and hour_start - prev_hour_start != timedelta(hours=1):
            pins = {}

        segs: list[_HourSeg] = []
        for run in local_runs:
            clipped = _clip_run_to_hour(run, hour_start)
            if clipped:
                segs.append(clipped)

        if not segs:
            pins = {}
            prev_hour_start = hour_start
            continue

        pins = _assign_lanes(segs, pins)
        lane_count = max((s.lane_index for s in segs), default=0) + 1
        slices.append(
            {
                "date": date_str,
                "hour": hour,
                "lane_count": lane_count,
                "segments": [
                    {
                        "session_group_id": s.session_group_id,
                        "source": s.source,
                        "app_or_label": s.app_or_label,
                        "category": s.category,
                        "start_min": s.start_min,
                        "end_min": s.end_min,
                        "lane_index": s.lane_index,
                        "total_lanes_this_hour": lane_count,
                        "session_ids": s.session_ids,
                        "duration_min": s.duration_min,
                    }
                    for s in sorted(segs, key=lambda x: (x.lane_index, x.start_min))
                ],
            }
        )
        prev_hour_start = hour_start

    return slices
