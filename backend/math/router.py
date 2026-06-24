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
    paths_json: str | None = None
    stroke_metrics_json: str | None = None
    ollama_vision_fallback: bool = True


class MathOcrOut(BaseModel):
    latex: str
    incomplete_step: bool
    confidence: float
    preprocess_applied: bool
    teacher_latex: str = ""
    needs_review: bool = False
    tier: str = "texteller"


class MathEvalIn(BaseModel):
    expression: str


class MathEvalOut(BaseModel):
    result: str
    latex: str
    steps: list[str]
    ok: bool = True
    error: str | None = None


@router.post("/eval", response_model=MathEvalOut)
def math_eval(
    body: MathEvalIn,
    _user: User = Depends(get_current_user),
):
    """SymPy simplify / integrate / diff / solve — CPU only, for hub calculator widget."""
    from backend.math.eval_service import eval_expression

    expr = (body.expression or "").strip()
    if not expr:
        raise HTTPException(status_code=400, detail="expression is required")
    try:
        out = eval_expression(expr)
    except ValueError as e:
        return MathEvalOut(result="", latex="", steps=[], ok=False, error=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Eval failed: {e}") from e
    return MathEvalOut(**out)


class MathOcrStatusOut(BaseModel):
    texteller_available: bool
    nim_teacher: bool
    ollama_vision: bool
    tier: str


@router.get("/ocr/status", response_model=MathOcrStatusOut)
def math_ocr_status(
    _user: User = Depends(get_current_user),
):
    """OCR engine health — lets the UI show 'ready' vs 'install OCR deps'."""
    import os

    from backend.integrations.nim_client import nim_available
    from backend.math.ocr_service import texteller_available
    from backend.math.ollama_tutor import ollama_available

    tex = texteller_available()
    nim = nim_available()
    ollama_vis = bool(ollama_available() and os.getenv("OLLAMA_VISION_MODEL", "").strip())
    tier = "texteller" if tex else ("ollama_vision" if ollama_vis else "unavailable")
    return MathOcrStatusOut(
        texteller_available=tex,
        nim_teacher=nim,
        ollama_vision=ollama_vis,
        tier=tier,
    )


@router.post("/ocr", response_model=MathOcrOut)
def math_ocr(
    body: MathOcrIn,
    _user: User = Depends(get_current_user),
):
    """Handwritten math → LaTeX via TexTeller ONNX (CPU); SymPy marks incomplete steps."""
    from backend.math.ocr_service import recognize_canvas

    try:
        result = recognize_canvas(
            body.canvas_image,
            paths_json=body.paths_json,
            stroke_metrics_json=body.stroke_metrics_json,
            ollama_vision_fallback=body.ollama_vision_fallback,
        )
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
        teacher_latex=result.teacher_latex,
        needs_review=result.needs_review,
        tier=result.tier,
    )


class MathInterventionIn(BaseModel):
    canvas_image: str = ""
    paths_json: str | None = None
    stroke_metrics_json: str | None = None
    prompt: str = ""
    topic: str = ""
    gamma: float = 55.0
    attention: float = 60.0
    canvas_idle_seconds: float = 0.0
    eraser_events: int = 0
    idle_seconds: float = 0.0
    eraser_strokes: int = 0


class MathInterventionOut(BaseModel):
    session_snapshot_id: str
    latex: str
    incomplete_step: bool
    confidence: float
    stuckness: float
    triggered: bool
    hint: str
    question: str
    detected_concept: str
    use_llm: bool = False


class InterventionPatchIn(BaseModel):
    notes: str = ""
    learner_recovered: bool = True


class InterventionCorrectIn(BaseModel):
    correct_latex: str
    notes: str = ""


class InterventionPatchOut(BaseModel):
    session_snapshot_id: str
    status: str
    ok: bool = True


@router.post("/intervention", response_model=MathInterventionOut)
def math_intervention(
    body: MathInterventionIn,
    user: User = Depends(get_current_user),
):
    """OCR + stuckness score → Socratic hint; logs DSC_interventions CSV + PNG."""
    from backend.math.intervention_handler import build_intervention
    from backend.math.intervention_log import log_intervention, new_snapshot_id

    if not (body.canvas_image or "").strip():
        raise HTTPException(status_code=400, detail="canvas_image is required")

    snapshot_id = new_snapshot_id()
    idle = body.canvas_idle_seconds or body.idle_seconds
    erasers = body.eraser_events or body.eraser_strokes
    try:
        result = build_intervention(
            canvas_image=body.canvas_image,
            paths_json=body.paths_json,
            prompt=body.prompt,
            topic=body.topic,
            gamma=body.gamma,
            attention=body.attention,
            canvas_idle_seconds=idle,
            eraser_events=erasers,
            snapshot_id=snapshot_id,
        )
    except ImportError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Intervention failed: {e}") from e

    if body.stroke_metrics_json:
        from backend.math.training_log import log_kinematics

        log_kinematics(
            sample_id=result.session_snapshot_id,
            user_id=user.id,
            context="intervention",
            stroke_metrics_json=body.stroke_metrics_json,
        )

    log_intervention(
        user_id=user.id,
        canvas_image=body.canvas_image,
        snapshot_id=result.session_snapshot_id,
        topic=body.topic,
        latex=result.latex,
        teacher_latex=result.teacher_latex,
        needs_review=result.needs_review,
        incomplete_step=result.incomplete_step,
        stuckness=result.stuckness,
        gamma=body.gamma,
        attention=body.attention,
        idle_seconds=idle,
        eraser_events=erasers,
        hint=result.hint,
        question=result.question,
        detected_concept=result.detected_concept,
        use_llm=result.use_llm,
        status="spawned" if result.triggered else "low_signal",
    )

    return MathInterventionOut(
        session_snapshot_id=result.session_snapshot_id,
        latex=result.latex,
        incomplete_step=result.incomplete_step,
        confidence=result.confidence,
        stuckness=result.stuckness,
        triggered=result.triggered,
        hint=result.hint,
        question=result.question,
        detected_concept=result.detected_concept,
        use_llm=result.use_llm,
    )


