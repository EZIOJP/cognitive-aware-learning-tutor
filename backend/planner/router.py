import json
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.orm import Session

from backend.core.auth import get_current_user
from backend.db.session import get_db
from backend.models import User
from backend.models.planner import PlannerBlock
from backend.models.timetable import Timetable, TrackedSession
from backend.models.planner_routine import PlannerRoutine
from backend.timetable.tracker_query import tracker_user_ids
from backend.planner.routines import (
    apply_routines,
    auto_apply_routines_today,
    seed_default_routines,
    serialize_routine,
    slots_to_planner_blocks,
    upgrade_stock_default_routines,
)
from backend.planner.schemas import (
    ApplyDayRhythmBody,
    ApplyMyDayBody,
    ApplyProposedBlocksBody,
    ApplyRoutinesBody,
    CompleteBlockBody,
    GenerateDayBody,
    GenerateWeekBody,
    GoogleOAuthCredentialsBody,
    MergeProposeBody,
    PlannerBlockCreate,
    PlannerBlockUpdate,
    ProposeFromExportBody,
    RollForwardBody,
    RoutineCreate,
    RoutineUpdate,
)
from backend.planner.service import (
    _minutes_between,
    _utc,
    iso_utc,
    local_day_bounds_utc,
    local_tz,
    complete_block,
    end_from_start_and_minutes,
    roll_forward_block,
    serialize_block,
    slot_datetime,
    suggest_next_slot,
)

router = APIRouter(prefix="/api/planner", tags=["planner"])


def _get_block(db: Session, user_id: int, block_id: int) -> PlannerBlock:
    block = (
        db.query(PlannerBlock)
        .filter(PlannerBlock.id == block_id, PlannerBlock.user_id == user_id)
        .first()
    )
    if block is None:
        raise HTTPException(status_code=404, detail="Block not found")
    return block


