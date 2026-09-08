"""Morning-first scheduling — study never before Bible / bath / eat."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from backend.planner.service import local_tz

_DAY_NAMES = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
_MORNING_CATEGORIES = frozenset({"spiritual", "personal", "food"})
_DEFAULT_STUDY_FLOOR_MIN = 8 * 60  # 08:00 after breakfast block
_NOON_MIN = 12 * 60
_BUFFER_MIN = 10


def _weekday_key(d: date) -> str:
    return _DAY_NAMES[d.weekday()]


def _parse_block_interval_minutes(block: dict[str, Any], day: date) -> tuple[int, int] | None:
    try:
        start = datetime.fromisoformat(str(block.get("start_at") or "").replace("Z", "+00:00"))
        end = datetime.fromisoformat(str(block.get("end_at") or "").replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if start.tzinfo is None:
        start = start.replace(tzinfo=local_tz())
    if end.tzinfo is None:
        end = end.replace(tzinfo=local_tz())
    start = start.astimezone(local_tz())
    end = end.astimezone(local_tz())
    if start.date() != day:
        return None
    return start.hour * 60 + start.minute, end.hour * 60 + end.minute


def _routine_interval_minutes(routine: dict[str, Any]) -> tuple[int, int]:
    start_s = str(routine.get("start_time") or "09:00")
    end_s = routine.get("end_time")
    sh, sm = (int(x) for x in start_s.split(":", 1)[:2])
    start_m = sh * 60 + sm
    if end_s:
        eh, em = (int(x) for x in str(end_s).split(":", 1)[:2])
        end_m = eh * 60 + em
    else:
        end_m = start_m + int(routine.get("duration_minutes") or 30)
    return start_m, end_m


def _is_morning_life_block(category: str, title: str) -> bool:
    c = (category or "").strip().lower()
    t = (title or "").strip().lower()
    if c in _MORNING_CATEGORIES:
        return True
    return any(
        k in t
        for k in (
            "bible",
            "devotion",
            "bath",
            "breakfast",
            "self-care",
            "shower",
            "prayer",
            "proverbs",
            "psalm",
        )
    )


def _is_study_block(block: dict[str, Any]) -> bool:
    src = str(block.get("source") or "").lower()
    if src in ("study", "break"):
        return src == "study"
    cat = str(block.get("category") or "").lower()
    if cat in ("study", "coursework", "work", "ai/ml", "coding practice"):
        return True
    t = str(block.get("title") or "").lower()
    return any(k in t for k in ("study", "scaler", "coursework", "lecture", "practice", "ai/ml"))


def morning_study_floor_min(
    *,
    day: date,
    routines: list[dict[str, Any]] | None = None,
    calendar_blocks: list[dict[str, Any]] | None = None,
    default_floor_min: int = _DEFAULT_STUDY_FLOOR_MIN,
) -> int:
    """
    Earliest minute study blocks may start.

    Rule: after all spiritual + personal + food routines/blocks that end before noon.
    Falls back to 08:00 when no morning routines exist.
    """
    floor = default_floor_min
    key = _weekday_key(day)

    for r in routines or []:
        if not isinstance(r, dict) or r.get("enabled") is False:
            continue
        days = r.get("days") or list(_DAY_NAMES)
        if key not in days and "daily" not in {str(d).lower() for d in days}:
            continue
        cat = str(r.get("category") or "").lower()
        title = str(r.get("title") or "")
        if not _is_morning_life_block(cat, title):
            continue
        _s, end_m = _routine_interval_minutes(r)
        if end_m <= _NOON_MIN:
            floor = max(floor, end_m)

    for b in calendar_blocks or []:
        if not isinstance(b, dict):
            continue
        interval = _parse_block_interval_minutes(b, day)
        if interval is None:
            continue
        start_m, end_m = interval
        if start_m >= _NOON_MIN:
            continue
        cat = str(b.get("category") or "")
        title = str(b.get("title") or "")
        if _is_morning_life_block(cat, title):
            floor = max(floor, end_m)

    return min(_NOON_MIN, floor + _BUFFER_MIN)


def filter_gaps_after_morning(
    gaps: list[tuple[int, int]],
    floor_min: int,
    *,
    min_gap: int = 25,
) -> list[tuple[int, int]]:
    """Drop or trim gaps that start before the morning study floor."""
    out: list[tuple[int, int]] = []
    for start, end in gaps:
        if end <= floor_min:
            continue
        s = max(start, floor_min)
        if end - s >= min_gap:
            out.append((s, end))
    return out


def _is_routine_block(block: dict[str, Any]) -> bool:
    """Life/routine blocks — not study tasks."""
    src = str(block.get("source") or "").lower()
    if src == "routine":
        return True
    if src == "break":
        return False
    cat = str(block.get("category") or "").lower()
    title = str(block.get("title") or "")
    if _is_study_block(block):
        return False
    if _is_morning_life_block(cat, title):
        return True
    if cat in ("personal", "food", "spiritual", "break"):
        return True
    return src == "existing" and not _is_study_block(block)


def _block_at_minutes(day: date, start_m: int, end_m: int, **fields: Any) -> dict[str, Any]:
    tz = local_tz()
    base = datetime(day.year, day.month, day.day, 0, 0, tzinfo=tz)
    return {
        **fields,
        "start_at": (base + timedelta(minutes=start_m)).isoformat(),
        "end_at": (base + timedelta(minutes=end_m)).isoformat(),
    }


def ensure_day_starts_with_routine(
    blocks: list[dict[str, Any]],
    *,
    day: date | None = None,
    routines: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """First block of the day must be a routine/life block — never a study task."""
    day = day or date.today()
    if not blocks:
        return blocks

    ordered = sort_blocks_chronological(blocks)
    day_blocks = [b for b in ordered if _parse_block_interval_minutes(b, day)]
    if not day_blocks:
        return ordered

    first = day_blocks[0]
    if _is_routine_block(first) or not _is_study_block(first):
        return ordered

    floor = morning_study_floor_min(day=day, routines=routines, calendar_blocks=blocks)
    return enforce_morning_order(blocks, day=day)  # pushes study to floor


def insert_breaks_after_study_tasks(
    blocks: list[dict[str, Any]],
    *,
    day: date | None = None,
    break_min: int = 10,
) -> list[dict[str, Any]]:
    """Every study task is followed by a short break block."""
    if not blocks:
        return blocks

    try:
        from backend.behavior.calt_desktop.sleep_anchor import day_end_minutes

        day_cap = day_end_minutes()
    except Exception:  # noqa: BLE001
        day_cap = 23 * 60

    by_day: dict[str, list[dict[str, Any]]] = {}
    for b in blocks:
        try:
            start = datetime.fromisoformat(str(b.get("start_at") or "").replace("Z", "+00:00"))
            if start.tzinfo is None:
                start = start.replace(tzinfo=local_tz())
            dk = start.astimezone(local_tz()).date().isoformat()
        except (TypeError, ValueError):
            dk = (day or date.today()).isoformat()
        by_day.setdefault(dk, []).append(b)

    out: list[dict[str, Any]] = []
    for dk in sorted(by_day.keys()):
        y, mo, d = (int(x) for x in dk.split("-"))
        dday = date(y, mo, d)
        day_list = sort_blocks_chronological(by_day[dk])
        for i, b in enumerate(day_list):
            out.append(b)
            if not _is_study_block(b):
                continue
            interval = _parse_block_interval_minutes(b, dday)
            if interval is None:
                continue
            _s, end_m = interval
            nxt = day_list[i + 1] if i + 1 < len(day_list) else None
            if nxt is not None:
                if str(nxt.get("source") or "").lower() == "break":
                    continue
                nxt_iv = _parse_block_interval_minutes(nxt, dday)
                if nxt_iv and nxt_iv[0] <= end_m + 2:
                    continue
            br_end = min(end_m + break_min, day_cap)
            if br_end - end_m < 8:
                continue
            out.append(
                _block_at_minutes(
                    dday,
                    end_m,
                    br_end,
                    title="Break",
                    category="break",
                    source="break",
                )
            )
    return sort_blocks_chronological(out)


def enforce_morning_order(blocks: list[dict[str, Any]], *, day: date | None = None) -> list[dict[str, Any]]:
    """Push study blocks to start at or after morning floor; sort chronologically."""
    day = day or date.today()
    routines = []
    calendar = []
    for b in blocks:
        if str(b.get("source") or "") == "routine":
            routines.append(b)
        else:
            calendar.append(b)
    floor = morning_study_floor_min(day=day, routines=routines, calendar_blocks=calendar)

    adjusted: list[dict[str, Any]] = []
    for b in blocks:
        if not _is_study_block(b):
            adjusted.append(b)
            continue
        interval = _parse_block_interval_minutes(b, day)
        if interval is None:
            adjusted.append(b)
            continue
        start_m, end_m = interval
        if start_m >= floor:
            adjusted.append(b)
            continue
        dur = max(10, end_m - start_m)
        new_start = floor
        new_end = new_start + dur
        y, mo, d = day.year, day.month, day.day
        tz = local_tz()
        out = dict(b)
        out["start_at"] = (datetime(y, mo, d, 0, 0, tzinfo=tz) + timedelta(minutes=new_start)).isoformat()
        out["end_at"] = (datetime(y, mo, d, 0, 0, tzinfo=tz) + timedelta(minutes=new_end)).isoformat()
        adjusted.append(out)

    return sort_blocks_chronological(adjusted)


def apply_day_rhythm(
    blocks: list[dict[str, Any]],
    *,
    day: date | None = None,
    routines: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Routine-first mornings + study floor + break after every task."""
    day = day or date.today()
    ordered = sort_blocks_chronological(blocks)
    stepped = ensure_day_starts_with_routine(ordered, day=day, routines=routines)
    stepped = enforce_morning_order(stepped, day=day)
    return insert_breaks_after_study_tasks(stepped, day=day)


