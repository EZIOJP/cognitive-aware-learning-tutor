"""Day coach — apply my day, drift, study-task blocks, weekly goals."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from backend.behavior.calt_desktop.planner_api import (
    apply_proposed_filtered,
    apply_routines_today,
    format_goals_for_prompt,
    load_goals,
    reorder_morning_routines,
    run_propose_merged,
)
from backend.behavior.calt_desktop.planner_data import blocks_for_day
from backend.behavior.calt_desktop.sleep_anchor import (
    DEFAULT_WAKE_HM,
    clamp_block_to_sleep,
    day_end_minutes,
    day_start_minutes,
)
from backend.planner.service import local_tz


def current_week_key(d: date | None = None) -> str:
    d = d or date.today()
    iso = d.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def ensure_weekly_goals(*, goals: dict[str, Any] | None = None) -> dict[str, Any]:
    """Reset study tasks when ISO week rolls — journeys/extras not auto-carried."""
    from backend.behavior.calt_desktop.planner_api import save_goals

    g = dict(goals or load_goals())
    wk = current_week_key()
    if str(g.get("weekKey") or "") == wk:
        return g
    g["weekKey"] = wk
    g["weeklyFocusHours"] = int(g.get("weeklyFocusHours") or 24)
    # Keep studyTasks if user set them this session; clear stale journey carry
    if g.get("carryJourneys") is not True:
        g.setdefault("studyTasks", [])
    save_goals(g)
    return g


def materialize_study_task_blocks(
    user_id: int,
    *,
    day: date | None = None,
    wake_hm: str = DEFAULT_WAKE_HM,
    study_tasks: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Pack studyTasks from goals into free gaps after routines."""
    day = day or date.today()
    if study_tasks is not None:
        tasks = [t for t in study_tasks if isinstance(t, dict)]
    else:
        goals = ensure_weekly_goals()
        tasks = [t for t in (goals.get("studyTasks") or []) if isinstance(t, dict)]
    if not tasks or not user_id:
        return []

    existing = blocks_for_day(user_id, day)
    busy: list[tuple[int, int]] = []
    for b in existing:
        try:
            s = datetime.fromisoformat(str(b["start_at"]).replace("Z", "+00:00")).astimezone(local_tz())
            e = datetime.fromisoformat(str(b["end_at"]).replace("Z", "+00:00")).astimezone(local_tz())
            busy.append((s.hour * 60 + s.minute, e.hour * 60 + e.minute))
        except (ValueError, KeyError):
            continue
    busy.sort()

    from backend.planner.morning_order import morning_study_floor_min

    floor = morning_study_floor_min(day=day, calendar_blocks=existing)
    day_end = day_end_minutes(wake_hm)
    cursor = max(day_start_minutes(wake_hm), floor)
    out: list[dict[str, Any]] = []

    def _advance_cursor() -> None:
        nonlocal cursor
        for s, e in busy:
            if cursor < e and cursor >= s:
                cursor = e
            elif cursor < s:
                break

    for task in tasks:
        title = str(task.get("title") or "Study").strip()
        mins = max(25, int(task.get("minutes") or 60))
        _advance_cursor()
        while cursor + mins > day_end:
            if cursor >= day_end - 10:
                break
            mins = max(25, mins - 15)
            if mins < 25:
                break
        if cursor + mins > day_end:
            continue
        # skip overlaps
        end_m = cursor + mins
        overlap = any(not (end_m <= s or cursor >= e) for s, e in busy)
        if overlap:
            cursor += 15
            continue
        tz = local_tz()
        start_dt = datetime(day.year, day.month, day.day, 0, 0, tzinfo=tz) + timedelta(minutes=cursor)
        end_dt = start_dt + timedelta(minutes=mins)
        row = {
            "title": title,
            "category": "study",
            "start_at": start_dt.isoformat(),
            "end_at": end_dt.isoformat(),
            "source": "study",
            "study_task": task,
        }
        clamped = clamp_block_to_sleep(row, wake_hm=wake_hm)
        if clamped:
            out.append(clamped)
            br_start = cursor + mins
            br_end = br_start + 10
            if br_end <= day_end and br_end - br_start >= 8:
                br_start_dt = datetime(day.year, day.month, day.day, 0, 0, tzinfo=tz) + timedelta(
                    minutes=br_start
                )
                br_end_dt = datetime(day.year, day.month, day.day, 0, 0, tzinfo=tz) + timedelta(
                    minutes=br_end
                )
                out.append(
                    {
                        "title": "Break",
                        "category": "break",
                        "start_at": br_start_dt.isoformat(),
                        "end_at": br_end_dt.isoformat(),
                        "source": "break",
                    }
                )
                busy.append((br_start, br_end))
            busy.append((cursor, cursor + mins))
            busy.sort()
            cursor = cursor + mins + 10

    return out


