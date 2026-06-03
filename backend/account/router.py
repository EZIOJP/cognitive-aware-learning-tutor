"""Account-level operations: GDPR-style data export."""

from __future__ import annotations

import csv
import io
import json
from datetime import date

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend.core.auth import get_current_user
from backend.db.session import get_db
from backend.models import (
    ActivitySession,
    DailyRollup,
    LifeDailyLog,
    MathAttempt,
    QuizSession,
    Reading,
    ReadingDefinition,
    User,
    UserPlugin,
    WordProgress,
)
from backend.vocab.repository import count_words, load_words

router = APIRouter(prefix="/api/account", tags=["account"])


def _build_export(db: Session, user: User) -> dict:
    readings = (
        db.query(Reading)
        .filter(Reading.user_id == user.id)
        .order_by(Reading.recorded_at.desc())
        .limit(10000)
        .all()
    )
    defn_map = {d.id: d.slug for d in db.query(ReadingDefinition).all()}

    return {
        "export_version": "1.0",
        "user": {
            "id": user.id,
            "username": user.username,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "is_admin": bool(user.is_admin),
        },
        "word_progress": [
            {
                "word_id": p.word_id,
                "mastery": p.mastery,
                "times_asked": p.times_asked,
                "times_correct": p.times_correct,
                "due_date": p.due_date.isoformat() if p.due_date else None,
                "is_suspended": p.is_suspended,
            }
            for p in db.query(WordProgress).filter(WordProgress.user_id == user.id).all()
        ],
        "quiz_sessions": [
            {
                "external_id": q.external_id,
                "quiz_type": q.quiz_type,
                "started_at": q.started_at.isoformat() if q.started_at else None,
                "completed_at": q.completed_at.isoformat() if q.completed_at else None,
                "hub_session_id": q.hub_session_id,
            }
            for q in db.query(QuizSession).filter(QuizSession.user_id == user.id).all()
        ],
        "math_attempts": [
            {
                "id": a.id,
                "topic": a.topic,
                "is_correct": a.is_correct,
                "created_at": a.created_at.isoformat() if a.created_at else None,
                "hub_session_id": a.hub_session_id,
            }
            for a in db.query(MathAttempt).filter(MathAttempt.user_id == user.id).all()
        ],
        "activity_sessions": [
            {
                "id": s.id,
                "session_type": s.session_type,
                "started_at": s.started_at.isoformat() if s.started_at else None,
                "ended_at": s.ended_at.isoformat() if s.ended_at else None,
            }
            for s in db.query(ActivitySession).filter(ActivitySession.user_id == user.id).all()
        ],
        "life_logs": [
            {
                "date": str(l.date),
                "life_score": l.life_score,
                "study_minutes": l.study_minutes,
            }
            for l in db.query(LifeDailyLog).filter(LifeDailyLog.user_id == user.id).all()
        ],
        "daily_rollups": [
            {
                "date": str(r.date),
                "productive_minutes": r.productive_minutes,
                "vocab_events": r.vocab_events,
                "math_attempts": r.math_attempts,
            }
            for r in db.query(DailyRollup).filter(DailyRollup.user_id == user.id).all()
        ],
        "plugins": [
            {"plugin_id": p.plugin_id, "enabled": p.enabled}
            for p in db.query(UserPlugin).filter(UserPlugin.user_id == user.id).all()
        ],
        "readings_sample": [
            {
                "slug": defn_map.get(r.definition_id, "unknown"),
                "recorded_at": r.recorded_at.isoformat() if r.recorded_at else None,
                "value_numeric": r.value_numeric,
                "session_id": r.session_id,
            }
            for r in readings[:500]
        ],
        "readings_total": len(readings),
        "words_in_db": count_words(db),
        "words_catalog_count": len(load_words(db)),
        "exported_on": date.today().isoformat(),
    }


@router.get("/export")
def export_my_data(
    format: str = Query("json", pattern="^(json|csv)$"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    payload = _build_export(db, user)
    if format == "json":
        return payload

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["section", "key", "value"])
    writer.writerow(["user", "username", user.username])
    for p in payload["word_progress"]:
        writer.writerow(["word_progress", p["word_id"], json.dumps(p)])
    for a in payload["math_attempts"]:
        writer.writerow(["math_attempt", a["id"], json.dumps(a)])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=export_{user.username}.csv"},
    )
