"""Global quiz API — vocab, math, study, code, review, and custom decks."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
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


class DeckSaveBody(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    topic: str = Field(default="", max_length=160)
    domain: str = Field(default="study", max_length=24)
    items: list[dict[str, Any]] = Field(default_factory=list)
    time_limit_sec: int | None = Field(default=None, ge=30, le=7200)
    deck_id: int | None = None


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
