import csv
import io
import json
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend.core.auth import get_current_user, require_admin
from backend.db.session import get_db
from backend.hub.schemas import PluginToggleIn, ReadingIn, ReadingsBatchIn, SessionPatchIn, SessionStartIn
from backend.hub.services.ingest import insert_reading, insert_readings_batch
from backend.hub.services.rollup import daily_payload, rebuild_daily_rollup
from backend.models import ActivitySession, DailyRollup, LifeDailyLog, Reading, ReadingDefinition, User, UserPlugin

router = APIRouter(prefix="/api/hub", tags=["hub"])


@router.post("/readings")
def post_readings(
    body: ReadingsBatchIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = [r.model_dump() for r in body.readings]
    try:
        rows = insert_readings_batch(db, user.id, items)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"inserted": len(rows), "ids": [r.id for r in rows]}


@router.post("/readings/single")
def post_reading_single(
    body: ReadingIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        row = insert_reading(db, user_id=user.id, **body.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"id": row.id}


@router.get("/readings")
def get_readings(
    slug: str | None = None,
    from_dt: datetime | None = Query(None, alias="from"),
    to_dt: datetime | None = Query(None, alias="to"),
    limit: int = 100,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = db.query(Reading).filter(Reading.user_id == user.id)
    if slug:
        defn = db.query(ReadingDefinition).filter(ReadingDefinition.slug == slug).first()
        if not defn:
            return {"readings": []}
        q = q.filter(Reading.definition_id == defn.id)
    if from_dt:
        q = q.filter(Reading.recorded_at >= from_dt)
    if to_dt:
        q = q.filter(Reading.recorded_at <= to_dt)
    rows = q.order_by(Reading.recorded_at.desc()).limit(limit).all()
    return {
        "readings": [
            {
                "id": r.id,
                "definition_id": r.definition_id,
                "recorded_at": r.recorded_at.isoformat() if r.recorded_at else None,
                "value_numeric": r.value_numeric,
                "value_json": json.loads(r.value_json) if r.value_json else None,
            }
            for r in rows
        ]
    }


@router.post("/sessions")
def start_session(
    body: SessionStartIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    sess = ActivitySession(
        user_id=user.id,
        session_type=body.session_type,
        metadata_json=json.dumps(body.metadata or {}),
    )
    db.add(sess)
    db.commit()
    db.refresh(sess)
    return {"id": sess.id, "session_type": sess.session_type, "started_at": sess.started_at.isoformat()}


@router.patch("/sessions/{session_id}")
def end_session(
    session_id: int,
    body: SessionPatchIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    sess = db.get(ActivitySession, session_id)
    if not sess or sess.user_id != user.id:
        raise HTTPException(status_code=404, detail="Session not found")
    if body.ended_at:
        sess.ended_at = body.ended_at
    if body.metadata is not None:
        sess.metadata_json = json.dumps(body.metadata)
    db.commit()
    return {"id": sess.id, "ended_at": sess.ended_at.isoformat() if sess.ended_at else None}


@router.get("/daily/{day}")
def get_daily(
    day: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if day in ("today", "now"):
        d = date.today()
    else:
        try:
            d = date.fromisoformat(day)
        except ValueError as e:
            raise HTTPException(status_code=400, detail="Invalid date YYYY-MM-DD") from e

    life = db.query(LifeDailyLog).filter(LifeDailyLog.user_id == user.id, LifeDailyLog.date == d).first()
    rollup = db.query(DailyRollup).filter(DailyRollup.user_id == user.id, DailyRollup.date == d).first()
    if not rollup:
        rollup = rebuild_daily_rollup(db, user.id, d)
    return daily_payload(rollup, life)


@router.post("/daily/rebuild")
def rebuild_daily(
    day: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    d = date.fromisoformat(day) if day else date.today()
    rollup = rebuild_daily_rollup(db, user.id, d)
    life = db.query(LifeDailyLog).filter(LifeDailyLog.user_id == user.id, LifeDailyLog.date == d).first()
    return daily_payload(rollup, life)


@router.get("/export")
def export_hub_data(
    from_day: str | None = None,
    to_day: str | None = None,
    format: str = "json",
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    logs = db.query(LifeDailyLog).filter(LifeDailyLog.user_id == user.id).all()
    rollups = db.query(DailyRollup).filter(DailyRollup.user_id == user.id).all()
    readings = db.query(Reading).filter(Reading.user_id == user.id).limit(5000).all()

    payload = {
        "user_id": user.id,
        "full_export_path": "/api/account/export",
        "life_logs": [
            {"date": str(l.date), "life_score": l.life_score, "study_minutes": l.study_minutes}
            for l in logs
        ],
        "rollups": [{"date": str(r.date), "productive_minutes": r.productive_minutes} for r in rollups],
        "readings_count": len(readings),
    }

    if format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["date", "life_score", "study_minutes"])
        for l in logs:
            writer.writerow([l.date, l.life_score, l.study_minutes])
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=hub_export.csv"},
        )
    return payload


@router.get("/plugins")
def list_plugins(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = db.query(UserPlugin).filter(UserPlugin.user_id == user.id).all()
    return {
        "plugins": [
            {"plugin_id": r.plugin_id, "enabled": r.enabled, "config": json.loads(r.config_json or "{}")}
            for r in rows
        ]
    }


@router.put("/plugins")
def set_plugin(
    body: PluginToggleIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    row = (
        db.query(UserPlugin)
        .filter(UserPlugin.user_id == user.id, UserPlugin.plugin_id == body.plugin_id)
        .first()
    )
    if not row:
        row = UserPlugin(user_id=user.id, plugin_id=body.plugin_id)
        db.add(row)
    row.enabled = body.enabled
    if body.config is not None:
        row.config_json = json.dumps(body.config)
    db.commit()
    return {"plugin_id": row.plugin_id, "enabled": row.enabled}
