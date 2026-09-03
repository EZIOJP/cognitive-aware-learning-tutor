"""Global quiz API — vocab, math, study, code, review, and custom decks."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy.orm import Session

from backend.core.auth import get_current_user
from backend.db.session import get_db
from backend.models import User
from backend.quiz import handler

router = APIRouter(prefix="/api/quiz", tags=["quiz"])


class QuizStartBody(BaseModel):
    domain: str = Field(..., description="vocab | math | study | code | mixed | review | deck")
    config: dict[str, Any] = Field(default_factory=dict)


class QuizAnswerBody(BaseModel):
    item_id: str
    response: str
    time_taken_ms: int = 0


class ReadCardPatchBody(BaseModel):
    body_markdown: str
    title: str | None = None
    expected_mtime: float | None = None


class TagCreateBody(BaseModel):
    id: str
    question_id: str | None = None
    word_ids: list[int] | None = None
    note_path: str | None = None
    topic_id: str | None = None


class TagRenameBody(BaseModel):
    new_id: str
    label: str | None = None


class TagMergeBody(BaseModel):
    from_tag: str
    into_tag: str


class QuestionUpsertBody(BaseModel):
    model_config = ConfigDict(extra="allow")
    kind: str
    topic_id: str
    topic_title: str = ""
    note_topic_ids: list[str] = Field(default_factory=list)
    question: dict[str, Any]


class QuestionImportBody(BaseModel):
    model_config = ConfigDict(extra="allow")
    kind: str
    topic_id: str
    note_topic_ids: list[str] = Field(default_factory=list)
    raw: Any = None
    markdown: str | None = None
    content: Any = None


class DeckSaveBody(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    topic: str = Field(default="", max_length=160)
    domain: str = Field(default="study", max_length=24)
    items: list[dict[str, Any]] = Field(default_factory=list)
    time_limit_sec: int | None = Field(default=None, ge=30, le=7200)
    deck_id: int | None = None


class LoopSessionCreateBody(BaseModel):
    tag: str = Field(..., min_length=1, max_length=160)


class LoopPracticeBody(BaseModel):
    count: int = Field(default=5, ge=1, le=50)
    kinds: list[str] | None = None


class CodeRunBody(BaseModel):
    code: str
    item: dict[str, Any] | None = None
    item_id: str | None = None


@router.get("/backlog")
def get_quiz_backlog(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return handler.get_backlog(db, user=user)


@router.get("/decks")
def get_quiz_decks(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return {"decks": handler.list_decks(db, user=user)}


@router.post("/decks")
def post_quiz_deck(
    body: DeckSaveBody,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        return handler.save_deck(
            db,
            user=user,
            title=body.title,
            items=body.items,
            domain=body.domain,
            topic=body.topic,
            time_limit_sec=body.time_limit_sec,
            deck_id=body.deck_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/decks/{deck_id}")
def delete_quiz_deck(
    deck_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        handler.delete_deck(db, user=user, deck_id=deck_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"deleted": True}


@router.delete("/review-cards")
def delete_review_cards(
    domain: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Clear Review Hub cards so new quizzes can seed fresh items."""
    result = handler.clear_review_cards(db, user=user, domain=domain)
    return result


