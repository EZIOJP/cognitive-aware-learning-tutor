"""Port of web propose merge (ProductivityPage + resolveProposedOverlaps + planVsActualUtils)."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

from backend.planner.service import local_tz

ROUTINE_WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
DAY_END_MIN = 23 * 60  # fallback; prefer sleep_anchor.day_end_minutes()


def effective_day_end_min(*, wake_hm: str | None = None) -> int:
    try:
        from backend.behavior.calt_desktop.sleep_anchor import day_end_minutes

        return day_end_minutes(wake_hm or "06:00")
    except Exception:  # noqa: BLE001
        return DAY_END_MIN


def _parse_iso(iso: str) -> datetime:
    raw = (iso or "").strip()
    if raw and not raw.endswith("Z") and "+" not in raw[-6:] and "-" not in raw[-6:]:
        raw = f"{raw}Z"
    dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(local_tz())


def _day_key(iso: str) -> str:
    d = _parse_iso(iso)
    return d.date().isoformat()


def _norm_title(title: str) -> str:
    return " ".join((title or "").strip().lower().split())


def draft_covered_by_saved_blocks(
    draft: dict[str, Any],
    blocks: list[dict[str, Any]],
) -> bool:
    try:
        ds = _parse_iso(str(draft.get("start_at") or ""))
        de = _parse_iso(str(draft.get("end_at") or ""))
    except ValueError:
        return False
    nt = _norm_title(str(draft.get("title") or ""))
    draft_ms = max(1, int((de - ds).total_seconds() * 1000))

    for b in blocks:
        if str(b.get("status") or "") == "rolled":
            continue
        try:
            bs = _parse_iso(str(b.get("start_at") or ""))
            be = _parse_iso(str(b.get("end_at") or ""))
        except ValueError:
            continue
        if ds.date() != bs.date():
            continue
        if _norm_title(str(b.get("title") or "")) == nt:
            return True
        overlap_ms = int(
            (min(de, be) - max(ds, bs)).total_seconds() * 1000
        )
        if overlap_ms > 0 and overlap_ms / draft_ms >= 0.6:
            return True
    return False


def blocks_overlap(a: dict[str, Any], b: dict[str, Any]) -> bool:
    try:
        as_ = _parse_iso(str(a.get("start_at") or ""))
        ae = _parse_iso(str(a.get("end_at") or ""))
        bs = _parse_iso(str(b.get("start_at") or ""))
        be = _parse_iso(str(b.get("end_at") or ""))
    except ValueError:
        return False
    return as_ < be and bs < ae


def materialize_routine_blocks(
    routines: list[dict[str, Any]],
    range_start: date,
    horizon_days: int,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for i in range(max(1, horizon_days)):
        day = range_start + timedelta(days=i)
        key = ROUTINE_WEEKDAYS[(day.weekday())]
        for r in routines:
            if not r.get("enabled"):
                continue
            days = r.get("days") or list(ROUTINE_WEEKDAYS)
            if key not in days:
                continue
            sh, sm = (int(x) for x in str(r.get("start_time") or "09:00").split(":", 1))
            if r.get("end_time"):
                eh, em = (int(x) for x in str(r["end_time"]).split(":", 1))
            else:
                total = sh * 60 + sm + max(1, int(r.get("duration_minutes") or 30))
                eh, em = total // 60 % 24, total % 60
            tz = local_tz()
            start = datetime(day.year, day.month, day.day, sh, sm, tzinfo=tz)
            end = datetime(day.year, day.month, day.day, eh, em, tzinfo=tz)
            if end <= start:
                end = start + timedelta(minutes=30)
            out.append(
                {
                    "title": r.get("title") or "Routine",
                    "category": r.get("category") or "personal",
                    "start_at": start.isoformat(),
                    "end_at": end.isoformat(),
                    "source": "routine",
                }
            )
    return out


def _source_priority(source: str | None) -> int:
    if source == "routine":
        return 0
    if source == "existing":
        return 1
    if source in ("study", None, ""):
        return 2
    if source == "break":
        return 3
    return 4


def _category_priority(category: str | None) -> int:
    """Morning-first when smart-fill packs study after routines."""
    c = str(category or "").lower()
    if c == "spiritual":
        return 0
    if c == "personal":
        return 1
    if c == "food":
        return 2
    if c in ("study", "coursework", "work"):
        return 3
    return 4


def _duration_min(b: dict[str, Any]) -> int:
    try:
        s = _parse_iso(str(b.get("start_at") or ""))
        e = _parse_iso(str(b.get("end_at") or ""))
    except ValueError:
        return 10
    return max(10, int((e - s).total_seconds() // 60))


def _start_min(b: dict[str, Any]) -> int:
    d = _parse_iso(str(b.get("start_at") or ""))
    return d.hour * 60 + d.minute


def _with_local_range(b: dict[str, Any], day: str, start_m: int, end_m: int) -> dict[str, Any]:
    y, mo, d = (int(x) for x in day.split("-"))
    tz = local_tz()
    start = datetime(y, mo, d, 0, 0, tzinfo=tz) + timedelta(minutes=start_m)
    end = datetime(y, mo, d, 0, 0, tzinfo=tz) + timedelta(minutes=end_m)
    out = dict(b)
    out["start_at"] = start.isoformat()
    out["end_at"] = end.isoformat()
    return out


def _nearly_same(a: dict[str, Any], b: dict[str, Any]) -> bool:
    if _norm_title(str(a.get("title") or "")) != _norm_title(str(b.get("title") or "")):
        return False
    if str(a.get("source") or "study") != str(b.get("source") or "study"):
        return False
    try:
        ta = _parse_iso(str(a.get("start_at") or ""))
        tb = _parse_iso(str(b.get("start_at") or ""))
    except ValueError:
        return False
    return abs((ta - tb).total_seconds()) < 120


def resolve_proposed_overlaps(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if len(blocks) <= 1:
        return list(blocks)

    deduped: list[dict[str, Any]] = []
    for b in blocks:
        if any(_nearly_same(x, b) for x in deduped):
            continue
        deduped.append(b)

    by_day: dict[str, list[dict[str, Any]]] = {}
    for b in deduped:
        k = _day_key(str(b.get("start_at") or ""))
        by_day.setdefault(k, []).append(b)

    out: list[dict[str, Any]] = []
    for day in sorted(by_day.keys()):
        from backend.planner.morning_order import _is_study_block

        sorted_blocks = sorted(
            by_day[day],
            key=lambda b: (
                _start_min(b),
                1 if _is_study_block(b) else 0,
                _source_priority(str(b.get("source") or "")),
                _category_priority(str(b.get("category") or "")),
            ),
        )
        cursor = -1
        for b in sorted_blocks:
            s = _start_min(b)
            dur = _duration_min(b)
            if s < cursor:
                s = cursor
            e = s + dur
            day_cap = effective_day_end_min()
            if e > day_cap:
                if s >= day_cap - 5:
                    continue
                e = day_cap
                dur = e - s
                if dur < 10:
                    continue
            out.append(_with_local_range(b, day, s, e))
            cursor = e
    return out


def merge_propose_result(
    *,
    api_blocks: list[dict[str, Any]],
    calendar_blocks: list[dict[str, Any]],
    routines: list[dict[str, Any]],
    range_start: date,
    horizon_days: int,
) -> list[dict[str, Any]]:
    """Same merge as ProductivityPage.runPropose after API returns."""
    today_key = range_start.isoformat()

    existing: list[dict[str, Any]] = [
        {
            "title": b.get("title"),
            "category": b.get("category"),
            "start_at": b.get("start_at"),
            "end_at": b.get("end_at"),
            "source": "existing",
            "existing_id": b.get("id"),
        }
        for b in calendar_blocks
    ]

    proposed_fresh: list[dict[str, Any]] = []
    for b in api_blocks or []:
        if not isinstance(b, dict):
            continue
        row = {**b, "source": b.get("source") or "study"}
        if not draft_covered_by_saved_blocks(row, calendar_blocks):
            proposed_fresh.append(row)

    has_routine_from_api = any(str(b.get("source") or "") == "routine" for b in proposed_fresh)
    routine_blocks: list[dict[str, Any]] = []
    if not has_routine_from_api:
        routine_blocks = [
            r
            for r in materialize_routine_blocks(
                [x for x in routines if x.get("enabled")],
                range_start,
                horizon_days,
            )
            if not draft_covered_by_saved_blocks(r, calendar_blocks)
        ]

    proposed_core = [
        *[
            r
            for r in routine_blocks
            if not any(blocks_overlap(r, p) for p in proposed_fresh)
        ],
        *proposed_fresh,
    ]
    existing_overlay = [
        e for e in existing if not any(blocks_overlap(e, p) for p in proposed_core)
    ]
    merged_raw = [*proposed_core, *existing_overlay]
    merged_filtered = [
        b
        for b in merged_raw
        if _day_key(str(b.get("start_at") or "")) >= today_key
    ]
    resolved = resolve_proposed_overlaps(merged_filtered)
    from backend.planner.morning_order import apply_day_rhythm, sort_blocks_chronological

    rhythm = apply_day_rhythm(
        resolved,
        day=range_start,
        routines=[x for x in routines if x.get("enabled")],
    )
    # Rhythm inserts breaks that can re-overlap study — cascade again (desktop + web).
    cascaded = resolve_proposed_overlaps(rhythm)
    return sort_blocks_chronological(cascaded)


def blocks_for_apply(
    proposed: list[dict[str, Any]],
    *,
    range_start: date | None = None,
    range_end: date | None = None,
) -> list[dict[str, Any]]:
    """Filter like web apply — skip existing overlays and past days."""
    today_key = (range_start or date.today()).isoformat()
    end_key = (range_end or date.today()).isoformat()
    out: list[dict[str, Any]] = []
    for b in proposed or []:
        if str(b.get("source") or "") == "existing":
            continue
        lk = _day_key(str(b.get("start_at") or ""))
        if lk < today_key:
            continue
        if lk > end_key:
            continue
        out.append(b)
    return out
