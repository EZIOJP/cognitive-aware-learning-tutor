import json
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.core.auth import get_current_user
from backend.db.session import get_db
from backend.models import User
from backend.models.timetable import Timetable, TimetableTask, TrackedSession
from backend.timetable.schemas import ImportJsonPayload, SyncPayload, slots_to_json
from backend.timetable.tracker_query import tracker_user_ids

router = APIRouter(prefix="/api/timetable", tags=["timetable"])

_DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


def _serialize_timetable(t: Timetable, scores: dict[str, int]) -> dict:
    from backend.behavior.category_scores import score_for_category

    tasks = []
    for task in t.tasks:
        sessions = [
            {
                "session_id": s.session_id,
                "start_time": s.start_time.isoformat() if s.start_time else None,
                "end_time": s.end_time.isoformat() if s.end_time else None,
                "source": s.source,
                "category": s.category,
                "productivity_score": score_for_category(s.category, scores),
            }
            for s in task.sessions
        ]
        tasks.append({
            "id": task.id,
            "title": task.title,
            "description": task.description,
            "sessions": sessions,
        })

    slots = []
    if t.schedule_json:
        try:
            slots = json.loads(t.schedule_json)
        except json.JSONDecodeError:
            slots = []

    return {
        "id": t.id,
        "name": t.name,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "tasks": tasks,
        "slots": slots,
    }


def _sync_payload(db: Session, user_id: int, payload: SyncPayload) -> dict:
    if payload.replace:
        existing = db.query(Timetable).filter(Timetable.user_id == user_id).all()
        for row in existing:
            db.delete(row)
        db.flush()

    timetable = Timetable(
        user_id=user_id,
        name=payload.name,
        schedule_json=slots_to_json(payload.slots) if payload.slots else None,
    )
    db.add(timetable)
    db.flush()

    task_id_map: dict[int, int] = {}
    for idx, task_schema in enumerate(payload.tasks):
        task = TimetableTask(
            timetable_id=timetable.id,
            title=task_schema.title,
            description=task_schema.description,
        )
        db.add(task)
        db.flush()
        task_id_map[idx] = task.id

    for sess_schema in payload.sessions:
        start_tz = sess_schema.start_time
        end_tz = sess_schema.end_time
        if start_tz.tzinfo is None:
            start_tz = start_tz.replace(tzinfo=timezone.utc)
        if end_tz.tzinfo is None:
            end_tz = end_tz.replace(tzinfo=timezone.utc)

        mapped_task_id = None
        if sess_schema.task_id is not None and sess_schema.task_id in task_id_map:
            mapped_task_id = task_id_map[sess_schema.task_id]

        existing = db.query(TrackedSession).filter(
            TrackedSession.session_id == sess_schema.session_id
        ).first()
        if existing:
            continue

        session = TrackedSession(
            session_id=sess_schema.session_id,
            user_id=user_id,
            task_id=mapped_task_id,
            start_time=start_tz,
            end_time=end_tz,
            source=sess_schema.source,
            category=sess_schema.category,
        )
        db.add(session)

    db.commit()
    db.refresh(timetable)
    return {"status": "success", "message": "Timetable synced", "timetable_id": timetable.id}


@router.post("/sync", response_model=dict)
def sync_timetable(
    payload: SyncPayload,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        return _sync_payload(db, user.id, payload)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Database error during sync: {str(e)}",
        ) from e