def plan_drift_summary(user_id: int, *, day: date | None = None) -> dict[str, Any]:
    """Plan vs actual for today — sessions from overlay API."""
    from backend.behavior.calt_desktop.planner_api import fetch_actual_overlay

    day = day or date.today()
    blocks = blocks_for_day(user_id, day)
    overlay = fetch_actual_overlay(user_id, day) if user_id else {"sessions": []}
    sessions = list(overlay.get("sessions") or [])
    lines: list[str] = []
    late = 0
    skipped = 0
    now = datetime.now(local_tz())

    for b in blocks:
        title = str(b.get("title") or "Block")[:40]
        try:
            start = datetime.fromisoformat(str(b["start_at"]).replace("Z", "+00:00")).astimezone(local_tz())
            end = datetime.fromisoformat(str(b["end_at"]).replace("Z", "+00:00")).astimezone(local_tz())
        except (ValueError, KeyError):
            continue
        matched = False
        for sess in sessions:
            st = str(sess.get("title") or sess.get("label") or "").lower()
            if title.lower()[:20] in st or st[:20] in title.lower():
                matched = True
                try:
                    actual_start = datetime.fromisoformat(str(sess.get("start_at") or "").replace("Z", "+00:00"))
                    delta = int((actual_start.astimezone(local_tz()) - start).total_seconds() // 60)
                    if abs(delta) >= 8:
                        late += 1
                        sign = "+" if delta > 0 else ""
                        lines.append(f"{title}: planned {start.strftime('%H:%M')}, started {sign}{delta}m")
                except (ValueError, TypeError):
                    pass
                break
        if not matched and end < now:
            skipped += 1
            lines.append(f"{title}: no session logged (skipped?)")

    return {
        "lines": lines[:6],
        "late_count": late,
        "skipped_count": skipped,
        "block_count": len(blocks),
        "summary": (
            f"{len(blocks)} blocks · {late} late · {skipped} unmatched"
            if blocks
            else "No blocks planned yet"
        ),
    }


def apply_my_day(
    user_id: int,
    *,
    wake_hm: str = DEFAULT_WAKE_HM,
    snapshot: bool = True,
    goals_prompt: str | None = None,
    study_tasks: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """One button: morning order → routines → smart fill → study tasks."""
    from backend.behavior.calt_desktop.apply_snapshot import save_before_apply

    if not user_id:
        return {"ok": False, "error": "no user"}

    snap_n = 0
    if snapshot:
        snap_n = save_before_apply(user_id, label="apply_my_day")

    reorder_morning_routines(user_id)
    routine_res = apply_routines_today(user_id)

    goals = goals_prompt or format_goals_for_prompt(ensure_weekly_goals())
    propose = run_propose_merged(
        user_id,
        goals=goals,
        horizon_days=1,
        use_llm=False,
        mode="smart",
    )
    blocks = list(propose.get("blocks") or [])
    task_blocks = materialize_study_task_blocks(
        user_id, wake_hm=wake_hm, study_tasks=study_tasks
    )
    # merge task blocks not covered
    from backend.behavior.calt_desktop.planner_propose_merge import draft_covered_by_saved_blocks

    calendar = blocks_for_day(user_id, date.today())
    for tb in task_blocks:
        if not draft_covered_by_saved_blocks(tb, calendar):
            blocks.append(tb)

    apply_res = apply_proposed_filtered(user_id, blocks, range_start=date.today(), range_end=date.today())

    return {
        "ok": True,
        "snapshot_blocks": snap_n,
        "routines_created": routine_res.get("created", 0),
        "study_created": apply_res.get("created", 0),
        "skipped_overlaps": apply_res.get("skipped_overlaps", 0),
        "sleep": day_end_minutes(wake_hm),
    }


def spine_blocks(user_id: int, *, day: date | None = None) -> list[dict[str, Any]]:
    """Ordered blocks for Today spine UI."""
    day = day or date.today()
    blocks = blocks_for_day(user_id, day)
    now = datetime.now(local_tz())

    for b in blocks:
        try:
            start = datetime.fromisoformat(str(b["start_at"]).replace("Z", "+00:00")).astimezone(local_tz())
            end = datetime.fromisoformat(str(b["end_at"]).replace("Z", "+00:00")).astimezone(local_tz())
        except (ValueError, KeyError):
            b["spine_state"] = "pending"
            continue
        if end <= now:
            b["spine_state"] = "done"
        elif start <= now < end:
            b["spine_state"] = "active"
        else:
            b["spine_state"] = "pending"
    return blocks