@router.get("/blocks", response_model=dict)
def list_blocks(
    from_dt: datetime = Query(..., alias="from"),
    to_dt: datetime = Query(..., alias="to"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    start = _utc(from_dt)
    end = _utc(to_dt)
    blocks = (
        db.query(PlannerBlock)
        .filter(
            PlannerBlock.user_id == user.id,
            PlannerBlock.start_at < end,
            PlannerBlock.end_at > start,
        )
        .order_by(PlannerBlock.start_at)
        .all()
    )
    return {"blocks": [serialize_block(b) for b in blocks]}


@router.post("/blocks", response_model=dict)
def create_block(
    body: PlannerBlockCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    start = _utc(body.start_at)
    if body.duration_minutes is not None:
        minutes = body.duration_minutes
        end = end_from_start_and_minutes(start, minutes)
    else:
        end = _utc(body.end_at)  # type: ignore[arg-type]
        minutes = _minutes_between(start, end)

    block = PlannerBlock(
        user_id=user.id,
        title=body.title,
        category=body.category,
        start_at=start,
        end_at=end,
        planned_minutes=minutes,
        remaining_minutes=minutes,
        status="scheduled",
        task_id=body.task_id,
        color=body.color,
    )
    db.add(block)
    db.commit()
    db.refresh(block)
    return {"block": serialize_block(block)}


@router.patch("/blocks/{block_id}", response_model=dict)
def update_block(
    block_id: int,
    body: PlannerBlockUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    block = _get_block(db, user.id, block_id)

    if body.title is not None:
        block.title = body.title
    if body.category is not None:
        block.category = body.category
    if body.color is not None:
        block.color = body.color
    if body.status is not None:
        block.status = body.status
    if body.remaining_minutes is not None:
        block.remaining_minutes = body.remaining_minutes

    start = _utc(body.start_at) if body.start_at else block.start_at
    if body.start_at is not None:
        block.start_at = start

    if body.duration_minutes is not None:
        mins = body.duration_minutes
        block.planned_minutes = mins
        block.remaining_minutes = mins
        block.end_at = end_from_start_and_minutes(start, mins)
    elif body.end_at is not None:
        block.end_at = _utc(body.end_at)
        block.planned_minutes = _minutes_between(block.start_at, block.end_at)
        if block.status == "scheduled":
            block.remaining_minutes = block.planned_minutes
    elif body.start_at is not None:
        block.end_at = end_from_start_and_minutes(start, block.remaining_minutes)

    db.commit()
    db.refresh(block)
    return {"block": serialize_block(block)}


@router.delete("/blocks/{block_id}", response_model=dict)
def delete_block(
    block_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    block = _get_block(db, user.id, block_id)
    db.delete(block)
    db.commit()
    return {"status": "deleted", "id": block_id}


@router.post("/blocks/{block_id}/start", response_model=dict)
def start_block(
    block_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    block = _get_block(db, user.id, block_id)
    block.status = "in_progress"
    db.commit()
    db.refresh(block)
    return {"block": serialize_block(block)}


@router.post("/blocks/{block_id}/complete", response_model=dict)
def complete_block_endpoint(
    block_id: int,
    body: CompleteBlockBody,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    block = _get_block(db, user.id, block_id)
    complete_block(block, minutes_spent=body.minutes_spent)
    db.commit()
    db.refresh(block)
    return {"block": serialize_block(block)}


@router.post("/blocks/{block_id}/roll-forward", response_model=dict)
def roll_forward_endpoint(
    block_id: int,
    body: RollForwardBody,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    block = _get_block(db, user.id, block_id)
    new_block = roll_forward_block(db, block, new_start=body.new_start)
    db.commit()
    db.refresh(block)
    db.refresh(new_block)
    return {
        "rolled_block": serialize_block(block),
        "new_block": serialize_block(new_block),
    }


@router.get("/overlay/actual", response_model=dict)
def overlay_actual(
    from_dt: datetime = Query(..., alias="from"),
    to_dt: datetime = Query(..., alias="to"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Desktop tracker + Amazfit sleep. PC time inside sleep is clipped away.

    Sleep only from watch timed windows (start_min/end_min + naps). Never invent
    midnight wedges. Cursor/idle left on overnight is overwritten by Sleep.
    """
    start = _utc(from_dt)
    end = _utc(to_dt)
    now = datetime.now(timezone.utc)
    user_ids = tracker_user_ids(db, user)

    sessions = (
        db.query(TrackedSession)
        .filter(
            TrackedSession.user_id.in_(user_ids),
            TrackedSession.source.in_(("desktop_tracker", "extension", "calt_spa")),
            TrackedSession.start_time < end,
            TrackedSession.end_time > start,
        )
        .order_by(TrackedSession.start_time)
        .all()
    )
    from backend.behavior.category_scores import load_score_map, serialize_tracked_session
    from backend.behavior.productivity_policy import load_policy_dict
    from backend.models import WearableDaily
    from backend.wearables.sleep_window import (
        clip_session_dicts_against_sleep,
        parse_sleep_dict,
        sleep_bouts,
    )

    scores = load_score_map(db)
    policy = load_policy_dict(db, user.id)
    out = [serialize_tracked_session(s, scores, policy) for s in sessions]

    sleep_events: list[dict] = []
    all_bouts: list[tuple] = []
    day0 = start.astimezone(local_tz()).date()
    day1 = end.astimezone(local_tz()).date()
    cursor = day0 - timedelta(days=1)
    last = day1 + timedelta(days=1)
    while cursor <= last:
        wd = (
            db.query(WearableDaily)
            .filter(
                WearableDaily.user_id == user.id,
                WearableDaily.local_date == cursor,
            )
            .first()
        )
        if not wd:
            cursor = cursor + timedelta(days=1)
            continue
        sleep = parse_sleep_dict(wd.payload_json)
        sm, em = sleep.get("start_min"), sleep.get("end_min")
        naps = sleep.get("naps") or []
        # Watch timed window only — reject duration-only / empty (naps alone OK)
        if sm is None and (em is None or em == -1) and not naps:
            cursor = cursor + timedelta(days=1)
            continue
        bouts = sleep_bouts(local_date=wd.local_date, sleep=sleep)
        hours = float(wd.sleep_hours or 0) or (
            float(sleep["total_min"]) / 60.0 if sleep.get("total_min") else 0.0
        )
        label = f"Sleep · {hours:.1f}h" + (
            f" · score {wd.sleep_score}" if wd.sleep_score else ""
        )
        for i, (s_dt, e_dt) in enumerate(bouts):
            s_u, e_u = _utc(s_dt), _utc(e_dt)
            if s_u >= now:
                continue
            if e_u > now:
                e_u = now
            if s_u >= end or e_u <= start or e_u <= s_u:
                continue
            all_bouts.append((s_u, e_u))
            sleep_events.append(
                {
                    "session_id": f"sleep:{wd.local_date.isoformat()}:{i}",
                    "start_time": iso_utc(s_u),
                    "end_time": iso_utc(e_u),
                    "source": "wearable_sleep",
                    "category": "Sleep",
                    "productivity_score": 0,
                    "window_title": label,
                    "app_name": "Amazfit",
                    "task_id": None,
                    "override_productive": False,
                }
            )
        cursor = cursor + timedelta(days=1)

    # Overwrite PC-on-during-sleep: Cursor/idle vanish under sleep wedges
    out = clip_session_dicts_against_sleep(out, all_bouts)
    out.extend(sleep_events)
    out.sort(key=lambda r: r.get("start_time") or "")
    from backend.planner.hour_slices import compute_hour_slices

    hour_slices = compute_hour_slices(out, tzinfo=local_tz())
    return {"sessions": out, "hour_slices": hour_slices}


@router.get("/adherence", response_model=dict)
def adherence_summary(
    day: datetime = Query(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return _adherence_for_day(db, user, day)


@router.get("/adherence/range", response_model=dict)
def adherence_range(
    days: int = Query(7, ge=1, le=31),
    end: datetime | None = Query(
        None,
        description="Inclusive end day (host-local). Defaults to today.",
    ),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """N calendar days ending on `end` (default: today)."""
    from datetime import timedelta

    end_date = _utc(end).astimezone(local_tz()).date() if end is not None else datetime.now(local_tz()).date()
    start = end_date - timedelta(days=days - 1)
    out = []
    cursor = start
    while cursor <= end_date:
        day_dt = datetime(cursor.year, cursor.month, cursor.day, tzinfo=local_tz())
        out.append(_adherence_for_day(db, user, day_dt))
        cursor = cursor + timedelta(days=1)
    return {"days": out, "start": start.isoformat(), "end": end_date.isoformat()}


def _adherence_for_day(db: Session, user: User, day: datetime) -> dict:
    # Host-local calendar day of the query instant (matches wall-clock planning).
    day_date = _utc(day).astimezone(local_tz()).date()
    start, end = local_day_bounds_utc(day_date)

    blocks = (
        db.query(PlannerBlock)
        .filter(
            PlannerBlock.user_id == user.id,
            PlannerBlock.start_at < end,
            PlannerBlock.end_at > start,
            PlannerBlock.status.in_(("scheduled", "in_progress", "done")),
        )
        .all()
    )

    from backend.behavior.tracker_ignore import is_ignored_app
    from backend.behavior.productivity_policy import load_policy_dict, resolve_session_score
    from backend.behavior.category_scores import load_score_map
    from backend.planner.day_metrics import compute_day_metrics

    sessions = (
        db.query(TrackedSession)
        .filter(
            TrackedSession.user_id.in_(tracker_user_ids(db, user)),
            TrackedSession.source.in_(("desktop_tracker", "extension", "calt_spa")),
            TrackedSession.start_time < end,
            TrackedSession.end_time > start,
        )
        .all()
    )
    sessions = [
        s
        for s in sessions
        if s.start_time
        and s.end_time
        and not is_ignored_app(s.app_name or "", s.window_title or "")
    ]

    scores = load_score_map(db)
    policy = load_policy_dict(db, user.id)
    threshold = int(policy.get("threshold") or 60)

    def score_fn(sess):
        return resolve_session_score(sess, scores, policy)

    return compute_day_metrics(day_date, blocks, sessions, score_fn, threshold=threshold)


@router.get("/export/last-7-days")
def export_productivity_last_days(
    days: int = Query(
        7,
        ge=1,
        le=366,
        description="Inclusive calendar-day window length (max 366 / ~1 leap year)",
    ),
    format: str = Query("json", pattern="^(json|csv)$"),
    include: str = Query(
        "summary,patterns,by_day,blocks,hints,policy,wearable",
        description="Comma list: summary,patterns,by_day,blocks,hints,policy,wearable",
    ),
    productive_only: bool = Query(False, description="Prefer productive metrics in by_day"),
    skip_empty: bool = Query(
        True,
        description="Omit days with no sessions, no plan, and no wearable snapshot",
    ),
    end_day: date | None = Query(
        None,
        description="Inclusive end calendar day (YYYY-MM-DD); default today",
    ),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Export recent planner, tracked usage, and optional watch metrics."""
    from fastapi.responses import Response

    from backend.planner.week_export import (
        build_productivity_week_export,
        export_as_csv,
        filter_export_payload,
    )

    payload = build_productivity_week_export(
        db, user, days=days, end_day=end_day, skip_empty=skip_empty
    )
    include_set = {p.strip() for p in include.split(",") if p.strip()}
    payload = filter_export_payload(
        payload, include=include_set, productive_only=productive_only
    )
    stamp = payload["range"]["end"].replace("-", "")
    if format == "csv":
        body = export_as_csv(payload)
        return Response(
            content=body,
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="productivity-{days}d-{stamp}.csv"',
            },
        )
    return payload


@router.get("/export/day-presence")
def export_day_presence(
    start: date = Query(..., description="Inclusive start calendar day (YYYY-MM-DD)"),
    end: date = Query(..., description="Inclusive end calendar day (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Lightweight list of days with tracked/plan/wearable signal for export calendars."""
    from backend.planner.week_export import MAX_EXPORT_DAYS, list_nonempty_export_days

    if end < start:
        start, end = end, start
    if (end - start).days + 1 > MAX_EXPORT_DAYS:
        start = end - timedelta(days=MAX_EXPORT_DAYS - 1)
    days = list_nonempty_export_days(db, user, start=start, end=end)
    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "days": days,
        "count": len(days),
    }


@router.post("/propose-from-export", response_model=dict)
def propose_from_export(
    body: ProposeFromExportBody,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """LLM (or rule-based) propose planner blocks from productivity export + routines."""
    from datetime import date as date_cls

    from backend.planner.llm_propose import propose_week_from_export
    from backend.planner.week_export import build_productivity_week_export, filter_export_payload

    payload = build_productivity_week_export(db, user, days=body.days)
    payload = filter_export_payload(
        payload,
        include={"summary", "patterns", "hints", "policy", "by_day", "wearable"},
        productive_only=False,
    )
    range_start = None
    raw_start = body.range_start or body.week_start
    if raw_start:
        range_start = date_cls.fromisoformat(raw_start[:10])

    routines: list[dict] = []
    if body.include_routines:
        rows = (
            db.query(PlannerRoutine)
            .filter(PlannerRoutine.user_id == user.id, PlannerRoutine.enabled.is_(True))
            .order_by(PlannerRoutine.sort_order, PlannerRoutine.id)
            .all()
        )
        routines = [serialize_routine(r) for r in rows]

    # Existing calendar blocks — treat as busy so propose doesn't double-book
    busy_blocks: list[dict] = []
    try:
        from datetime import timedelta as _td

        from backend.planner.service import local_day_bounds_utc, local_tz, serialize_block

        rs = range_start or datetime.now(local_tz()).date()
        start_utc, _ = local_day_bounds_utc(rs)
        _, end_utc = local_day_bounds_utc(rs + _td(days=max(1, body.horizon_days) - 1))
        cal_rows = (
            db.query(PlannerBlock)
            .filter(
                PlannerBlock.user_id == user.id,
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
    except Exception:
        busy_blocks = []

    return propose_week_from_export(
        payload,
        goals=body.goals,
        week_start=range_start,
        range_start=range_start,
        horizon_days=body.horizon_days,
        use_llm=body.use_llm,
        routines=routines,
        mode=body.mode,
        draft_blocks=body.draft_blocks,
        busy_blocks=busy_blocks,
        db=db,
        user_id=user.id,
    )


@router.post("/apply-proposed-blocks", response_model=dict)
def apply_proposed_blocks(
    body: ApplyProposedBlocksBody,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Apply previewed LLM/rule blocks to the planner calendar."""
    from backend.planner.routines import _has_overlap

    created = []
    skipped = 0
    for raw in body.blocks or []:
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
        if _has_overlap(db, user.id, start, end):
            skipped += 1
            continue
        minutes = _minutes_between(start, end)
        block = PlannerBlock(
            user_id=user.id,
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


@router.post("/apply-day-rhythm", response_model=dict)
def apply_day_rhythm_route(
    body: ApplyDayRhythmBody,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Morning-first order + study floor + breaks — same logic as CALT Desktop merge."""
    from datetime import date as date_cls

    from backend.planner.morning_order import apply_day_rhythm, morning_order_rule_text

    day = date_cls.fromisoformat(body.day[:10]) if body.day else datetime.now(local_tz()).date()
    rows = (
        db.query(PlannerRoutine)
        .filter(PlannerRoutine.user_id == user.id, PlannerRoutine.enabled.is_(True))
        .order_by(PlannerRoutine.sort_order, PlannerRoutine.id)
        .all()
    )
    routines = [serialize_routine(r) for r in rows]
    blocks = apply_day_rhythm(list(body.blocks or []), day=day, routines=routines)
    return {
        "blocks": blocks,
        "rule": morning_order_rule_text(day=day, routines=routines, calendar_blocks=blocks),
    }


@router.post("/merge-propose", response_model=dict)
def merge_propose_route(
    body: MergeProposeBody,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Merge propose API output with calendar + routines — same logic as CALT Desktop."""
    from datetime import date as date_cls

    from backend.behavior.calt_desktop.planner_propose_merge import merge_propose_result
    from backend.planner.morning_order import morning_order_rule_text
    from backend.planner.service import serialize_block

    range_start = (
        date_cls.fromisoformat(body.range_start[:10])
        if body.range_start
        else datetime.now(local_tz()).date()
    )
    horizon = body.horizon_days
    start_utc, _ = local_day_bounds_utc(range_start)
    _, end_utc = local_day_bounds_utc(range_start + timedelta(days=max(1, horizon) - 1))
    cal_rows = (
        db.query(PlannerBlock)
        .filter(
            PlannerBlock.user_id == user.id,
            PlannerBlock.start_at < end_utc,
            PlannerBlock.end_at > start_utc,
        )
        .order_by(PlannerBlock.start_at)
        .all()
    )
    calendar_blocks = [serialize_block(b) for b in cal_rows]
    routine_rows = (
        db.query(PlannerRoutine)
        .filter(PlannerRoutine.user_id == user.id, PlannerRoutine.enabled.is_(True))
        .order_by(PlannerRoutine.sort_order, PlannerRoutine.id)
        .all()
    )
    routines = [serialize_routine(r) for r in routine_rows]
    merged = merge_propose_result(
        api_blocks=list(body.api_blocks or []),
        calendar_blocks=calendar_blocks,
        routines=routines,
        range_start=range_start,
        horizon_days=horizon,
    )
    return {
        "blocks": merged,
        "rule": morning_order_rule_text(day=range_start, routines=routines, calendar_blocks=merged),
        "merged_count": len(merged),
    }


@router.post("/apply-my-day", response_model=dict)
def apply_my_day_route(
    body: ApplyMyDayBody,
    user: User = Depends(get_current_user),
):
    """One-shot day build: morning order → routines → smart fill → study tasks."""
    from backend.behavior.calt_desktop.day_coach import apply_my_day
    from backend.behavior.calt_desktop.sleep_anchor import DEFAULT_WAKE_HM

    wake = body.wake_hm or DEFAULT_WAKE_HM
    return apply_my_day(
        user.id,
        wake_hm=wake,
        snapshot=body.snapshot,
        goals_prompt=body.goals,
        study_tasks=body.study_tasks,
    )


@router.post("/revert-last-apply", response_model=dict)
def revert_last_apply_route(user: User = Depends(get_current_user)):
    """Undo the last apply-my-day / apply-proposed snapshot."""
    from backend.behavior.calt_desktop.apply_snapshot import revert_last_apply

    return revert_last_apply(user.id)


@router.get("/plan-drift", response_model=dict)
def plan_drift_route(
    day: str | None = Query(None),
    user: User = Depends(get_current_user),
):
    """Plan vs actual drift lines for Today / calendar glance."""
    from datetime import date as date_cls

    from backend.behavior.calt_desktop.day_coach import plan_drift_summary

    d = date_cls.fromisoformat(day[:10]) if day else datetime.now(local_tz()).date()
    return plan_drift_summary(user.id, day=d)


@router.get("/morning-order-rule", response_model=dict)
def morning_order_rule_route(
    day: str | None = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Human-readable morning scheduling rule for UI hints."""
    from datetime import date as date_cls

    from backend.planner.morning_order import morning_order_rule_text

    d = date_cls.fromisoformat(day[:10]) if day else datetime.now(local_tz()).date()
    rows = (
        db.query(PlannerRoutine)
        .filter(PlannerRoutine.user_id == user.id, PlannerRoutine.enabled.is_(True))
        .order_by(PlannerRoutine.sort_order, PlannerRoutine.id)
        .all()
    )
    routines = [serialize_routine(r) for r in rows]
    return {"rule": morning_order_rule_text(day=d, routines=routines)}


@router.post("/generate-week", response_model=dict)
def generate_week_from_timetable(
    body: GenerateWeekBody,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Expand weekly timetable slots into dated planner blocks for the current week."""
    timetable: Timetable | None = None
    if body.timetable_id is not None:
        timetable = (
            db.query(Timetable)
            .filter(Timetable.id == body.timetable_id, Timetable.user_id == user.id)
            .first()
        )
    else:
        timetable = (
            db.query(Timetable)
            .filter(Timetable.user_id == user.id)
            .order_by(Timetable.id.desc())
            .first()
        )

    if timetable is None or not timetable.schedule_json:
        raise HTTPException(status_code=404, detail="No timetable with slots found")

    try:
        slots = json.loads(timetable.schedule_json)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid schedule_json") from exc

    week_start = body.week_start or datetime.now(timezone.utc)
    created: list[PlannerBlock] = []

    for slot in slots:
        day = slot.get("day", "mon")
        start_h = slot.get("start", "09:00")
        end_h = slot.get("end", "10:00")
        title = slot.get("title") or "Study block"
        category = slot.get("category") or "study"
        task_index = slot.get("task_index", 0)

        task_id = None
        tasks = sorted(timetable.tasks, key=lambda t: t.id)
        if 0 <= task_index < len(tasks):
            task_id = tasks[task_index].id
            if title == "Study block":
                title = tasks[task_index].title

        start_at = slot_datetime(week_start, day, start_h)
        end_at = slot_datetime(week_start, day, end_h)
        minutes = _minutes_between(start_at, end_at)

        block = PlannerBlock(
            user_id=user.id,
            title=title,
            category=category,
            start_at=start_at,
            end_at=end_at,
            planned_minutes=minutes,
            remaining_minutes=minutes,
            status="scheduled",
            task_id=task_id,
        )
        db.add(block)
        created.append(block)

    db.commit()
    for b in created:
        db.refresh(b)

    return {
        "created": len(created),
        "blocks": [serialize_block(b) for b in created],
    }


@router.post("/generate-day", response_model=dict)
def generate_day(
    body: GenerateDayBody,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Apply daily slots to planner for a specific date (default today)."""
    from datetime import date as date_type

    if not body.slots:
        raise HTTPException(status_code=400, detail="slots required")
    target = date_type.today()
    if body.date:
        target = date_type.fromisoformat(body.date)
    created = slots_to_planner_blocks(
        db,
        user.id,
        body.slots,
        target_date=target,
        skip_overlaps=body.skip_overlaps,
    )
    return {"created": len(created), "blocks": [serialize_block(b) for b in created]}


@router.get("/routines", response_model=dict)
def list_routines(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    upgrade_stock_default_routines(db, user.id)
    rows = (
        db.query(PlannerRoutine)
        .filter(PlannerRoutine.user_id == user.id)
        .order_by(PlannerRoutine.sort_order, PlannerRoutine.id)
        .all()
    )
    return {"routines": [serialize_routine(r) for r in rows]}


@router.post("/routines/seed-defaults", response_model=dict)
def routines_seed_defaults(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    n = seed_default_routines(db, user.id)
    upgrade_stock_default_routines(db, user.id)
    rows = (
        db.query(PlannerRoutine)
        .filter(PlannerRoutine.user_id == user.id)
        .order_by(PlannerRoutine.sort_order, PlannerRoutine.id)
        .all()
    )
    return {"created": n, "routines": [serialize_routine(r) for r in rows]}


@router.post("/routines", response_model=dict)
def create_routine(
    body: RoutineCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    days = body.days or ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    row = PlannerRoutine(
        user_id=user.id,
        title=body.title,
        category=body.category,
        start_time=body.start_time,
        end_time=body.end_time,
        duration_minutes=body.duration_minutes,
        days_json=json.dumps(days),
        color=body.color,
        enabled=body.enabled,
        sort_order=body.sort_order,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"routine": serialize_routine(row)}


@router.patch("/routines/{routine_id}", response_model=dict)
def update_routine(
    routine_id: int,
    body: RoutineUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    row = (
        db.query(PlannerRoutine)
        .filter(PlannerRoutine.id == routine_id, PlannerRoutine.user_id == user.id)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Routine not found")
    data = body.model_dump(exclude_unset=True)
    if "days" in data:
        row.days_json = json.dumps(data.pop("days"))
    for k, v in data.items():
        setattr(row, k, v)
    db.commit()
    db.refresh(row)
    return {"routine": serialize_routine(row)}


@router.delete("/routines/{routine_id}", response_model=dict)
def delete_routine(
    routine_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    row = (
        db.query(PlannerRoutine)
        .filter(PlannerRoutine.id == routine_id, PlannerRoutine.user_id == user.id)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Routine not found")
    db.delete(row)
    db.commit()
    return {"status": "deleted"}


@router.post("/routines/apply", response_model=dict)
def routines_apply(
    body: ApplyRoutinesBody,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from datetime import date as date_type

    target = None
    if body.date:
        target = date_type.fromisoformat(body.date)
    created = apply_routines(
        db,
        user.id,
        target_date=target,
        skip_overlaps=body.skip_overlaps,
    )
    return {"created": len(created), "blocks": [serialize_block(b) for b in created]}


@router.post("/routines/auto-apply-today", response_model=dict)
def routines_auto_apply_today(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Once per local day per user: materialize enabled routines on today's calendar."""
    return auto_apply_routines_today(db, user.id)


# --- Google Calendar (web → GCal → phone → Amazfit) ---


@router.get("/google-calendar/status", response_model=dict)
def google_calendar_status(user: User = Depends(get_current_user)):
    from backend.planner.google_calendar import google_calendar_configured

    del user
    return google_calendar_configured()


@router.post("/google-calendar/credentials", response_model=dict)
def google_calendar_save_credentials(
    body: GoogleOAuthCredentialsBody,
    user: User = Depends(get_current_user),
):
    """Save OAuth client id/secret from the web UI (local-only file)."""
    from backend.planner.google_calendar import save_oauth_client

    del user
    try:
        return {
            "ok": True,
            **save_oauth_client(body.client_id, body.client_secret),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/google-calendar/auth-url", response_model=dict)
def google_calendar_auth_url(user: User = Depends(get_current_user)):
    from backend.planner.google_calendar import build_auth_url

    del user
    try:
        return {"ok": True, "url": build_auth_url()}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/google-calendar/callback")
def google_calendar_callback(
    code: str | None = Query(None),
    error: str | None = Query(None),
):
    """OAuth redirect target — returns a tiny HTML page the user can close."""
    from backend.planner.google_calendar import exchange_code

    if error:
        return HTMLResponse(
            f"<html><body><h3>Google auth failed</h3><p>{error}</p></body></html>",
            status_code=400,
        )
    if not code:
        return HTMLResponse("<html><body><h3>Missing code</h3></body></html>", status_code=400)
    try:
        exchange_code(code)
    except Exception as e:
        return HTMLResponse(
            f"<html><body><h3>Token exchange failed</h3><p>{e}</p></body></html>",
            status_code=400,
        )
    return HTMLResponse(
        "<html><body style='font-family:sans-serif;padding:2rem'>"
        "<h2>CALT connected to Google Calendar</h2>"
        "<p>You can close this tab and click <b>Push to Google</b> in Productivity.</p>"
        "</body></html>"
    )


@router.post("/google-calendar/disconnect", response_model=dict)
def google_calendar_disconnect(user: User = Depends(get_current_user)):
    from backend.planner.google_calendar import disconnect_google

    del user
    disconnect_google()
    return {"ok": True}


@router.post("/google-calendar/sync", response_model=dict)
def google_calendar_sync(
    days: int = Query(14, ge=1, le=62),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Push upcoming planner blocks to Google Calendar."""
    from backend.planner.google_calendar import sync_blocks_to_google

    now = datetime.now(timezone.utc)
    end = now + timedelta(days=days)
    start = now - timedelta(days=1)
    rows = (
        db.query(PlannerBlock)
        .filter(
            PlannerBlock.user_id == user.id,
            PlannerBlock.end_at >= start,
            PlannerBlock.start_at <= end,
            PlannerBlock.status.notin_(("cancelled", "rolled")),
        )
        .order_by(PlannerBlock.start_at.asc())
        .all()
    )
    blocks = [serialize_block(b) for b in rows]
    result = sync_blocks_to_google(blocks)
    result["block_count"] = len(blocks)
    return result


@router.get("/calendar.ics")
def planner_calendar_ics(
    days: int = Query(14, ge=1, le=62),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Download ICS of upcoming planner blocks (import into Google Calendar)."""
    from backend.planner.google_calendar import blocks_to_ics

    now = datetime.now(timezone.utc)
    end = now + timedelta(days=days)
    start = now - timedelta(days=1)
    rows = (
        db.query(PlannerBlock)
        .filter(
            PlannerBlock.user_id == user.id,
            PlannerBlock.end_at >= start,
            PlannerBlock.start_at <= end,
            PlannerBlock.status.notin_(("cancelled", "rolled")),
        )
        .order_by(PlannerBlock.start_at.asc())
        .all()
    )
    ics = blocks_to_ics([serialize_block(b) for b in rows])
    return Response(
        content=ics,
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="calt-planner.ics"'},
    )