def _import_parsed(db: Session, user_id: int, parsed: ImportJsonPayload) -> dict:
    """Sync weekly template and optionally apply daily slots to planner."""
    from backend.planner.routines import slots_to_planner_blocks

    planner_created = 0
    if parsed.schedule_type == "daily" and parsed.daily_slots:
        target = date.today()
        if parsed.date:
            target = date.fromisoformat(parsed.date)
        if parsed.apply_to_planner:
            blocks = slots_to_planner_blocks(
                db,
                user_id,
                [s.model_dump() for s in parsed.daily_slots],
                target_date=target,
            )
            planner_created = len(blocks)

    # Weekly slots stored on timetable; daily-only imports may have empty slots
    weekly_slots = parsed.slots
    if parsed.schedule_type == "weekly" or weekly_slots:
        payload = SyncPayload(
            name=parsed.name or "Imported timetable",
            tasks=parsed.tasks,
            slots=weekly_slots,
            sessions=parsed.sessions,
            replace=parsed.replace,
        )
        result = _sync_payload(db, user_id, payload)
        result["planner_blocks_created"] = planner_created
        result["schedule_type"] = parsed.schedule_type
        return result

    if planner_created:
        return {
            "status": "success",
            "message": f"Applied {planner_created} block(s) to planner",
            "planner_blocks_created": planner_created,
            "schedule_type": "daily",
        }

    raise ValueError("No weekly slots or daily_slots found in import")


@router.post("/import/json", response_model=dict)
def import_timetable_json(
    body: dict,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Import timetable from JSON body or `{"timetable": {...}}` wrapper."""
    try:
        parsed = ImportJsonPayload.from_raw(body)
        return _import_parsed(db, user.id, parsed)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e)) from e


class ImportTextBody(BaseModel):
    text: str
    apply_to_planner: bool = True


@router.post("/import/text", response_model=dict)
def import_timetable_text(
    body: ImportTextBody,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Import from pasted text — strips markdown fences and surrounding prose."""
    try:
        parsed = ImportJsonPayload.from_text(body.text)
        if body.apply_to_planner and parsed.schedule_type == "daily":
            parsed.apply_to_planner = True
        return _import_parsed(db, user.id, parsed)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/template", response_model=dict)
def timetable_template():
    """Example JSON for import — weekly and daily formats."""
    return {
        "weekly_example": {
            "name": "Spring Week",
            "type": "weekly",
            "tasks": [
                {"title": "Linear Algebra", "description": "Lecture + problem set"},
                {"title": "Python Study", "description": "NumPy practice"},
            ],
            "slots": [
                {"day": "mon", "start": "09:00", "end": "11:00", "task_index": 0, "title": "Linear Algebra"},
                {"day": "wed", "start": "14:00", "end": "16:00", "task_index": 1, "title": "Python Study"},
            ],
        },
        "daily_example": {
            "name": "Today",
            "type": "daily",
            "date": date.today().isoformat(),
            "apply_to_planner": True,
            "daily_slots": [
                {"start": "07:00", "end": "07:30", "title": "Bible", "category": "spiritual"},
                {"start": "09:00", "end": "11:00", "title": "Deep work", "category": "study"},
                {"start": "13:00", "end": "13:45", "title": "Lunch", "category": "food"},
            ],
        },
        "sessions": [],
    }


@router.get("", response_model=dict)
def get_timetables(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    timetables = db.query(Timetable).filter(Timetable.user_id == user.id).order_by(
        Timetable.id.desc()
    ).all()

    # Desktop sessions without task link (tracker bridge)
    desktop_sessions = (
        db.query(TrackedSession)
        .filter(
            TrackedSession.user_id.in_(tracker_user_ids(db, user)),
            TrackedSession.task_id.is_(None),
            TrackedSession.source == "desktop_tracker",
        )
        .order_by(TrackedSession.start_time.desc())
        .limit(50)
        .all()
    )
    from backend.behavior.category_scores import load_score_map, score_for_category

    scores = load_score_map(db)
    live_sessions = [
        {
            "session_id": s.session_id,
            "start_time": s.start_time.isoformat() if s.start_time else None,
            "end_time": s.end_time.isoformat() if s.end_time else None,
            "source": s.source,
            "category": s.category,
            "productivity_score": score_for_category(s.category, scores),
        }
        for s in desktop_sessions
    ]

    return {
        "timetables": [_serialize_timetable(t, scores) for t in timetables],
        "live_desktop_sessions": live_sessions,
        "days": list(_DAYS),
    }
