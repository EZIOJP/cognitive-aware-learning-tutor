"""Vocab + math API routes (shared DB session, hub side-effects)."""

from __future__ import annotations

import csv
import io
import json
import random
import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

try:
    import sympy as sp
except ImportError:
    sp = None

from fastapi import APIRouter, Depends, File, Header, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from backend.core.auth import (
    get_current_user,
    hash_password,
    require_admin,
    token_for,
    verify_password,
)
from backend.core.serializers import user_admin_payload
from backend.config import get_settings
from backend.hub.services.sessions import get_or_open_activity_session, start_activity_session
from backend.db.session import get_db
from backend.math.services.randomizer import pick_practice_problem
from backend.models import MathAttempt, MathQuestion, MathQuestionTemplate, User, WordProgress
from backend.vocab.hub_hooks import on_face_status, on_math_attempt, on_vocab_quiz_complete
from backend.vocab.quiz_store import (
    complete_quiz_session,
    create_quiz_session,
    get_quiz_session,
    save_quiz_session,
)
from backend.vocab.words import load_words, save_words

MASTERY_MASTERED = 6
GROUP_SIZE = 30


def _load_words(db: Session) -> list[dict[str, Any]]:
    return load_words(db)


def _save_words(db: Session, words: list[dict[str, Any]]) -> None:
    save_words(words, db)


