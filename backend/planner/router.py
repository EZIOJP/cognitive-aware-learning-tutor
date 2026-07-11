import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
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
)
from backend.planner.schemas import (
    ApplyRoutinesBody,
    CompleteBlockBody,
    GenerateDayBody,
    GenerateWeekBody,
    PlannerBlockCreate,
    PlannerBlockUpdate,
    RollForwardBody,
    RoutineCreate,
    RoutineUpdate,
)
from backend.planner.service import (
    _minutes_between,
    _utc,
    iso_utc,
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
    from backend.behavior.session_merge import merge_for_calendar

    start = _utc(from_dt)
    end = _utc(to_dt)
    user_ids = tracker_user_ids(db, user)

    sessions = (
        db.query(TrackedSession)
        .filter(
            TrackedSession.user_id.in_(user_ids),
            TrackedSession.source == "desktop_tracker",
            TrackedSession.start_time < end,
            TrackedSession.end_time > start,
        )
        .order_by(TrackedSession.start_time)
        .all()
    )
    sessions = merge_for_calendar(sessions)
    from backend.behavior.category_scores import load_score_map, serialize_tracked_session

    scores = load_score_map(db)
    return {
        "sessions": [serialize_tracked_session(s, scores) for s in sessions]
    }


@router.get("/export/last-7-days")
def export_productivity_last_days(
    days: int = Query(7, ge=1, le=31, description="How many calendar days ending today"),
    format: str = Query("json", pattern="^(json|csv)$"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Export recent planner + tracked usage for designing weekly timetables."""
    from fastapi.responses import Response

    from backend.planner.week_export import build_productivity_week_export, export_as_csv

    payload = build_productivity_week_export(db, user, days=days)
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

    start = _utc(day).replace(hour=0, minute=0, second=0, microsecond=0)
    end = start.replace(hour=23, minute=59, second=59, microsecond=999999)

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
    planned_minutes = sum(b.planned_minutes for b in blocks)

    sessions = (
        db.query(TrackedSession)
        .filter(
            TrackedSession.user_id.in_(tracker_user_ids(db, user)),
            TrackedSession.start_time < end,
            TrackedSession.end_time > start,
        )
        .all()
    )
    actual_seconds = sum(
        (s.end_time - s.start_time).total_seconds()
        for s in sessions
        if s.start_time and s.end_time
    )
    actual_minutes = int(actual_seconds // 60)

    from backend.behavior.category_scores import (
        PRODUCTIVE_THRESHOLD,
        load_score_map,
        score_for_category,
    )
    from backend.planner.effective_focus import effective_focus_minutes

    scores = load_score_map(db)
    productive_minutes = sum(
        int((s.end_time - s.start_time).total_seconds() // 60)
        for s in sessions
        if s.start_time and s.end_time
        and score_for_category(s.category, scores) >= PRODUCTIVE_THRESHOLD
    )
    effective_focus = effective_focus_minutes(
        blocks,
        sessions,
        lambda cat: score_for_category(cat, scores),
    )

    pct = round(100 * actual_minutes / planned_minutes, 1) if planned_minutes else None

    return {
        "day": start.date().isoformat(),
        "planned_minutes": planned_minutes,
        "actual_minutes": actual_minutes,
        "productive_minutes": productive_minutes,
        "effective_focus_minutes": effective_focus,
        "adherence_pct": pct,
        "block_count": len(blocks),
        "session_count": len(sessions),
    }


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
    rows = (
        db.query(PlannerRoutine)
        .filter(PlannerRoutine.user_id == user.id)
        .order_by(PlannerRoutine.sort_order)
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