@router.post("/wipe-practice")
def post_wipe_practice(
    all_users: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Wipe decks, ReviewCards, and quiz sessions. Vocab word bank is kept."""
    return handler.wipe_practice_history(db, user=user, all_users=all_users)


@router.get("/results/recent")
def get_recent_quiz_results(
    limit: int = 10,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return {"results": handler.list_recent_results(db, user=user, limit=min(limit, 30))}


@router.get("/review/due")
def get_due_review(
    limit: int = 40,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = handler.list_due_items(db, user=user, limit=min(limit, 100))
    return {"items": items, "count": len(items)}


@router.get("/content/catalog")
def get_content_catalog(
    kind: str | None = None,
    track: str | None = None,
    note_topic_id: str | None = None,
    user: User = Depends(get_current_user),
):
    """Hybrid catalog: curated content_bank packs + mathgenerator recipes + DB counts."""
    from backend.quiz import content_bank as cb
    from backend.quiz import math_generators as mg
    from backend.models import MathQuestion

    _ = user
    catalog = cb.load_catalog()
    topics = cb.list_topics(kind=kind, track=track, note_topic_id=note_topic_id)
    curated = [t.to_summary() for t in topics]
    for row in curated:
        row["bank"] = "curated"

    generators: list[dict] = []
    gen_err: str | None = None
    try:
        gen_payload = mg.catalog_generators()
        generators = gen_payload["generators"]
        if note_topic_id:
            tag = note_topic_id.strip().upper()
            generators = [g for g in generators if tag in (g.get("note_topic_ids") or [])]
        if track and track.strip().lower() not in ("", "generator", "all"):
            # keep curated only when filtering a non-generator track
            if track.strip().lower() != "aptitude":
                pass
        for g in generators:
            g["bank"] = "generator"
    except Exception as exc:  # noqa: BLE001
        gen_err = str(exc)
        generators = []

    db_count = 0
    try:
        from backend.db.session import SessionLocal

        s = SessionLocal()
        try:
            db_count = s.query(MathQuestion).filter(MathQuestion.is_active == True).count()  # noqa: E712
        finally:
            s.close()
    except Exception:  # noqa: BLE001
        db_count = 0

    base = catalog.to_dict()
    return {
        **base,
        "topics": curated,
        "generators": generators,
        "generator_count": len(generators),
        "db_question_count": db_count,
        "hybrid": True,
        "generator_error": gen_err,
    }


@router.post("/content/sync-db")
def post_content_sync_db(
    kind: str = "math",
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Upsert curated content_bank math items into math_questions SQLite table."""
    from backend.quiz import content_bank as cb

    _ = user
    return cb.sync_curated_to_db(db, kind=kind)


@router.get("/content/curriculum")
def get_content_curriculum(user: User = Depends(get_current_user)):
    """Math Daily Path unlock order (data/questions/math/curriculum.json)."""
    import json

    from backend.paths import QUESTIONS_DIR

    _ = user
    path = QUESTIONS_DIR / "math" / "curriculum.json"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="curriculum.json not found")
    return json.loads(path.read_text(encoding="utf-8"))


