"""Sleep-backward day bounds for smart fill (default 8h from 22:00 wake at 06:00)."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from backend.planner.service import local_tz

DEFAULT_WAKE_HM = "06:00"
DEFAULT_SLEEP_HOURS = 8
SLEEP_PREP_MIN = 30  # last block must end this many minutes before sleep


def parse_hm(value: str, *, default: tuple[int, int] = (6, 0)) -> tuple[int, int]:
    raw = (value or "").strip()
    if not raw:
        return default
    try:
        parts = raw.split(":")
        h = int(parts[0])
        m = int(parts[1]) if len(parts) > 1 else 0
        if 0 <= h <= 23 and 0 <= m <= 59:
            return h, m
    except (TypeError, ValueError):
        pass
    return default


def sleep_target_hm(
    wake_hm: str = DEFAULT_WAKE_HM,
    *,
    sleep_hours: float = DEFAULT_SLEEP_HOURS,
) -> tuple[int, int]:
    """Bedtime for *sleep_hours* before next wake (e.g. wake 06:00 + 8h sleep → 22:00)."""
    wh, wm = parse_hm(wake_hm)
    wake_min = wh * 60 + wm
    sleep_min = int(round(float(sleep_hours) * 60))
    target = (wake_min - sleep_min) % (24 * 60)
    return target // 60, target % 60


def day_end_minutes(
    wake_hm: str = DEFAULT_WAKE_HM,
    *,
    sleep_hours: float = DEFAULT_SLEEP_HOURS,
    prep_min: int = SLEEP_PREP_MIN,
) -> int:
    """Last schedulable minute of day (exclusive end for blocks)."""
    sh, sm = sleep_target_hm(wake_hm, sleep_hours=sleep_hours)
    end = sh * 60 + sm - max(0, int(prep_min))
    return max(6 * 60, min(23 * 60 + 59, end))


def day_start_minutes(wake_hm: str = DEFAULT_WAKE_HM) -> int:
    wh, wm = parse_hm(wake_hm)
    return max(5 * 60, wh * 60 + wm - 30)


def clamp_block_to_sleep(
    block: dict,
    *,
    wake_hm: str = DEFAULT_WAKE_HM,
    sleep_hours: float = DEFAULT_SLEEP_HOURS,
) -> dict | None:
    """Trim or drop a block that extends past sleep anchor."""
    from backend.behavior.calt_desktop.planner_propose_merge import _parse_iso, _with_local_range

    try:
        start = _parse_iso(str(block.get("start_at") or ""))
        end = _parse_iso(str(block.get("end_at") or ""))
    except ValueError:
        return block
    day = start.date().isoformat()
    day_end = day_end_minutes(wake_hm, sleep_hours=sleep_hours)
    start_m = start.hour * 60 + start.minute
    end_m = end.hour * 60 + end.minute
    if start_m >= day_end:
        return None
    if end_m <= day_end:
        return block
    if day_end - start_m < 10:
        return None
    return _with_local_range(block, day, start_m, day_end)


def sleep_summary(wake_hm: str = DEFAULT_WAKE_HM, *, sleep_hours: float = DEFAULT_SLEEP_HOURS) -> str:
    sh, sm = sleep_target_hm(wake_hm, sleep_hours=sleep_hours)
    end = day_end_minutes(wake_hm, sleep_hours=sleep_hours)
    return (
        f"Wake {wake_hm} · sleep target {sh:02d}:{sm:02d} "
        f"({sleep_hours:g}h) · blocks end by {end // 60:02d}:{end % 60:02d}"
    )
