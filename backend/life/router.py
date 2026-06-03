from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.core.auth import get_current_user
from backend.db.session import get_db
from backend.hub.services.ingest import insert_reading
from backend.hub.services.rollup import daily_payload, rebuild_daily_rollup
from backend.life.schemas import LifeDailyIn
from backend.life.services.scoring import compute_life_score
from backend.models import LifeDailyLog, User

router = APIRouter(prefix="/api/life", tags=["life"])


def _upsert_life_log(db: Session, user_id: int, d: date, body: LifeDailyIn) -> LifeDailyLog:
    row = db.query(LifeDailyLog).filter(LifeDailyLog.user_id == user_id, LifeDailyLog.date == d).first()
    if not row:
        row = LifeDailyLog(user_id=user_id, date=d)
        db.add(row)

    for key, value in body.model_dump().items():
        setattr(row, key, value)

    row.life_score = compute_life_score(**body.model_dump())
    db.commit()
    db.refresh(row)
    return row


@router.get("/daily/{day}")
def get_life_daily(
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
            raise HTTPException(status_code=400, detail="Invalid date") from e
    row = db.query(LifeDailyLog).filter(LifeDailyLog.user_id == user.id, LifeDailyLog.date == d).first()
    if not row:
        return {"date": day, "life_score": 0, "empty": True}
    return {
        "date": day,
        "empty": False,
        "life_score": row.life_score,
        **{c.name: getattr(row, c.name) for c in LifeDailyLog.__table__.columns if c.name not in ("id", "user_id", "date")},
    }


@router.put("/daily/{day}")
def put_life_daily(
    day: str,
    body: LifeDailyIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if day in ("today", "now"):
        d = date.today()
    else:
        try:
            d = date.fromisoformat(day)
        except ValueError as e:
            raise HTTPException(status_code=400, detail="Invalid date") from e

    row = _upsert_life_log(db, user.id, d, body)

    try:
        insert_reading(
            db,
            user_id=user.id,
            slug="study_minutes",
            value_numeric=float(row.study_minutes),
            source_device="life_form",
        )
        insert_reading(
            db,
            user_id=user.id,
            slug="sleep_hours",
            value_numeric=float(row.sleep_hours),
            source_device="life_form",
        )
    except ValueError:
        pass

    rollup = rebuild_daily_rollup(db, user.id, d)
    return {
        "life_score": row.life_score,
        "daily": daily_payload(rollup, row),
        "log": body.model_dump(),
    }
