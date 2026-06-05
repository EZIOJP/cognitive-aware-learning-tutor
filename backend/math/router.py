import io
import json
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
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


class TutorHintIn(BaseModel):
    canvas_image: str = ""
    prompt: str = ""
    topic: str = ""
    gamma: float = 0
    attention: float = 0


class TutorHintOut(BaseModel):
    hint: str
    question: str
    detected_concept: str
    use_llm: bool = False


@router.post("/tutor/hint", response_model=TutorHintOut)
def math_tutor_hint(
    body: TutorHintIn,
    user: User = Depends(get_current_user),
):
    """Rule-based coach by default; Ollama only when OLLAMA_ENABLED=1 and reachable."""
    from backend.math.ollama_tutor import generate_tutor_hint, ollama_available
    from backend.math.rule_tutor import rule_based_hint

    ruled = rule_based_hint(
        prompt=body.prompt,
        topic=body.topic or "current problem",
        gamma=body.gamma,
        attention=body.attention,
    )

    if ollama_available():
        llm = generate_tutor_hint(
            prompt=body.prompt,
            topic=ruled["detected_concept"],
            gamma=body.gamma,
            attention=body.attention,
            canvas_image=body.canvas_image,
        )
        if llm:
            return TutorHintOut(
                hint=llm["hint"],
                question=llm["question"],
                detected_concept=llm.get("detected_concept", ruled["detected_concept"]),
                use_llm=True,
            )
    return TutorHintOut(
        hint=ruled["hint"],
        question=ruled["question"],
        detected_concept=ruled["detected_concept"],
        use_llm=False,
    )


class MathOcrIn(BaseModel):
    canvas_image: str


class MathOcrOut(BaseModel):
    latex: str
    incomplete_step: bool
    confidence: float
    preprocess_applied: bool


@router.post("/ocr", response_model=MathOcrOut)
def math_ocr(
    body: MathOcrIn,
    _user: User = Depends(get_current_user),
):
    """Handwritten math → LaTeX via pix2tex; SymPy marks incomplete steps."""
    from backend.math.ocr_service import recognize_canvas

    try:
        result = recognize_canvas(body.canvas_image)
    except ImportError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OCR failed: {e}") from e

    return MathOcrOut(
        latex=result.latex,
        incomplete_step=result.incomplete_step,
        confidence=result.confidence,
        preprocess_applied=result.preprocess_applied,
    )
