"""Aggregate logged-in user data + project overview for the AI study coach."""

from __future__ import annotations

import time
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from backend.models import (
    FocusEvent,
    LectureNote,
    LifeDailyLog,
    MathAttempt,
    User,
    UserPlugin,
    WordProgress,
)
from backend.vocab.words import load_words

MASTERY_MASTERED = 6

PROJECT_OVERVIEW = """
Cognitive-Aware Learning Tutor — local-first study dashboard (React + FastAPI + SQLite).

Mission: help the student study smarter with optional biometric/focus awareness, not guilt or hustle culture.

Primary study loops:
- GRE Vocabulary: Read Mode → Quiz → Report → Low-Mastery → back to Read (/gre-vocab)
- Math Tutor: practice, canvas OCR, rule-based + optional local AI hints (/math-tutor)
- Life Tracker: sleep, study minutes, mood, life score (/life-tracker)
- Lecture Notes: Windows Live Captions → AI notes (/lecture-notes)
- Project Agent: Gemma + codebase file access for finishing the app (/project-agent) — pairs with Cursor
- Focus Mirror: webcam attention + Pomodoro red-border when unfocused 5s+ (plugin)
- Pomodoro: focus/break cycles in the top bar

Coach attitude: warm, direct, practical. Never say "optimize" or "productivity" as buzzwords.
Suggest ONE clear next action when the student is stuck. Tie advice to their actual metrics below.
If they ask what the app does, explain routes above in plain language.
""".strip()


def _vocab_summary(db: Session, user_id: int) -> dict[str, Any]:
    words = load_words(db)
    total_words = len(words)
    rows = db.query(WordProgress).filter(WordProgress.user_id == user_id).all()
    now = datetime.now(timezone.utc)
    studied = sum(1 for p in rows if (p.times_asked or 0) > 0)
    mastered = sum(1 for p in rows if (p.mastery or 0) >= MASTERY_MASTERED)
    low_mastery = sum(1 for p in rows if (p.mastery or 0) <= 0 and (p.times_asked or 0) > 0)
    due = sum(
        1
        for p in rows
        if p.due_date is not None
        and p.due_date.replace(tzinfo=timezone.utc) <= now
        and not p.is_suspended
    )
    accuracy_vals = [
        round((p.times_correct or 0) / max(1, p.times_asked or 0) * 100, 1)
        for p in rows
        if (p.times_asked or 0) > 0
    ]
    avg_accuracy = round(sum(accuracy_vals) / len(accuracy_vals), 2) if accuracy_vals else 0.0
    return {
        "total_words": total_words,
        "studied_words": studied,
        "mastered_words": mastered,
        "low_mastery_words": low_mastery,
        "due_for_review": due,
        "overall_accuracy_pct": avg_accuracy,
        "recommended_loop": "Read → Quiz → Report → Low-Mastery",
    }


def _life_recent(db: Session, user_id: int, *, days: int = 7) -> list[dict[str, Any]]:
    since = date.today() - timedelta(days=days - 1)
    rows = (
        db.query(LifeDailyLog)
        .filter(LifeDailyLog.user_id == user_id, LifeDailyLog.date >= since)
        .order_by(LifeDailyLog.date.desc())
        .all()
    )
    return [
        {
            "date": str(r.date),
            "life_score": r.life_score,
            "study_minutes": r.study_minutes,
            "sleep_hours": r.sleep_hours,
            "mood_score": r.mood_score,
            "stress_level": r.stress_level,
            "deep_work_blocks": r.deep_work_blocks,
        }
        for r in rows
    ]


def _focus_summary(db: Session, user_id: int, *, days: int = 7) -> dict[str, Any]:
    since = int(time.time()) - days * 86400
    rows = (
        db.query(FocusEvent)
        .filter(FocusEvent.user_id == user_id, FocusEvent.started_at >= since)
        .order_by(FocusEvent.started_at.desc())
        .limit(15)
        .all()
    )
    by_type: dict[str, int] = {}
    total_distraction_sec = 0.0
    for r in rows:
        by_type[r.event_type] = by_type.get(r.event_type, 0) + 1
        if r.duration_seconds:
            total_distraction_sec += r.duration_seconds
    return {
        "events_last_7_days": len(rows),
        "by_type": by_type,
        "total_distraction_minutes": round(total_distraction_sec / 60, 1),
        "recent": [
            {
                "type": r.event_type,
                "minutes": round((r.duration_seconds or 0) / 60, 1),
                "when": r.started_at,
            }
            for r in rows[:5]
        ],
    }


def _math_summary(db: Session, user_id: int) -> dict[str, Any]:
    today = date.today()
    total = db.query(MathAttempt).filter(MathAttempt.user_id == user_id).count()
    today_count = (
        db.query(MathAttempt)
        .filter(MathAttempt.user_id == user_id, MathAttempt.created_at >= datetime.combine(today, datetime.min.time()))
        .count()
    )
    return {"attempts_today": today_count, "attempts_total": total}


