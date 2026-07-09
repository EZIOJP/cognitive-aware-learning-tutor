"""Orchestrator for the unified Topic Study Flow."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from backend.core.llm_job_context import llm_job
from backend.core.ollama_client import LlmOptions
from backend.models import User
from backend.transcripts.study_intel import generate_quiz_items, load_note_text
from backend.corpus.grounded_notes import generate_grounded_notes
from backend.quiz.handler import start_session

log = logging.getLogger(__name__)


def run_topic_study_flow(
    db: Session,
    user_id: int,
    *,
    topic: str,
    transcript_file: str,
    folder_path: str = "",
    title: str = "",
    ingest_corpus: bool = True,
    quiz_count: int = 8,
    start_quiz: bool = False,
    llm: LlmOptions | None = None,
    llm_tier: str | None = None,
    confirm_heavy_budget: bool = False,
) -> dict[str, Any]:
    """Execute the entire study flow: notes -> ingest -> quiz."""
    log.info("Starting topic study flow for topic=%s user_id=%s", topic, user_id)

    with llm_job(tier=llm_tier, task="notes_job"):
        return _run_topic_study_flow_impl(
            db,
            user_id,
            topic=topic,
            transcript_file=transcript_file,
            folder_path=folder_path,
            title=title,
            ingest_corpus=ingest_corpus,
            quiz_count=quiz_count,
            start_quiz=start_quiz,
            llm=llm,
            llm_tier=llm_tier,
            confirm_heavy_budget=confirm_heavy_budget,
        )


def _run_topic_study_flow_impl(
    db: Session,
    user_id: int,
    *,
    topic: str,
    transcript_file: str,
    folder_path: str = "",
    title: str = "",
    ingest_corpus: bool = True,
    quiz_count: int = 8,
    start_quiz: bool = False,
    llm: LlmOptions | None = None,
    llm_tier: str | None = None,
    confirm_heavy_budget: bool = False,
) -> dict[str, Any]:
    # 1. Retrieve & Notes & Corpus Handoff
    # generate_grounded_notes does hybrid_retrieve and ingest_lecture_handoff internally
    notes_result = generate_grounded_notes(
        transcript_file=transcript_file,
        topic=topic,
        folder_path=folder_path,
        title=title,
        llm=llm,
        llm_tier=llm_tier,
        confirm_heavy_budget=confirm_heavy_budget,
        ingest_corpus=ingest_corpus,
    )
    
    relative_note_path = notes_result.get("filename")
    if not relative_note_path:
        raise RuntimeError("Failed to generate grounded notes.")
        
    # Load the generated note text for quiz generation
    note_text = load_note_text(db, user_id, relative_note_path)
    
    # 2. Generate Quiz
    quiz_data = generate_quiz_items(
        [note_text],
        count=quiz_count,
        topic=topic,
        llm=llm,
        llm_tier=llm_tier,
        confirm_heavy_budget=confirm_heavy_budget,
        prefer_notes=True,
    )
    
    questions = quiz_data.get("questions") or []
    
    # 3. Create Quiz Session (if questions exist)
    session_id = None
    if questions:
        user_obj = db.get(User, user_id)
        if user_obj:
            session_resp = start_session(
                db, 
                user=user_obj, 
                domain="study", 
                config={
                    "questions": questions,
                    "note_path": relative_note_path,
                    "topic": topic
                }
            )
            session_id = session_resp.get("session_id")
            
    # Mocking deck_id as we're relying on global study sessions instead of QuizDeck
    deck_id = None
    
    return {
        "run_id": None,
        "topic": topic,
        "steps": {
            "retrieve": { "hit_count": notes_result.get("chunk_count", 0) },
            "notes": { 
                "mode": notes_result.get("mode", "unknown"), 
                "relative_path": relative_note_path, 
                "filename": relative_note_path 
            },
            "corpus_handoff": notes_result.get("corpus_handoff") or {},
            "quiz": { 
                "deck_id": deck_id, 
                "question_count": len(questions), 
                "session_id": session_id 
            }
        },
        "next_urls": {
            "notes": f"/lecture-notes?file={relative_note_path}",
            "quiz": f"/review?session={session_id}" if session_id else "/review",
            "review_due": "/review"
        }
    }
