import io
import json
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend.core.auth import get_current_user, require_admin
from backend.db.session import get_db
from backend.math.schemas import MathImportBundle, MathImportResult
from backend.math.services.import_questions import parse_import_payload, upsert_questions
from backend.math.services.randomizer import pick_from_bank
from backend.models import MathQuestion, User

router = APIRouter(prefix="/api/math", tags=["math"])


@router.post("/questions/import/json", response_model=MathImportResult)
def import_questions_json(
    body: dict[str, Any],
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """Import question bank (draft format — see docs/MATH_QUESTION_IMPORT.md)."""
    items, parse_errors = parse_import_payload(body)
    if not items:
        raise HTTPException(status_code=400, detail=parse_errors or ["No valid questions"])
    result = upsert_questions(db, items, default_source=body.get("source") if isinstance(body, dict) else None)
    result.errors = parse_errors + result.errors
    return result


@router.post("/questions/import/file", response_model=MathImportResult)
async def import_questions_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    raw = await file.read()
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON file: {e}") from e
    items, parse_errors = parse_import_payload(data)
    if not items:
        raise HTTPException(status_code=400, detail=parse_errors or ["No valid questions"])
    default_source = data.get("source") if isinstance(data, dict) else "file_import"
    result = upsert_questions(db, items, default_source=default_source)
    result.errors = parse_errors + result.errors
    return result


@router.post("/questions/import/preview")
def preview_import(
    body: dict[str, Any],
    _user: User = Depends(get_current_user),
):
    """Validate import without writing — use while finalizing file format."""
    items, errors = parse_import_payload(body)
    preview = [
        {
            "topic": i.topic,
            "prompt": (i.prompt or "")[:120],
            "expected_answer": i.expected_answer,
            "external_id": i.external_id,
        }
        for i in items[:20]
    ]
    return {
        "valid_count": len(items),
        "preview": preview,
        "errors": errors,
        "truncated": len(items) > 20,
    }


@router.get("/questions/export/json")
def export_questions_json(
    topic: str | None = None,
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    q = db.query(MathQuestion)
    if not include_inactive:
        q = q.filter(MathQuestion.is_active == True)
    if topic:
        q = q.filter(MathQuestion.topic == topic)
    rows = q.order_by(MathQuestion.topic, MathQuestion.id).all()
    questions = [
        {
            "external_id": r.external_id,
            "topic": r.topic,
            "prompt": r.prompt,
            "expected_answer": r.expected_answer,
            "explanation": r.explanation,
            "latex": r.latex,
            "difficulty": r.difficulty,
            "answer_format": r.answer_format,
            "tags": json.loads(r.tags_json or "[]"),
            "metadata": json.loads(r.metadata_json or "{}"),
            "source": r.source,
            "is_active": r.is_active,
        }
        for r in rows
    ]
    return {
        "format_version": 1,
        "topic": topic,
        "questions": questions,
    }


@router.get("/questions")
def list_questions(
    topic: str | None = None,
    limit: int = Query(50, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = db.query(MathQuestion).filter(MathQuestion.is_active == True)
    if topic:
        q = q.filter(MathQuestion.topic == topic)
    total = q.count()
    rows = q.order_by(MathQuestion.id).offset(offset).limit(limit).all()
    return {
        "questions": [
            {
                "id": r.id,
                "topic": r.topic,
                "prompt": r.prompt,
                "difficulty": r.difficulty,
                "external_id": r.external_id,
            }
            for r in rows
        ],
        "pagination": {"total": total, "offset": offset, "limit": limit},
    }


@router.delete("/questions/{question_id}")
def delete_question(
    question_id: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    row = db.get(MathQuestion, question_id)
    if not row:
        raise HTTPException(status_code=404, detail="Question not found")
    row.is_active = False
    db.commit()
    return {"deleted": question_id, "soft": True}