def _notes_summary(db: Session, user_id: int) -> dict[str, Any]:
    rows = (
        db.query(LectureNote)
        .filter(LectureNote.user_id == user_id)
        .order_by(LectureNote.created_at.desc())
        .limit(12)
        .all()
    )
    topics = sorted({r.topic for r in rows if r.topic})
    return {
        "count": db.query(LectureNote).filter(LectureNote.user_id == user_id).count(),
        "topics": topics[:8],
        "recent_titles": [r.title for r in rows[:6]],
    }


def _plugins_enabled(db: Session, user_id: int) -> list[str]:
    rows = db.query(UserPlugin).filter(UserPlugin.user_id == user_id, UserPlugin.enabled.is_(True)).all()
    return sorted({r.plugin_id for r in rows})


def _face_snapshot() -> dict[str, Any] | None:
    try:
        from backend.vocab.routes import _face_status

        face = dict(_face_status)
        if not face.get("updated_at"):
            return None
        return {
            "attention": face.get("attention"),
            "attitude": face.get("attitude"),
            "face_detected": face.get("face_detected"),
            "focus": face.get("focus"),
            "updated_at": face.get("updated_at"),
        }
    except Exception:
        return None


def _quiz_backlog_summary(db: Session, user_id: int) -> dict[str, Any]:
    try:
        from backend.quiz import review_cards as rc_mod

        return rc_mod.backlog_summary(db, user_id=user_id)
    except Exception:
        return {"due_count": 0, "total_cards": 0, "by_domain": {}, "deck_count": 0}


def _suggested_priorities(ctx: dict[str, Any]) -> list[str]:
    steps: list[str] = []
    today = ctx.get("today") or {}
    vocab = ctx.get("vocab") or {}
    quiz = ctx.get("quiz_backlog") or {}
    if quiz.get("due_count", 0) > 0:
        steps.append(f"Review {quiz['due_count']} due cards in Review Hub (/review).")
    notes = ctx.get("lecture_notes") or {}
    if notes.get("count", 0) == 0:
        steps.append("Run live captions scraper, then transcript_to_notes.bat --latest.")
    elif notes.get("count", 0) > 0 and quiz.get("total_cards", 0) == 0:
        steps.append("Generate a quiz from Lecture Notes and take it once to seed FSRS.")
    if today.get("vocab_events", 0) == 0:
        steps.append("Run one GRE vocab cycle (Read → Quiz → Report).")
    if vocab.get("due_for_review", 0) > 0:
        steps.append(f"Review {vocab['due_for_review']} due vocab words.")
    if vocab.get("low_mastery_words", 0) > 0:
        steps.append("Open Low-Mastery list and drill weak words.")
    if today.get("study_minutes", 0) < 60:
        steps.append("Block 25–50 minutes for focused study (Pomodoro).")
    if today.get("sleep_minutes", 0) < 420:
        steps.append("Protect 7+ hours of sleep tonight.")
    if (ctx.get("math") or {}).get("attempts_today", 0) == 0:
        steps.append("Complete one math practice set.")
    focus = ctx.get("focus") or {}
    if focus.get("total_distraction_minutes", 0) > 30:
        steps.append("Try Focus Mirror + Pomodoro during the next session.")
    if not steps:
        steps.append("Maintain today's rhythm — metrics look balanced.")
    return steps[:5]


def build_coach_context(db: Session, user: User, *, daily: dict[str, Any] | None = None) -> dict[str, Any]:
    from backend.math.training_log import training_stats_for_hub

    if daily is None:
        from datetime import date

        from backend.hub.services.rollup import rebuild_daily_rollup
        from backend.models import LifeDailyLog

        d = date.today()
        life = db.query(LifeDailyLog).filter(LifeDailyLog.user_id == user.id, LifeDailyLog.date == d).first()
        rollup = rebuild_daily_rollup(db, user.id, d)
        performance = "needs-improvement"
        if life and life.life_score >= 80:
            performance = "excellent"
        elif life and life.life_score >= 55:
            performance = "good"
        daily = {
            "date": d.isoformat(),
            "life_score": life.life_score if life else 0,
            "study_minutes": life.study_minutes if life else 0,
            "productive_minutes": rollup.productive_minutes,
            "sleep_minutes": rollup.sleep_minutes,
            "vocab_events": rollup.vocab_events,
            "math_attempts": rollup.math_attempts,
            "overall_performance": performance,
        }

    ctx: dict[str, Any] = {
        "project": PROJECT_OVERVIEW,
        "student": {
            "username": user.username,
            "is_admin": bool(getattr(user, "is_admin", False)),
        },
        "today": {**daily, **training_stats_for_hub(user.id)},
        "vocab": _vocab_summary(db, user.id),
        "life_last_7_days": _life_recent(db, user.id),
        "math": _math_summary(db, user.id),
        "lecture_notes": _notes_summary(db, user.id),
        "focus": _focus_summary(db, user.id),
        "plugins_enabled": _plugins_enabled(db, user.id),
        "face_tracker": _face_snapshot(),
        "quiz_backlog": _quiz_backlog_summary(db, user.id),
    }
    ctx["suggested_priorities"] = _suggested_priorities(ctx)

    from backend.hub.services.coach_knowledge import knowledge_index

    ctx["knowledge_index"] = knowledge_index(db, user.id)
    return ctx
