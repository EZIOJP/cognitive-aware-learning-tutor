"""Orchestrator for the unified Topic Study Flow."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.core.llm_job_context import llm_job
from backend.core.ollama_client import LlmOptions
from backend.models import User
from backend.quiz.handler import start_session
from backend.transcripts.notes_generator import resolve_transcript_path
from backend.transcripts.study_intel import generate_quiz_items, load_note_text

log = logging.getLogger(__name__)


def run_topic_study_flow(
    db: Session,
    user_id: int,
    *,
    topic: str,
    transcript_file: str,
    folder_path: str = "",
    title: str = "",
    ingest_corpus: bool = False,
    quiz_count: int = 8,
    start_quiz: bool = False,
    llm: LlmOptions | None = None,
    llm_tier: str | None = None,
    confirm_heavy_budget: bool = False,
) -> dict[str, Any]:
    """Execute the entire study flow: notes -> quiz (corpus RAG only when enabled)."""
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
    ingest_corpus: bool = False,
    quiz_count: int = 8,
    start_quiz: bool = False,
    llm: LlmOptions | None = None,
    llm_tier: str | None = None,
    confirm_heavy_budget: bool = False,
) -> dict[str, Any]:
    from backend.transcripts.note_generation import generate_notes_unified

    settings = get_settings()
    if not settings.corpus_grounded_notes:
        ingest_corpus = False

    transcript_path = resolve_transcript_path(transcript_file)
    note_title = (title or topic or transcript_path.stem).strip()

    path, _content, mode, rag_result = generate_notes_unified(
        transcript_path=transcript_path,
        transcript_file=transcript_file,
        title=note_title,
        topic=topic,
        folder_path=folder_path,
        llm=llm,
        llm_tier=llm_tier,
        confirm_heavy_budget=confirm_heavy_budget,
        ingest_corpus=ingest_corpus,
    )

    from backend.paths import NOTES_DIR

    relative_note_path = path.relative_to(NOTES_DIR).as_posix()
    meta = rag_result or {}
    note_text = load_note_text(db, user_id, relative_note_path)

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
                    "topic": topic,
                },
            )
            session_id = session_resp.get("session_id")

    return {
        "run_id": None,
        "topic": topic,
        "steps": {
            "retrieve": {"hit_count": int(meta.get("chunk_count") or 0)},
            "notes": {
                "mode": mode,
                "relative_path": relative_note_path,
                "filename": relative_note_path,
                "grounding_status": meta.get("grounding_status"),
                "grounding_reason": meta.get("grounding_reason"),
            },
            "corpus_handoff": meta.get("corpus_handoff") or {},
            "quiz": {
                "deck_id": None,
                "question_count": len(questions),
                "session_id": session_id,
            },
        },
        "next_urls": {
            "notes": f"/lecture-notes?file={relative_note_path}",
            "quiz": f"/review?session={session_id}" if session_id else "/review",
            "review_due": "/review",
        },
    }