@router.patch("/intervention/{snapshot_id}/recover", response_model=InterventionPatchOut)
def math_intervention_recover(
    snapshot_id: str,
    body: InterventionPatchIn,
    _user: User = Depends(get_current_user),
):
    """Student dismissed hint or resumed work."""
    from backend.math.intervention_log import update_intervention_status

    ok = update_intervention_status(
        snapshot_id,
        "recovered",
        body.notes,
        learner_recovered=body.learner_recovered,
    )
    if not ok:
        raise HTTPException(status_code=404, detail="Intervention snapshot not found")
    return InterventionPatchOut(session_snapshot_id=snapshot_id, status="recovered")


@router.patch("/intervention/{snapshot_id}/correct", response_model=InterventionPatchOut)
def math_intervention_correct(
    snapshot_id: str,
    body: InterventionCorrectIn,
    user: User = Depends(get_current_user),
):
    """Admin/human correct LaTeX label → DSC_handwriting_dataset.csv."""
    from backend.math.intervention_log import log_intervention_correction, update_intervention_status

    latex = (body.correct_latex or "").strip()
    if not latex:
        raise HTTPException(status_code=400, detail="correct_latex is required")
    ok = update_intervention_status(snapshot_id, "correct", body.notes, learner_recovered=True)
    if not ok:
        raise HTTPException(status_code=404, detail="Intervention snapshot not found")
    log_intervention_correction(
        snapshot_id=snapshot_id,
        correct_latex=latex,
        user_id=user.id,
    )
    return InterventionPatchOut(session_snapshot_id=snapshot_id, status="correct")


class TrainSampleIn(BaseModel):
    tier: str
    prompt_id: str
    prompt_text: str = ""
    canvas_image: str
    predicted_latex: str = ""
    confirmed_latex: str | None = None
    action: str  # confirm | correct
    paths_json: str | None = None
    stroke_metrics_json: str | None = None
    target_latex: str = ""


class TrainSampleOut(BaseModel):
    sample_id: str
    confirmed_latex: str
    teacher_latex: str = ""
    agree: str


@router.get("/train/curriculum")
def train_curriculum(user: User = Depends(get_current_user)):
    from backend.math.training_service import curriculum_with_progress

    return curriculum_with_progress(user.id)


@router.get("/train/progress")
def train_progress(user: User = Depends(get_current_user)):
    from backend.math.training_log import training_progress

    return training_progress(user.id)


@router.post("/train/sample", response_model=TrainSampleOut)
async def train_sample(body: TrainSampleIn, user: User = Depends(get_current_user)):
    from backend.integrations.nim_client import nim_available, nim_vision_latex
    from backend.math.training_log import log_training_sample

    if body.action not in ("confirm", "correct"):
        raise HTTPException(status_code=400, detail="action must be confirm or correct")
    if not (body.canvas_image or "").strip():
        raise HTTPException(status_code=400, detail="canvas_image is required")

    predicted = (body.predicted_latex or "").strip()
    if body.action == "confirm":
        confirmed = predicted
    else:
        confirmed = (body.confirmed_latex or "").strip()
        if not confirmed:
            raise HTTPException(status_code=400, detail="confirmed_latex required for correct action")

    teacher_latex = ""
    if body.action == "correct" and nim_available():
        try:
            teacher_latex = await nim_vision_latex(body.canvas_image)
        except Exception:
            teacher_latex = ""

    sample_id = log_training_sample(
        user_id=user.id,
        tier=body.tier,
        prompt_id=body.prompt_id,
        prompt_text=body.prompt_text,
        canvas_image=body.canvas_image,
        predicted_latex=predicted,
        confirmed_latex=confirmed,
        teacher_latex=teacher_latex,
        action=body.action,
        paths_json=body.paths_json,
        stroke_metrics_json=body.stroke_metrics_json,
        target_latex=body.target_latex,
    )

    agree = "true" if predicted == confirmed else ("teacher_match" if teacher_latex == confirmed else "corrected")
    return TrainSampleOut(
        sample_id=sample_id,
        confirmed_latex=confirmed,
        teacher_latex=teacher_latex,
        agree=agree,
    )


@router.post("/train/retrain")
def train_retrain_stub(
    _user: User = Depends(get_current_user),
    _admin: User = Depends(require_admin),
):
    """v1 stub — logs sample count; wire scripts/retrain_texteller.py in v2."""
    from backend.math.training_log import _read_rows

    total = len(_read_rows())
    return {
        "status": "stub",
        "message": "Fine-tune job not wired yet. Dataset ready for export.",
        "total_samples": total,
        "retrain_at": 50,
    }