def _to_iso_or_none(dt: datetime | None) -> str | None:
    if not dt:
        return None
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _parse_due(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def _calc_next_due(mastery: int) -> tuple[datetime, int]:
    days = 1 if mastery < 0 else 2 if mastery <= 2 else 7 if mastery <= 5 else 21 if mastery <= 8 else 60
    return datetime.now(UTC) + timedelta(days=days), days


def _merge_word(word: dict[str, Any], progress: WordProgress | None) -> dict[str, Any]:
    if not progress:
        return {
            **word,
            "mastery": 0,
            "times_asked": 0,
            "times_correct": 0,
            "consecutive_correct": 0,
            "accuracy_rate": 0.0,
            "is_due": False,
            "is_suspended": False,
        }
    is_due = bool(progress.due_date and datetime.now(UTC) >= progress.due_date and not progress.is_suspended)
    accuracy = (progress.times_correct / progress.times_asked * 100) if progress.times_asked > 0 else 0.0
    return {
        **word,
        "mastery": progress.mastery,
        "times_asked": progress.times_asked,
        "times_correct": progress.times_correct,
        "consecutive_correct": progress.consecutive_correct,
        "accuracy_rate": round(accuracy, 2),
        "is_due": is_due,
        "is_suspended": progress.is_suspended,
    }


class RegisterBody(BaseModel):
    username: str
    password: str


class LoginBody(BaseModel):
    username: str
    password: str


class QuizStartBody(BaseModel):
    quiz_type: str = "adaptive_group"
    group_number: int | None = None
    word_ids: list[int] = []


class QuizAnswerBody(BaseModel):
    word_id: int
    answer: str
    time_taken: int = 0


class WordUpdateBody(BaseModel):
    word: str | None = None
    pronunciation: str | None = None
    meaning: str | None = None
    story_mnemonic: str | None = None
    etymology: str | None = None
    examples: list[dict[str, Any]] | None = None
    synonyms: list[str] | None = None
    antonyms: list[str] | None = None
    tags: list[str] | None = None
    model_config = ConfigDict(extra="ignore")


class WordCreateBody(BaseModel):
    word: str
    meaning: str
    pronunciation: str | None = ""
    story_mnemonic: str | None = ""
    etymology: str | None = ""
    examples: list[dict[str, Any]] | None = None
    synonyms: list[str] | None = None
    antonyms: list[str] | None = None
    tags: list[str] | None = None
    model_config = ConfigDict(extra="ignore")


class ProgressUpdateBody(BaseModel):
    is_suspended: bool

class JsonImportBody(BaseModel):
    words: list[WordCreateBody]


class AdminPasswordResetBody(BaseModel):
    password: str


class MathTemplateBody(BaseModel):
    title: str
    topic: str = "Arithmetic"
    operation: str = "add"
    min_value: int = 1
    max_value: int = 20
    number_type: str = "any"
    decimal_places: int = 0
    points: int = 10
    is_active: bool = True


class MathAttemptBody(BaseModel):
    generated_id: str
    template_id: int | None = None
    question_id: int | None = None
    topic: str
    prompt: str
    expected_answer: str
    user_answer: str


class FaceFocusBody(BaseModel):
    not_focused: bool = False
    head_turned_away: bool = False
    long_eye_closure: bool = False
    no_face: bool = False


class FaceStatusBody(BaseModel):
    attention: float = 0
    attitude: str = "unknown"
    blink_rate: float = 0
    face_detected: bool = False
    details: dict[str, Any] = {}
    focus: FaceFocusBody | None = None


class FaceEnrollBody(BaseModel):
    embedding: list[float]


class FaceLoginBody(BaseModel):
    username: str
    embedding: list[float]


class FocusEventStartBody(BaseModel):
    event_type: str
    pomodoro_mode: str = "focus"


router = APIRouter(prefix="/api/vocab", tags=["vocab"])

_face_status: dict[str, Any] = {
    "attention": 0,
    "attitude": "not running",
    "blink_rate": 0,
    "face_detected": False,
    "updated_at": None,
    "details": {},
}


def _coerce_answer(value: float | int | str, decimal_places: int = 0) -> str:
    if isinstance(value, str):
        return value
    if decimal_places > 0:
        return f"{float(value):.{decimal_places}f}"
    if float(value).is_integer():
        return str(int(value))
    return str(round(float(value), 4))


def _random_number(tpl: MathQuestionTemplate) -> float | int:
    lo = min(tpl.min_value, tpl.max_value)
    hi = max(tpl.min_value, tpl.max_value)
    decimal_places = max(0, min(4, int(tpl.decimal_places or 0)))
    number_type = (tpl.number_type or "any").lower()

    if decimal_places > 0:
        scale = 10 ** decimal_places
        value = random.randint(lo * scale, hi * scale) / scale
        return round(value, decimal_places)

    pool = list(range(lo, hi + 1))
    if number_type == "odd":
        pool = [n for n in pool if n % 2 != 0]
    elif number_type == "even":
        pool = [n for n in pool if n % 2 == 0]
    elif number_type == "positive":
        pool = [n for n in pool if n > 0]
    elif number_type == "negative":
        pool = [n for n in pool if n < 0]
    if not pool:
        pool = list(range(lo, hi + 1)) or [0]
    return random.choice(pool)


def _generate_math_problem(tpl: MathQuestionTemplate) -> dict[str, Any]:
    operation = (tpl.operation or "add").lower()
    a = _random_number(tpl)
    b = _random_number(tpl)
    if operation == "divide":
        b = b or 1

    prompt = ""
    answer: float | int | str
    explanation = ""
    latex = ""

    if operation == "add":
        prompt = f"Solve: {a} + {b}"
        answer = float(a) + float(b)
    elif operation == "subtract":
        prompt = f"Solve: {a} - {b}"
        answer = float(a) - float(b)
    elif operation == "multiply":
        prompt = f"Solve: {a} x {b}"
        answer = float(a) * float(b)
    elif operation == "divide":
        prompt = f"Solve: {a} / {b}"
        answer = float(a) / float(b)
    elif operation == "linear_equation":
        x_value = int(_random_number(tpl))
        coeff = int(_random_number(tpl)) or 1
        offset = int(_random_number(tpl))
        rhs = coeff * x_value + offset
        prompt = f"Solve for x: {coeff}x + {offset} = {rhs}"
        answer = x_value
        explanation = "Move the constant term, then divide by the coefficient of x."
        if sp is not None:
            x = sp.symbols("x")
            latex = sp.latex(sp.Eq(coeff * x + offset, rhs))
    elif operation == "simplify":
        coeff_1 = int(_random_number(tpl))
        coeff_2 = int(_random_number(tpl))
        constant = int(_random_number(tpl))
        prompt = f"Simplify: {coeff_1}x + {coeff_2}x + {constant}"
        if sp is not None:
            x = sp.symbols("x")
            expr = sp.simplify(coeff_1 * x + coeff_2 * x + constant)
            answer = str(expr)
            latex = sp.latex(expr)
        else:
            answer = f"{coeff_1 + coeff_2}x + {constant}"
        explanation = "Combine like terms."
    else:
        prompt = f"Solve: {a} + {b}"
        answer = float(a) + float(b)

    expected = _coerce_answer(answer, tpl.decimal_places if operation == "divide" else 0)
    return {
        "generated_id": str(uuid.uuid4()),
        "template_id": tpl.id,
        "title": tpl.title,
        "topic": tpl.topic,
        "operation": operation,
        "prompt": prompt,
        "latex": latex,
        "expected_answer": expected,
        "points": tpl.points,
        "explanation": explanation,
        "sympy_enabled": sp is not None,
    }


@router.post("/auth/register")
def register(body: RegisterBody, db: Session = Depends(get_db)):
    username = body.username.strip().lower()
    if len(username) < 3 or len(body.password) < 6:
        raise HTTPException(status_code=400, detail="Username/password too short")
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(status_code=409, detail="Username already exists")
    settings = get_settings()
    user = User(
        username=username,
        password_hash=hash_password(body.password),
        password_plain=body.password if settings.expose_password_plain else None,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    from backend.hub.services.seed import seed_user_plugins

    seed_user_plugins(db, user.id)
    return {"token": token_for(user), "user": {"id": user.id, "username": user.username}}


@router.post("/auth/login")
def login(body: LoginBody, db: Session = Depends(get_db)):
    username = body.username.strip().lower()
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"token": token_for(user), "user": {"id": user.id, "username": user.username}}


@router.get("/auth/me")
def me(user: User = Depends(get_current_user)):
    return {"id": user.id, "username": user.username}


def _progress_map_for_user(db: Session, user_id: int) -> dict[int, WordProgress]:
    rows = db.query(WordProgress).filter(WordProgress.user_id == user_id).all()
    return {row.word_id: row for row in rows}


@router.get("/groups/detailed/")
def groups_detailed(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    words = _load_words(db)
    pmap = _progress_map_for_user(db, user.id)
    merged = [_merge_word(w, pmap.get(int(w["id"]))) for w in words]
    grouped: dict[int, list[dict[str, Any]]] = {}
    for w in merged:
        grouped.setdefault(int(w.get("group_number", 1)), []).append(w)
    result: list[dict[str, Any]] = []
    for gn in sorted(grouped):
        gw = grouped[gn]
        mastered = sum(1 for w in gw if int(w["mastery"]) >= MASTERY_MASTERED)
        not_started = sum(1 for w in gw if int(w["times_asked"]) == 0)
        due_review = sum(1 for w in gw if bool(w["is_due"]))
        total = len(gw)
        result.append({
            "group_number": gn,
            "total_words": total,
            "words_started": total - not_started,
            "words_mastered": mastered,
            "completion_percentage": round((mastered / total) * 100) if total else 0,
            "is_completed": mastered >= total * 0.8 if total else False,
            "mastery_threshold": MASTERY_MASTERED,
            "stats": {
                "mastered": mastered,
                "needPractice": sum(1 for w in gw if 0 < int(w["mastery"]) < MASTERY_MASTERED),
                "dueReview": due_review,
                "notStarted": not_started,
            },
        })
    return {"groups": result}


@router.get("/quiz/dashboard/")
def quiz_dashboard(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    words = _load_words(db)
    pmap = _progress_map_for_user(db, user.id)
    merged = [_merge_word(w, pmap.get(int(w["id"]))) for w in words]
    studied = [w for w in merged if int(w["times_asked"]) > 0]
    mastered = [w for w in merged if int(w["mastery"]) >= MASTERY_MASTERED]
    due_reviews = [w for w in merged if bool(w["is_due"])]
    low_mastery = [w for w in merged if int(w["mastery"]) <= 0]
    avg_accuracy = round(sum(float(w["accuracy_rate"]) for w in studied) / len(studied), 2) if studied else 0.0
    return {
        "total_words": len(merged),
        "studied_words": len(studied),
        "mastered": len(mastered),
        "due_reviews": {"count": len(due_reviews)},
        "low_mastery": {"count": len(low_mastery)},
        "suspended_words": sum(1 for w in merged if bool(w["is_suspended"])),
        "overall_accuracy": avg_accuracy,
        "study_coverage_pct": round((len(studied) / len(merged)) * 100, 2) if merged else 0.0,
        "streak": {"current_streak": 0},
    }


@router.post("/quiz/adaptive/start/")
def quiz_start(
    body: QuizStartBody,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    words = _load_words(db)
    if body.word_ids:
        pool = [w for w in words if int(w["id"]) in body.word_ids]
    elif body.group_number:
        pool = [w for w in words if int(w.get("group_number", 1)) == body.group_number]
    else:
        pool = words
    hub_sess = start_activity_session(
        db,
        user_id=user.id,
        session_type="vocab_quiz",
        metadata={"quiz_type": body.quiz_type, "group_number": body.group_number},
    )
    session_id = create_quiz_session(
        db,
        user_id=user.id,
        quiz_type=body.quiz_type,
        words=pool,
        hub_session_id=hub_sess.id,
    )
    return {
        "session_id": session_id,
        "hub_session_id": hub_sess.id,
        "total_questions": len(pool),
    }


@router.get("/quiz/adaptive/{session_id}/question/")
def quiz_question(
    session_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    sess = get_quiz_session(db, session_id, user.id)
    if not sess:
        return {"session_complete": True}
    idx = int(sess["index"])
    pool = sess["words"]
    if idx >= len(pool):
        return {"session_complete": True}
    w = pool[idx]
    all_meanings = [x["meaning"] for x in pool if x.get("meaning")]
    distractor_pool = [m for m in all_meanings if m != w["meaning"]]
    distractors = random.sample(distractor_pool, min(3, len(distractor_pool)))
    options = random.sample([w["meaning"], *distractors], len(distractors) + 1)
    return {
        "session_complete": False,
        "word_id": w["id"],
        "word": w["word"],
        "pronunciation": w.get("pronunciation", ""),
        "options": options,
        "question_number": idx + 1,
        "total_questions": len(pool),
    }


def _get_or_create_progress(db: Session, user_id: int, word_id: int) -> WordProgress:
    progress = db.query(WordProgress).filter(WordProgress.user_id == user_id, WordProgress.word_id == word_id).first()
    if progress:
        return progress
    progress = WordProgress(user_id=user_id, word_id=word_id)
    db.add(progress)
    db.commit()
    db.refresh(progress)
    return progress


@router.post("/quiz/adaptive/{session_id}/answer/")
def quiz_answer(
    session_id: str,
    body: QuizAnswerBody,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    sess = get_quiz_session(db, session_id, user.id)
    if not sess:
        raise HTTPException(status_code=404, detail="Quiz session not found")
    w = next((x for x in sess["words"] if int(x["id"]) == body.word_id), None)
    if not w:
        raise HTTPException(status_code=404, detail="Word not found in session")
    p = _get_or_create_progress(db, user.id, body.word_id)
    mastery_before = p.mastery
    is_correct = body.answer.strip() == str(w["meaning"]).strip()
    if is_correct:
        p.mastery += 1
        p.times_correct += 1
        p.consecutive_correct += 1
    else:
        p.mastery -= 2
        p.consecutive_correct = 0
    p.times_asked += 1
    if p.mastery >= 3 and is_correct:
        due, interval_days = _calc_next_due(p.mastery)
        p.due_date = due
        p.interval_days = interval_days
    db.add(p)
    db.commit()
    db.refresh(p)
    sess["attempts"].append({
        "word_id": body.word_id,
        "word": w["word"],
        "is_correct": is_correct,
        "mastery_before": mastery_before,
        "mastery_after": p.mastery,
    })
    sess["index"] += 1
    save_quiz_session(db, sess)
    return {
        "is_correct": is_correct,
        "correct_answer": w["meaning"],
        "mastery_before": mastery_before,
        "mastery_after": p.mastery,
    }


@router.post("/quiz/adaptive/{session_id}/complete/")
def quiz_complete(
    session_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    sess = get_quiz_session(db, session_id, user.id)
    if not sess:
        return {
            "performance": {
                "total_questions": 0,
                "correct_answers": 0,
                "accuracy_rate": 0,
                "words_improved": 0,
            },
            "attempts": [],
        }
    attempts = sess.get("attempts", [])
    correct = sum(1 for a in attempts if a["is_correct"])
    total = len(attempts)
    hub_session_id = complete_quiz_session(db, session_id, user.id)
    on_vocab_quiz_complete(
        db, user.id, correct, total, hub_session_id=hub_session_id
    )
    return {
        "performance": {
            "total_questions": total,
            "correct_answers": correct,
            "accuracy_rate": round((correct / total) * 100) if total else 0,
            "words_improved": sum(1 for a in attempts if a["mastery_after"] > a["mastery_before"]),
        },
        "attempts": attempts,
    }


@router.get("/words/by-criteria/")
def words_by_criteria(
    group: int | None = None,
    mastery_min: float | None = None,
    mastery_max: float | None = None,
    due_for_review: bool = False,
    word_ids: str | None = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    pmap = _progress_map_for_user(db, user.id)
    merged = [_merge_word(w, pmap.get(int(w["id"]))) for w in _load_words(db)]
    if word_ids:
        id_set = {int(x.strip()) for x in word_ids.split(",") if x.strip().isdigit()}
        if id_set:
            merged = [w for w in merged if int(w["id"]) in id_set]
    if group is not None:
        merged = [w for w in merged if int(w.get("group_number", 1)) == group]
    if mastery_min is not None:
        merged = [w for w in merged if float(w["mastery"]) >= mastery_min]
    if mastery_max is not None:
        merged = [w for w in merged if float(w["mastery"]) <= mastery_max]
    if due_for_review:
        merged = [w for w in merged if bool(w.get("is_due"))]
    page = merged[offset : offset + limit]
    return {
        "words": page,
        "pagination": {
            "limit": limit,
            "offset": offset,
            "returned": len(page),
            "total_available": len(merged),
            "has_more": offset + limit < len(merged),
        },
    }


@router.put("/words/{word_id}")
def update_word(
    word_id: int,
    body: WordUpdateBody,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    words = _load_words(db)
    idx = next((i for i, w in enumerate(words) if int(w["id"]) == word_id), -1)
    if idx < 0:
        raise HTTPException(status_code=404, detail="Word not found")
    patch = body.model_dump(exclude_none=True)
    words[idx] = {**words[idx], **patch}
    _save_words(db, words)
    return words[idx]


@router.post("/words")
def create_word(
    body: WordCreateBody,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    words = _load_words(db)
    next_id = max((int(w["id"]) for w in words), default=0) + 1
    new_word = {
        "id": next_id,
        **body.model_dump(exclude_none=True),
    }
    if new_word.get("examples") is None:
        new_word["examples"] = []
    if new_word.get("synonyms") is None:
        new_word["synonyms"] = []
    if new_word.get("antonyms") is None:
        new_word["antonyms"] = []
    if new_word.get("tags") is None:
        new_word["tags"] = []

    words.append(new_word)
    for i, w in enumerate(words):
        w["group_number"] = (i // GROUP_SIZE) + 1
    _save_words(db, words)
    return new_word


@router.delete("/words/{word_id}")
def delete_word(
    word_id: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    words = _load_words(db)
    filtered = [w for w in words if int(w["id"]) != word_id]
    if len(filtered) == len(words):
        raise HTTPException(status_code=404, detail="Word not found")
    for i, w in enumerate(filtered):
        w["group_number"] = (i // GROUP_SIZE) + 1
    _save_words(db, filtered)
    return {"deleted": word_id}


@router.post("/words/import/csv")
async def import_words_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    content = await file.read()
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="CSV must be utf-8") from exc
    reader = csv.DictReader(io.StringIO(text))
    words = _load_words(db)
    by_word = {str(w["word"]).strip().lower(): w for w in words}
    next_id = max((int(w["id"]) for w in words), default=0) + 1
    added = 0
    skipped = 0
    for row in reader:
        word = str(row.get("word", "")).strip()
        meaning = str(row.get("meaning", "")).strip()
        if not word or not meaning:
            skipped += 1
            continue
        key = word.lower()
        if key in by_word:
            skipped += 1
            continue
        item = {
            "id": next_id,
            "word": word,
            "meaning": meaning,
            "pronunciation": str(row.get("pronunciation", "")).strip(),
            "examples": [{"text": str(row.get("example", "")).strip()}] if str(row.get("example", "")).strip() else [],
        }
        words.append(item)
        by_word[key] = item
        next_id += 1
        added += 1
    for i, w in enumerate(words):
        w["group_number"] = (i // GROUP_SIZE) + 1
    _save_words(db, words)
    return {"added": added, "skipped": skipped, "total_words": len(words)}


@router.post("/words/import/json")
def import_words_json(
    body: JsonImportBody,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    words = _load_words(db)
    by_word = {str(w["word"]).strip().lower(): w for w in words}
    next_id = max((int(w["id"]) for w in words), default=0) + 1
    added = 0
    skipped = 0
    for w_data in body.words:
        word_str = w_data.word.strip()
        meaning = w_data.meaning.strip()
        if not word_str or not meaning:
            skipped += 1
            continue
        key = word_str.lower()
        if key in by_word:
            skipped += 1
            continue
        new_word = {
            "id": next_id,
            **w_data.model_dump(exclude_none=True),
        }
        if new_word.get("examples") is None:
            new_word["examples"] = []
        if new_word.get("synonyms") is None:
            new_word["synonyms"] = []
        if new_word.get("antonyms") is None:
            new_word["antonyms"] = []
        if new_word.get("tags") is None:
            new_word["tags"] = []

        words.append(new_word)
        by_word[key] = new_word
        next_id += 1
        added += 1

    for i, w in enumerate(words):
        w["group_number"] = (i // GROUP_SIZE) + 1
    _save_words(db, words)
    return {"added": added, "skipped": skipped, "total_words": len(words)}


@router.get("/words/export/csv")
def export_words_csv(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    words = _load_words(db)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "word", "meaning", "pronunciation", "group_number"])
    for w in words:
        writer.writerow([w.get("id"), w.get("word"), w.get("meaning"), w.get("pronunciation", ""), w.get("group_number", 1)])
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=vocab_words.csv"},
    )


@router.get("/words/export/group/{group_number}")
def export_words_group_json(
    group_number: int,
    include_progress: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Export one vocab group (full word objects) for backup, sharing, or external tools."""
    words = [w for w in _load_words(db) if int(w.get("group_number", 1)) == group_number]
    if not words:
        raise HTTPException(status_code=404, detail=f"Group {group_number} not found or empty")
    payload: dict[str, Any] = {
        "format_version": 1,
        "group_number": group_number,
        "word_count": len(words),
        "words": words,
    }
    if include_progress:
        pmap = _progress_map_for_user(db, user.id)
        payload["progress"] = [
            {
                "word_id": int(w["id"]),
                **_merge_word(w, pmap.get(int(w["id"]))),
            }
            for w in words
        ]
    return payload


@router.get("/words/export/group/{group_number}/csv")
def export_words_group_csv(
    group_number: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    words = [w for w in _load_words(db) if int(w.get("group_number", 1)) == group_number]
    if not words:
        raise HTTPException(status_code=404, detail=f"Group {group_number} not found or empty")
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "word", "meaning", "pronunciation", "group_number", "story_mnemonic", "etymology"])
    for w in words:
        writer.writerow([
            w.get("id"),
            w.get("word"),
            w.get("meaning"),
            w.get("pronunciation", ""),
            w.get("group_number", group_number),
            w.get("story_mnemonic", ""),
            w.get("etymology", ""),
        ])
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=vocab_group_{group_number}.csv"},
    )


@router.post("/progress/{word_id}/read")
def record_read_progress(
    word_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Bump mastery when the learner advances in Read Mode (same gentle boost as a correct review)."""
    _load_words(db)  # ensure word bank exists
    p = _get_or_create_progress(db, user.id, word_id)
    mastery_before = p.mastery
    p.mastery += 1
    p.times_asked += 1
    p.times_correct += 1
    p.consecutive_correct += 1
    if p.mastery >= 3:
        due, interval_days = _calc_next_due(p.mastery)
        p.due_date = due
        p.interval_days = interval_days
    db.add(p)
    db.commit()
    db.refresh(p)
    return {
        "word_id": word_id,
        "mastery_before": mastery_before,
        "mastery_after": p.mastery,
    }


@router.patch("/progress/{word_id}")
def update_progress(word_id: int, body: ProgressUpdateBody, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    progress = _get_or_create_progress(db, user.id, word_id)
    progress.is_suspended = body.is_suspended
    db.add(progress)
    db.commit()
    return {"word_id": word_id, "is_suspended": progress.is_suspended}


@router.get("/progress/summary")
def progress_summary(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    pmap = _progress_map_for_user(db, user.id)
    studied = [p for p in pmap.values() if p.times_asked > 0]
    return {
        "studied_words": len(studied),
        "mastered_words": sum(1 for p in pmap.values() if p.mastery >= MASTERY_MASTERED),
        "due_reviews": sum(1 for p in pmap.values() if p.due_date and datetime.now(UTC) >= p.due_date and not p.is_suspended),
        "suspended_words": sum(1 for p in pmap.values() if p.is_suspended),
        "avg_accuracy": round(sum((p.times_correct / p.times_asked * 100) for p in studied) / len(studied), 2) if studied else 0.0,
        "last_updated": _to_iso_or_none(max((p.updated_at for p in pmap.values()), default=None)),
    }


@router.get("/math/templates")
def math_templates(db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    templates = db.query(MathQuestionTemplate).order_by(MathQuestionTemplate.created_at.desc()).all()
    return {"templates": [
        {
            "id": t.id,
            "title": t.title,
            "topic": t.topic,
            "operation": t.operation,
            "min_value": t.min_value,
            "max_value": t.max_value,
            "number_type": t.number_type,
            "decimal_places": t.decimal_places,
            "points": t.points,
            "is_active": t.is_active,
            "created_at": _to_iso_or_none(t.created_at),
        }
        for t in templates
    ]}


@router.post("/math/templates")
def create_math_template(body: MathTemplateBody, db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    tpl = MathQuestionTemplate(**body.model_dump())
    db.add(tpl)
    db.commit()
    db.refresh(tpl)
    return {"template": {"id": tpl.id, **body.model_dump()}}


@router.put("/math/templates/{template_id}")
def update_math_template(template_id: int, body: MathTemplateBody, db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    tpl = db.get(MathQuestionTemplate, template_id)
    if not tpl:
        raise HTTPException(status_code=404, detail="Math template not found")
    for key, value in body.model_dump().items():
        setattr(tpl, key, value)
    db.add(tpl)
    db.commit()
    db.refresh(tpl)
    return {"template": {"id": tpl.id, **body.model_dump()}}


@router.delete("/math/templates/{template_id}")
def delete_math_template(template_id: int, db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    tpl = db.get(MathQuestionTemplate, template_id)
    if not tpl:
        raise HTTPException(status_code=404, detail="Math template not found")
    db.delete(tpl)
    db.commit()
    return {"deleted": template_id}


@router.get("/math/practice/next")
def next_math_problem(
    topic: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    def _from_template() -> dict[str, Any]:
        query = db.query(MathQuestionTemplate).filter(MathQuestionTemplate.is_active == True)
        if topic:
            query = query.filter(MathQuestionTemplate.topic == topic)
        templates = query.all()
        if not templates:
            raise HTTPException(status_code=404, detail="No active math templates or imported questions")
        recent = (
            db.query(MathAttempt.template_id)
            .filter(MathAttempt.user_id == user.id, MathAttempt.template_id.isnot(None))
            .order_by(MathAttempt.created_at.desc())
            .limit(5)
            .all()
        )
        recent_ids = {row[0] for row in recent}
        pool = [t for t in templates if t.id not in recent_ids] or templates
        return _generate_math_problem(random.choice(pool))

    hub_sess = get_or_open_activity_session(
        db, user_id=user.id, session_type="math_practice", metadata={"topic": topic}
    )
    problem = pick_practice_problem(db, topic, _from_template)
    return {"problem": problem, "hub_session_id": hub_sess.id}


def _normalize_math_answer(v: str) -> str:
    return v.strip().lower().replace(" ", "")


@router.post("/math/practice/submit")
def submit_math_attempt(body: MathAttemptBody, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    expected_raw = body.expected_answer
    if body.question_id:
        bank_q = db.get(MathQuestion, body.question_id)
        if bank_q:
            expected_raw = bank_q.expected_answer

    expected = _normalize_math_answer(expected_raw)
    actual = _normalize_math_answer(body.user_answer)
    is_correct = actual == expected

    tpl = db.get(MathQuestionTemplate, body.template_id) if body.template_id else None
    base_points = tpl.points if tpl else 10
    mastery_delta = base_points if is_correct else -max(3, base_points // 2)
    hub_sess = get_or_open_activity_session(
        db, user_id=user.id, session_type="math_practice", metadata={"topic": body.topic}
    )
    attempt = MathAttempt(
        user_id=user.id,
        template_id=body.template_id,
        question_id=body.question_id,
        generated_id=body.generated_id,
        topic=body.topic,
        prompt=body.prompt,
        expected_answer=expected_raw,
        user_answer=body.user_answer,
        is_correct=is_correct,
        mastery_delta=mastery_delta,
        hub_session_id=hub_sess.id,
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)
    on_math_attempt(db, user.id, is_correct, body.topic, hub_session_id=hub_sess.id)

    # --- Knowledge graph observation ---
    try:
        from backend.hub.services.knowledge_graph import log_observation, upsert_node  # noqa: PLC0415

        kg_node = upsert_node(db, user_id=user.id, label=body.topic, node_type="concept")
        log_observation(
            db,
            node_id=kg_node.id,
            user_id=user.id,
            interaction_type="math_fail" if not is_correct else "math_pass",
            value=float(mastery_delta),
        )
    except Exception:  # noqa: BLE001
        pass

    return {
        "is_correct": is_correct,
        "expected_answer": body.expected_answer,
        "mastery_delta": mastery_delta,
        "attempt_id": attempt.id,
    }


@router.get("/math/mastery")
def math_mastery(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    attempts = db.query(MathAttempt).filter(MathAttempt.user_id == user.id).all()
    by_topic: dict[str, dict[str, Any]] = {}
    for attempt in attempts:
        item = by_topic.setdefault(attempt.topic, {
            "topic": attempt.topic,
            "attempts": 0,
            "correct": 0,
            "mastery_points": 0,
            "last_practiced": None,
        })
        item["attempts"] += 1
        item["correct"] += 1 if attempt.is_correct else 0
        item["mastery_points"] = max(0, min(100, item["mastery_points"] + attempt.mastery_delta))
        item["last_practiced"] = _to_iso_or_none(attempt.created_at)

    rows = []
    for item in by_topic.values():
        attempts_count = int(item["attempts"])
        points = int(item["mastery_points"])
        status = "relearn" if points < 25 else "learning" if points < 55 else "practicing" if points < 85 else "mastered"
        rows.append({
            **item,
            "accuracy": round((item["correct"] / attempts_count) * 100, 1) if attempts_count else 0,
            "status": status,
        })
    return {"topics": sorted(rows, key=lambda r: r["topic"])}


@router.get("/math/sessions")
def math_sessions(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    attempts = db.query(MathAttempt).filter(MathAttempt.user_id == user.id).order_by(MathAttempt.created_at.desc()).limit(50).all()
    return {"attempts": [
        {
            "id": a.id,
            "topic": a.topic,
            "prompt": a.prompt,
            "expected_answer": a.expected_answer,
            "user_answer": a.user_answer,
            "is_correct": a.is_correct,
            "mastery_delta": a.mastery_delta,
            "created_at": _to_iso_or_none(a.created_at),
        }
        for a in attempts
    ]}


@router.post("/face/status")
def update_face_status(
    body: FaceStatusBody,
    db: Session = Depends(get_db),
    authorization: str | None = Header(None),
):
    from backend.core.auth import decode_user, ensure_demo_user

    user = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
        user = decode_user(token, db)
    if user is None and get_settings().dev_mode:
        user = ensure_demo_user(db)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    _face_status.update(body.model_dump())
    _face_status["updated_at"] = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    if body.face_detected:
        on_face_status(db, user.id, body.attention)
    return {"status": "ok", "face": _face_status}


@router.get("/face/status")
def face_status():
    return {"face": _face_status}


@router.post("/auth/face/enroll")
def face_enroll(body: FaceEnrollBody, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from backend.core.face_auth import embedding_to_json

    if len(body.embedding) < 8:
        raise HTTPException(status_code=400, detail="Invalid embedding vector.")
    user.face_embedding_json = embedding_to_json(body.embedding)
    db.commit()
    return {"status": "ok", "enrolled": True}


@router.get("/auth/face/status")
def face_enroll_status(user: User = Depends(get_current_user)):
    from backend.core.face_auth import parse_embedding

    return {"enrolled": parse_embedding(user.face_embedding_json) is not None}


@router.post("/auth/face/login")
def face_login(body: FaceLoginBody, db: Session = Depends(get_db)):
    from backend.core.auth import token_for
    from backend.core.face_auth import cosine_similarity, parse_embedding

    username = body.username.strip().lower()
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    stored = parse_embedding(user.face_embedding_json)
    if not stored:
        raise HTTPException(status_code=400, detail="Face not enrolled for this user.")
    if len(body.embedding) != len(stored):
        raise HTTPException(status_code=400, detail="Embedding dimension mismatch.")
    score = cosine_similarity(body.embedding, stored)
    if score < 0.85:
        raise HTTPException(status_code=401, detail="Face match failed.")
    return {"token": token_for(user), "user": {"id": user.id, "username": user.username}}


@router.post("/focus/events/start")
def focus_event_start(
    body: FocusEventStartBody,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from backend.models.study import FocusEvent

    if body.pomodoro_mode != "focus":
        return {"id": None, "skipped": True}
    row = FocusEvent(
        user_id=user.id,
        event_type=body.event_type,
        pomodoro_mode=body.pomodoro_mode,
        started_at=int(time.time()),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id}


class FocusEventEndBody(BaseModel):
    focus_score: float | None = None  # 0.0–1.0; None = not tracked
    active_note_path: str | None = None  # relative path to currently open note


@router.patch("/focus/events/{event_id}/end")
def focus_event_end(
    event_id: int,
    body: FocusEventEndBody | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from backend.models.study import FocusEvent

    row = db.query(FocusEvent).filter(FocusEvent.id == event_id, FocusEvent.user_id == user.id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Event not found.")
    now = int(time.time())
    row.ended_at = now
    row.duration_seconds = float(now - row.started_at)
    db.commit()

    # Log focus observation to knowledge graph
    focus_score = (body.focus_score if body else None) or 1.0
    active_note = body.active_note_path if body else None
    is_drop = focus_score < 0.4
    try:
        from backend.hub.services.knowledge_graph import log_observation, upsert_node  # noqa: PLC0415
        from backend.paths import NOTES_DIR  # noqa: PLC0415

        if active_note:
            from pathlib import Path as _Path  # noqa: PLC0415

            note_path = _Path(active_note)
            if not note_path.is_absolute():
                note_path = NOTES_DIR / note_path
            label = note_path.stem.replace("_", " ")
        else:
            label = "general_focus_session"

        kg_node = upsert_node(db, user_id=user.id, label=label, node_type="concept")
        log_observation(
            db,
            node_id=kg_node.id,
            user_id=user.id,
            interaction_type="focus_drop" if is_drop else "focus_ok",
            value=focus_score,
        )
    except Exception:  # noqa: BLE001
        pass

    return {"id": row.id, "duration_seconds": row.duration_seconds}


@router.get("/admin/users")
def admin_users(db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    users = db.query(User).order_by(User.created_at.desc()).all()
    out = []
    for u in users:
        progress_count = db.query(WordProgress).filter(WordProgress.user_id == u.id).count()
        mastered_count = db.query(WordProgress).filter(
            WordProgress.user_id == u.id,
            WordProgress.mastery >= MASTERY_MASTERED,
        ).count()
        out.append(
            user_admin_payload(
                u, progress_rows=progress_count, mastered_rows=mastered_count
            )
        )
    return {"users": out}


@router.post("/admin/users/{user_id}/reset-progress")
def admin_reset_user_progress(
    user_id: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db.query(WordProgress).filter(WordProgress.user_id == user_id).delete()
    db.commit()
    return {"status": "ok", "user_id": user_id, "message": "Progress reset"}


@router.post("/admin/users/{user_id}/reset-password")
def admin_reset_user_password(
    user_id: int,
    body: AdminPasswordResetBody,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    if len(body.password) < 3:
        raise HTTPException(status_code=400, detail="Password too short")
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    settings = get_settings()
    user.password_hash = hash_password(body.password)
    if settings.expose_password_plain:
        user.password_plain = body.password
    db.add(user)
    db.commit()
    out = {
        "status": "ok",
        "user_id": user_id,
        "username": user.username,
        "message": "Password reset",
    }
    if settings.expose_password_plain:
        out["password"] = body.password
    return out


@router.post("/admin/users/reset-all-progress")
def admin_reset_all_users_progress(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    db.query(WordProgress).delete()
    db.commit()
    return {"status": "ok", "message": "All users progress reset"}
