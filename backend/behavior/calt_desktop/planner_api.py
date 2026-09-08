"""Direct planner API for desktop (same backend as /api/planner routes)."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from backend.db.base import SessionLocal
from backend.models.planner import PlannerBlock
from backend.models.planner_routine import PlannerRoutine
from backend.paths import ROOT
from backend.planner.service import (
    _minutes_between,
    _utc,
    local_day_bounds_utc,
    local_tz,
    serialize_block,
)
from backend.planner.routines import (
    apply_routines,
    seed_default_routines,
    serialize_routine,
    upgrade_stock_default_routines,
)

_GOALS_PATH = ROOT / "data" / "behavior" / "productivity_goals.json"

_DEFAULT_GOALS: dict[str, Any] = {
    "focusHoursPerDay": 4,
    "weeklyFocusHours": 24,
    "mainGoal": "Complete daily study blocks before entertainment.",
    "reward": "Free time after on-plan focus target.",
    "extraGoals": [],
    "studyTasks": [],
}


def load_goals() -> dict[str, Any]:
    try:
        if _GOALS_PATH.is_file():
            data = json.loads(_GOALS_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return {**_DEFAULT_GOALS, **data}
    except (OSError, ValueError, TypeError):
        pass
    return dict(_DEFAULT_GOALS)


def save_goals(data: dict[str, Any], *, user_id: int | None = None) -> dict[str, Any]:
    _GOALS_PATH.parent.mkdir(parents=True, exist_ok=True)
    merged = {**load_goals(), **data}
    _GOALS_PATH.write_text(json.dumps(merged, indent=2), encoding="utf-8")
    if user_id:
        try:
            from backend.behavior.productivity_policy import update_policy

            db = SessionLocal()
            try:
                update_policy(
                    db,
                    user_id,
                    {
                        "daily_goal_minutes": focus_hours_to_goal_minutes(
                            merged.get("focusHoursPerDay", 4)
                        )
                    },
                )
                db.commit()
            finally:
                db.close()
        except Exception:  # noqa: BLE001
            pass
    return merged


def focus_hours_to_goal_minutes(hours: float) -> int:
    return min(960, max(15, int(round(float(hours) * 60))))


def format_goals_for_prompt(goals: dict[str, Any] | None = None) -> str:
    """Match web ProductivityGoalsPanel.formatGoalsForPrompt."""
    g = goals or load_goals()
    extras = g.get("extraGoals") or []
    extra_block = ""
    if isinstance(extras, list):
        titled = [
            str(x.get("title") or "").strip()
            for x in extras
            if isinstance(x, dict) and str(x.get("title") or "").strip()
        ]
        if titled:
            extra_block = f" Extra goals/todos: {'; '.join(titled)}."
    tasks = g.get("studyTasks") or []
    task_block = ""
    if isinstance(tasks, list):
        lines = []
        for t in tasks:
            if not isinstance(t, dict):
                continue
            title = str(t.get("title") or "").strip()
            if not title:
                continue
            mins = int(t.get("minutes") or 60)
            allow = ", ".join(t.get("allowHosts") or [])[:120]
            block = ", ".join(t.get("blockCategories") or [])[:80]
            lines.append(f"{title} ({mins}m; allow {allow or 'study sites'}; block {block or 'distractions'})")
        if lines:
            task_block = " Study tasks: " + " | ".join(lines) + "."
    return (
        f"{g.get('mainGoal', '')} Daily effective-focus target: {g.get('focusHoursPerDay', 4)}h. "
        f"Weekly target: {g.get('weeklyFocusHours', 24)}h. Reward: {g.get('reward', '')}.{extra_block}{task_block}"
    )


def list_routines(user_id: int) -> list[dict[str, Any]]:
    db = SessionLocal()
    try:
        upgrade_stock_default_routines(db, user_id)
        rows = (
            db.query(PlannerRoutine)
            .filter(PlannerRoutine.user_id == user_id)
            .order_by(PlannerRoutine.sort_order, PlannerRoutine.id)
            .all()
        )
        return [serialize_routine(r) for r in rows]
    finally:
        db.close()


def seed_routine_defaults(user_id: int) -> int:
    db = SessionLocal()
    try:
        n = seed_default_routines(db, user_id)
        upgrade_stock_default_routines(db, user_id)
        db.commit()
        return n
    finally:
        db.close()


def apply_routines_today(user_id: int) -> dict[str, Any]:
    db = SessionLocal()
    try:
        created = apply_routines(db, user_id, target_date=date.today(), skip_overlaps=True)
        db.commit()
        return {"created": len(created)}
    finally:
        db.close()


def reorder_morning_routines(user_id: int) -> int:
    db = SessionLocal()
    try:
        from backend.planner.routines import upgrade_stock_default_routines

        return upgrade_stock_default_routines(db, user_id)
    finally:
        db.close()


def propose_week(
    user_id: int,
    *,
    goals: str,
    horizon_days: int = 7,
    use_llm: bool = True,
    mode: str = "smart",
    draft_blocks: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    from backend.models import User
    from backend.planner.llm_propose import propose_week_from_export
    from backend.planner.week_export import build_productivity_week_export, filter_export_payload

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if user is None:
            raise ValueError("user not found")
        payload = build_productivity_week_export(db, user, days=7)
        payload = filter_export_payload(
            payload,
            include={"summary", "patterns", "hints", "policy", "by_day", "wearable"},
            productive_only=False,
        )
        range_start = datetime.now(local_tz()).date()
        rows = (
            db.query(PlannerRoutine)
            .filter(PlannerRoutine.user_id == user_id, PlannerRoutine.enabled.is_(True))
            .order_by(PlannerRoutine.sort_order, PlannerRoutine.id)
            .all()
        )
        routines = [serialize_routine(r) for r in rows]
        start_utc, _ = local_day_bounds_utc(range_start)
        _, end_utc = local_day_bounds_utc(range_start + timedelta(days=max(1, horizon_days) - 1))
        cal_rows = (
            db.query(PlannerBlock)
            .filter(
                PlannerBlock.user_id == user_id,
                PlannerBlock.start_at < end_utc,
                PlannerBlock.end_at > start_utc,
            )
            .all()
        )
        busy_blocks = [
            {
                "title": b.title,
                "category": b.category,
                "start_at": serialize_block(b)["start_at"],
                "end_at": serialize_block(b)["end_at"],
            }
            for b in cal_rows
        ]
        return propose_week_from_export(
            payload,
            goals=goals,
            range_start=range_start,
            week_start=range_start,
            horizon_days=horizon_days,
            use_llm=use_llm,
            routines=routines,
            mode=mode,
            draft_blocks=draft_blocks,
            busy_blocks=busy_blocks,
            db=db,
            user_id=user_id,
        )
    finally:
        db.close()


def run_propose_merged(
    user_id: int,
    *,
    goals: str,
    horizon_days: int = 7,
    use_llm: bool = True,
    mode: str = "smart",
    draft_blocks: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """API propose + web-style client merge."""
    from backend.behavior.calt_desktop.planner_data import blocks_for_range
    from backend.behavior.calt_desktop.planner_propose_merge import merge_propose_result

    range_start = datetime.now(local_tz()).date()
    res = propose_week(
        user_id,
        goals=goals,
        horizon_days=horizon_days,
        use_llm=use_llm,
        mode=mode,
        draft_blocks=draft_blocks,
    )
    calendar = blocks_for_range(user_id, range_start, horizon_days)
    routines = list_routines(user_id)
    merged = merge_propose_result(
        api_blocks=list(res.get("blocks") or []),
        calendar_blocks=calendar,
        routines=routines,
        range_start=range_start,
        horizon_days=horizon_days,
    )
    return {**res, "blocks": merged, "merged_count": len(merged)}


def reorder_routine_ids(user_id: int, ordered_ids: list[int]) -> int:
    db = SessionLocal()
    try:
        rows = {
            r.id: r
            for r in db.query(PlannerRoutine)
            .filter(PlannerRoutine.user_id == user_id)
            .all()
        }
        n = 0
        for i, rid in enumerate(ordered_ids):
            row = rows.get(rid)
            if row is None:
                continue
            if row.sort_order != i:
                row.sort_order = i
                n += 1
        db.commit()
        return n
    finally:
        db.close()


def apply_my_day_api(user_id: int, **kwargs: Any) -> dict[str, Any]:
    from backend.behavior.calt_desktop.day_coach import apply_my_day

    return apply_my_day(user_id, **kwargs)


def revert_last_apply_api(user_id: int) -> dict[str, Any]:
    from backend.behavior.calt_desktop.apply_snapshot import revert_last_apply

    return revert_last_apply(user_id)


ROUTINE_DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def create_routine(user_id: int, body: dict[str, Any]) -> dict[str, Any]:
    db = SessionLocal()
    try:
        days = body.get("days") or list(ROUTINE_DAYS)
        row = PlannerRoutine(
            user_id=user_id,
            title=str(body.get("title") or "Routine").strip()[:200],
            category=str(body.get("category") or "personal").strip()[:80],
            start_time=str(body.get("start_time") or "09:00"),
            end_time=body.get("end_time"),
            duration_minutes=int(body.get("duration_minutes") or 30),
            days_json=json.dumps(days),
            color=body.get("color"),
            enabled=bool(body.get("enabled", True)),
            sort_order=int(body.get("sort_order") or 0),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return serialize_routine(row)
    finally:
        db.close()


def update_routine(user_id: int, routine_id: int, patch: dict[str, Any]) -> dict[str, Any]:
    db = SessionLocal()
    try:
        row = (
            db.query(PlannerRoutine)
            .filter(PlannerRoutine.id == routine_id, PlannerRoutine.user_id == user_id)
            .first()
        )
        if row is None:
            raise KeyError("Routine not found")
        if "days" in patch:
            row.days_json = json.dumps(patch.pop("days"))
        for k, v in patch.items():
            if hasattr(row, k):
                setattr(row, k, v)
        db.commit()
        db.refresh(row)
        return serialize_routine(row)
    finally:
        db.close()


def delete_routine(user_id: int, routine_id: int) -> None:
    db = SessionLocal()
    try:
        row = (
            db.query(PlannerRoutine)
            .filter(PlannerRoutine.id == routine_id, PlannerRoutine.user_id == user_id)
            .first()
        )
        if row is None:
            raise KeyError("Routine not found")
        db.delete(row)
        db.commit()
    finally:
        db.close()


def apply_proposed_filtered(
    user_id: int,
    blocks: list[dict[str, Any]],
    *,
    range_start: date | None = None,
    range_end: date | None = None,
) -> dict[str, Any]:
    from backend.behavior.calt_desktop.planner_propose_merge import blocks_for_apply

    to_apply = blocks_for_apply(
        blocks,
        range_start=range_start or date.today(),
        range_end=range_end or date.today(),
    )
    payload = [
        {
            "title": b.get("title"),
            "category": b.get("category"),
            "start_at": b.get("start_at"),
            "end_at": b.get("end_at"),
        }
        for b in to_apply
    ]
    return apply_proposed_blocks(user_id, payload)


def apply_proposed_blocks(user_id: int, blocks: list[dict[str, Any]]) -> dict[str, Any]:
    from backend.planner.routines import _has_overlap

    db = SessionLocal()
    try:
        created: list[PlannerBlock] = []
        skipped = 0
        for raw in blocks or []:
            if not isinstance(raw, dict):
                continue
            title = str(raw.get("title") or "Study block").strip()[:200]
            category = str(raw.get("category") or "study").strip()[:80]
            start_raw = raw.get("start_at")
            end_raw = raw.get("end_at")
            if not start_raw or not end_raw:
                continue
            try:
                start = _utc(datetime.fromisoformat(str(start_raw).replace("Z", "+00:00")))
                end = _utc(datetime.fromisoformat(str(end_raw).replace("Z", "+00:00")))
            except ValueError:
                continue
            if end <= start:
                continue
            if _has_overlap(db, user_id, start, end):
                skipped += 1
                continue
            minutes = _minutes_between(start, end)
            block = PlannerBlock(
                user_id=user_id,
                title=title,
                category=category,
                start_at=start,
                end_at=end,
                planned_minutes=minutes,
                remaining_minutes=minutes,
                status="scheduled",
            )
            db.add(block)
            created.append(block)
        db.commit()
        for b in created:
            db.refresh(b)
        return {
            "created": len(created),
            "skipped_overlaps": skipped,
            "blocks": [serialize_block(b) for b in created],
        }
    finally:
        db.close()


def fetch_actual_overlay(user_id: int, day: date) -> dict[str, Any]:
    """Same payload shape as GET /api/planner/overlay/actual."""
    from backend.models import User
    from backend.planner.router import overlay_actual  # noqa: PLC0415 — reuse route logic

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if user is None:
            return {"sessions": [], "hour_slices": []}
        start, end = local_day_bounds_utc(day)
        return overlay_actual(from_dt=start, to_dt=end, db=db, user=user)
    finally:
        db.close()


def google_calendar_status() -> dict[str, Any]:
    from backend.planner.google_calendar import google_calendar_configured

    return google_calendar_configured()


def sync_google_calendar(user_id: int, *, days: int = 14) -> dict[str, Any]:
    from backend.models import User
    from backend.planner.google_calendar import sync_blocks_to_google

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if user is None:
            return {"ok": False, "error": "no user"}
        start = datetime.now(timezone.utc)
        end = start + timedelta(days=days)
        blocks = (
            db.query(PlannerBlock)
            .filter(
                PlannerBlock.user_id == user_id,
                PlannerBlock.start_at < end,
                PlannerBlock.end_at > start,
                PlannerBlock.status.notin_(("cancelled", "rolled")),
            )
            .order_by(PlannerBlock.start_at.asc())
            .all()
        )
        return sync_blocks_to_google(blocks)
    finally:
        db.close()