def sort_blocks_chronological(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def _key(b: dict[str, Any]) -> tuple:
        try:
            start = datetime.fromisoformat(str(b.get("start_at") or "").replace("Z", "+00:00"))
            if start.tzinfo is None:
                start = start.replace(tzinfo=local_tz())
            start = start.astimezone(local_tz())
            sm = start.hour * 60 + start.minute
        except (TypeError, ValueError):
            sm = 99 * 60
        src = str(b.get("source") or "")
        src_pri = 0 if src == "routine" else (1 if src == "existing" else 2)
        cat = str(b.get("category") or "").lower()
        cat_pri = 0 if cat == "spiritual" else (1 if cat in ("personal", "food") else 3)
        study_pri = 1 if _is_study_block(b) else 0
        return (sm, study_pri, src_pri, cat_pri, str(b.get("title") or ""))

    return sorted(blocks, key=_key)


def morning_order_rule_text(
    *,
    day: date | None = None,
    routines: list[dict[str, Any]] | None = None,
    calendar_blocks: list[dict[str, Any]] | None = None,
) -> str:
    day = day or date.today()
    floor = morning_study_floor_min(
        day=day, routines=routines, calendar_blocks=calendar_blocks
    )
    hh, mm = divmod(floor, 60)
    return (
        f"Day starts with routines · study after {hh:02d}:{mm:02d} · break after each task"
    )