@router.post("/content/import")
def post_content_import(
    kind: str | None = None,
    topic_id: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Seed FSRS ReviewCards from authored content packs."""
    from backend.quiz import content_bank as cb

    return cb.import_content(db, user_id=user.id, kind=kind, topic_id=topic_id)


@router.get("/study-loop/tags")
def get_study_loop_tags(
    q: str | None = None,
    kind: str | None = None,
    user: User = Depends(get_current_user),
):
    from backend.quiz import tag_index as ti

    _ = user
    tags = ti.list_tags(q=q, kind=kind)
    return {"tags": tags, "count": len(tags)}


@router.post("/study-loop/tags")
def post_study_loop_tag(
    body: TagCreateBody,
    user: User = Depends(get_current_user),
):
    from backend.quiz import tag_index as ti

    _ = user
    try:
        return ti.add_tag(
            body.id,
            question_id=body.question_id,
            word_ids=body.word_ids,
            note_path=body.note_path,
            topic_id=body.topic_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/study-loop/tags/merge")
def post_study_loop_tags_merge(
    body: TagMergeBody,
    user: User = Depends(get_current_user),
):
    from backend.quiz import tag_index as ti

    _ = user
    try:
        return ti.merge_tags(body.from_tag, body.into_tag)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/study-loop/tags/{tag}")
def patch_study_loop_tag(
    tag: str,
    body: TagRenameBody,
    user: User = Depends(get_current_user),
):
    from backend.quiz import tag_index as ti

    _ = user
    try:
        result = ti.rename_tag(tag, body.new_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if body.label is not None:
        result = {**result, "label": body.label}
    return result


@router.get("/study-loop/read-cards")
def get_study_loop_read_cards(
    tag: str | None = None,
    user: User = Depends(get_current_user),
):
    from backend.quiz import read_cards as rc

    _ = user
    items = rc.list_read_cards(tag=tag)
    return {"items": items, "count": len(items)}


@router.get("/study-loop/read-cards/{card_id:path}")
def get_study_loop_read_card(
    card_id: str,
    user: User = Depends(get_current_user),
):
    from backend.quiz import read_cards as rc

    _ = user
    card = rc.get_read_card(card_id)
    if card is None:
        raise HTTPException(status_code=404, detail="Read card not found.")
    return card


@router.patch("/study-loop/read-cards/{card_id:path}")
def patch_study_loop_read_card(
    card_id: str,
    body: ReadCardPatchBody,
    user: User = Depends(get_current_user),
):
    from backend.quiz import note_writeback as wb
    from backend.quiz.read_cards import parse_card_id

    _ = user
    try:
        note_path, topic_id = parse_card_id(card_id)
        result = wb.patch_note_section(
            note_path=note_path,
            topic_id=topic_id,
            body_markdown=body.body_markdown,
            title=body.title,
            expected_mtime=body.expected_mtime,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        if str(exc) == "mtime_conflict":
            raise HTTPException(
                status_code=409,
                detail="Note changed on disk. Reload before saving.",
            ) from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result


@router.get("/study-loop/questions")
def get_study_loop_questions(
    tag: str | None = None,
    kind: str | None = None,
    user: User = Depends(get_current_user),
):
    from backend.quiz import question_crud as qc

    _ = user
    items = qc.list_questions(tag=tag, kind=kind)
    return {"items": items, "count": len(items)}


@router.post("/study-loop/questions")
def post_study_loop_question(
    body: QuestionUpsertBody,
    user: User = Depends(get_current_user),
):
    from backend.quiz import question_crud as qc

    _ = user
    try:
        return qc.upsert_question(body.model_dump())
    except (ValueError, FileNotFoundError, ValidationError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/study-loop/questions/{question_id:path}")
def patch_study_loop_question(
    question_id: str,
    body: dict[str, Any],
    user: User = Depends(get_current_user),
):
    from backend.quiz import question_crud as qc

    _ = user
    try:
        return qc.patch_question(question_id, body)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/study-loop/questions/{question_id:path}")
def delete_study_loop_question(
    question_id: str,
    user: User = Depends(get_current_user),
):
    from backend.quiz import question_crud as qc

    _ = user
    try:
        return qc.delete_question(question_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/study-loop/questions/import")
def post_study_loop_questions_import(
    body: QuestionImportBody,
    user: User = Depends(get_current_user),
):
    from backend.quiz import question_crud as qc

    _ = user
    raw = body.raw if body.raw is not None else body.markdown if body.markdown is not None else body.content
    try:
        return qc.import_questions(
            raw,
            kind=body.kind,
            topic_id=body.topic_id,
            note_topic_ids=body.note_topic_ids,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _study_loop_http(exc: ValueError) -> HTTPException:
    msg = str(exc)
    if msg == "session_not_found":
        return HTTPException(status_code=404, detail=msg)
    if msg == "no_practice_content":
        return HTTPException(status_code=400, detail=msg)
    return HTTPException(status_code=400, detail=msg)


@router.post("/study-loop/sessions")
def post_study_loop_session(
    body: LoopSessionCreateBody,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from backend.quiz import study_loop as sl

    try:
        return sl.create_loop_session(user_id=user.id, tag=body.tag, db=db)
    except ValueError as exc:
        raise _study_loop_http(exc) from exc


@router.get("/study-loop/sessions/{session_id}")
def get_study_loop_session(
    session_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from backend.quiz import study_loop as sl

    try:
        return sl.get_session(user_id=user.id, session_id=session_id, db=db)
    except ValueError as exc:
        raise _study_loop_http(exc) from exc


@router.post("/study-loop/sessions/{session_id}/mark-read")
def post_study_loop_mark_read(
    session_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from backend.quiz import study_loop as sl

    try:
        return sl.mark_read(user_id=user.id, session_id=session_id, db=db)
    except ValueError as exc:
        raise _study_loop_http(exc) from exc


@router.post("/study-loop/sessions/{session_id}/start-practice")
def post_study_loop_start_practice(
    session_id: str,
    body: LoopPracticeBody | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from backend.quiz import study_loop as sl

    payload = body or LoopPracticeBody()
    try:
        return sl.start_practice(
            db=db,
            user=user,
            session_id=session_id,
            count=payload.count,
            kinds=payload.kinds,
        )
    except ValueError as exc:
        raise _study_loop_http(exc) from exc


@router.post("/code/run")
def post_code_run(body: CodeRunBody, user: User = Depends(get_current_user)):
    from backend.quiz import code_runner as cr
    from backend.quiz import content_bank as cb

    _ = user
    item = body.item
    if item is None and body.item_id:
        found = cb.get_questions(question_ids=[body.item_id])
        item = found[0] if found else None
    if not item:
        raise HTTPException(status_code=400, detail="item or item_id required")
    correct, feedback, payload = cr.grade_submission(item, body.code)
    return {"correct": correct, "feedback": feedback, **payload}


class ImportancePutBody(BaseModel):
    importance: int = Field(..., ge=1, le=5)
    note: str | None = None
    expected_updated_at: str | None = None


class LowMasteryStartBody(BaseModel):
    tag: str | None = None
    count: int | None = Field(default=None, ge=1, le=40)


class ImportanceSuggestBody(BaseModel):
    tags: list[str] | None = None
    overwrite_claude: bool = False


@router.get("/importance")
def get_importance(
    tag: str | None = None,
    user: User = Depends(get_current_user),
):
    from backend.quiz import importance as imp

    _ = user
    store = imp.load_store()
    if tag:
        row = (store.get("tags") or {}).get(tag)
        return {
            "tag_id": tag,
            "importance": imp.importance_for(tag, store),
            "source": (row or {}).get("source", "default"),
            "updated_at": (row or {}).get("updated_at"),
            "note": (row or {}).get("note"),
            "bar": imp.bar_for(imp.importance_for(tag, store)),
            "interval_factor": imp.interval_factor_for(imp.importance_for(tag, store)),
            "row": row,
        }
    return store


@router.get("/importance/low-mastery")
def get_low_mastery(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from backend.quiz import importance as imp
    from backend.quiz import tag_index as ti
    from backend.models.review_card import ReviewCard

    store = imp.load_store()
    cards = db.query(ReviewCard).filter(ReviewCard.user_id == user.id).all()
    tag_ids = [str(t["id"]) for t in ti.list_tags()]
    return {"tags": imp.list_low_mastery(cards, tag_ids, store)}


@router.post("/importance/low-mastery/start")
def post_low_mastery_start(
    body: LowMasteryStartBody | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    payload = body or LowMasteryStartBody()
    try:
        return handler.start_low_mastery_session(
            db, user=user, tag=payload.tag, count=payload.count
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/importance/suggest")
def post_importance_suggest(
    body: ImportanceSuggestBody | None = None,
    user: User = Depends(get_current_user),
):
    from backend.core.llm_gateway import llm_complete
    from backend.quiz import importance as imp
    from backend.quiz import tag_index as ti

    _ = user
    payload = body or ImportanceSuggestBody()
    known = {str(t["id"]) for t in ti.list_tags()}
    want = payload.tags or sorted(known)
    prompt = (
        "Assign importance 1-5 for these study tags. "
        "Return JSON {\"suggestions\": [{\"tag_id\": \"...\", \"importance\": 3, \"note\": \"optional\"}]}.\n"
        f"Tags: {json.dumps(want[:200])}"
    )
    try:
        result = llm_complete(prompt, task="classify", json_schema=None)
        text = getattr(result, "text", None)
        if not text:
            raise imp.SuggestLlmError("llm_failed")
        return imp.run_suggest(
            tags=payload.tags,
            overwrite_claude=payload.overwrite_claude,
            known_tags=known,
            llm_text=text,
        )
    except Exception as exc:
        if isinstance(exc, HTTPException):
            raise
        if isinstance(exc, imp.SuggestLlmError):
            raise HTTPException(status_code=502, detail="suggest_llm_failed") from exc
        raise HTTPException(status_code=502, detail="suggest_llm_failed") from exc


@router.get("/importance/{tag}")
def get_importance_tag(
    tag: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from backend.quiz import importance as imp
    from backend.models.review_card import ReviewCard

    store = imp.load_store()
    row = (store.get("tags") or {}).get(tag)
    cards = db.query(ReviewCard).filter(ReviewCard.user_id == user.id).all()
    progress = imp.progress_for_tag(cards, tag, store)
    return {
        "tag_id": tag,
        "importance": imp.importance_for(tag, store),
        "source": (row or {}).get("source", "default"),
        "updated_at": (row or {}).get("updated_at"),
        "note": (row or {}).get("note"),
        "bar": progress["bar"],
        "interval_factor": imp.interval_factor_for(imp.importance_for(tag, store)),
        "progress": {
            "cleared": progress["cleared"],
            "total": progress["total"],
            "mastered": progress["mastered"],
        },
    }


@router.put("/importance/{tag}")
def put_importance_tag(
    tag: str,
    body: ImportancePutBody,
    user: User = Depends(get_current_user),
):
    from backend.quiz import importance as imp

    _ = user
    try:
        row = imp.put_importance(
            tag,
            body.importance,
            note=body.note,
            expected_updated_at=body.expected_updated_at,
            source="user",
        )
    except ValueError as exc:
        if str(exc) == "mtime_conflict":
            raise HTTPException(status_code=409, detail="mtime_conflict") from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return row


@router.post("/start")
def start_quiz(
    body: QuizStartBody,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        return handler.start_session(db, user=user, domain=body.domain, config=body.config)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{session_id}/question")
def get_quiz_question(
    session_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = handler.get_question(db, user=user, session_id=session_id)
    if q is None:
        raise HTTPException(status_code=404, detail="No more questions or session not found.")
    return {"question": q}


@router.post("/{session_id}/answer")
def post_quiz_answer(
    session_id: str,
    body: QuizAnswerBody,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        return handler.submit_answer(
            db,
            user=user,
            session_id=session_id,
            item_id=body.item_id,
            response=body.response,
            time_taken_ms=body.time_taken_ms,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{session_id}/complete")
def post_quiz_complete(
    session_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return handler.complete_session(db, user=user, session_id=session_id)
