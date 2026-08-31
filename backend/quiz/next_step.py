"""Structured next_step for Study Loop / quiz complete (not insights coach tips)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from backend.models.review_card import QuizDeck, ReviewCard
from backend.quiz import srs as srs_mod


def compute_next_step(db: Session, *, user_id: int | None) -> dict[str, Any]:
    """
    Priority: review due → math drill (available/in_progress node) → notes/lecture → vocab.
    """
    if user_id is None:
        return {
            "action": "sign_in",
            "label": "Sign in",
            "to": "/profile",
            "reason": "Sync quizzes and spaced repetition.",
            "due_count": 0,
        }

    now = datetime.now(UTC)
    rows = db.query(ReviewCard).filter(ReviewCard.user_id == user_id).all()
    due_total = 0
    by_domain: dict[str, int] = {}
    for row in rows:
        by_domain[row.domain] = by_domain.get(row.domain, 0) + 1
        state = srs_mod.srs_from_metadata(json.loads(row.srs_json or "{}"))
        if srs_mod.is_due(state, now=now):
            due_total += 1

    if due_total > 0:
        return {
            "action": "review_due",
            "label": f"Review {due_total} due",
            "to": "/review?tab=due",
            "reason": "Protect retention — clear due cards first.",
            "due_count": due_total,
        }

    try:
        from backend.math.skills import next_available_node

        nxt = next_available_node(db, user_id=user_id)
        if nxt:
            title = str(nxt.get("title") or nxt["id"])
            return {
                "action": "math_drill",
                "label": f"Continue: {title}",
                "to": f"/review?tab=start&math_node={nxt['id']}",
                "reason": "Practice the next unlocked math skill.",
                "due_count": 0,
                "meta": {"node_id": nxt["id"], "layer": nxt.get("layer"), "status": nxt.get("status")},
            }
    except Exception:
        pass

    decks = db.query(QuizDeck).filter(QuizDeck.user_id == user_id).count()
    study_cards = by_domain.get("study", 0)
    if study_cards == 0 and decks == 0:
        return {
            "action": "lecture_notes",
            "label": "Study from notes",
            "to": "/lecture-notes",
            "reason": "Generate a notes quiz to seed your review queue.",
            "due_count": 0,
        }
    if study_cards == 0:
        return {
            "action": "notes_quiz",
            "label": "Quiz a lecture",
            "to": "/lecture-notes",
            "reason": "Turn lecture notes into a quiz.",
            "due_count": 0,
        }

    return {
        "action": "start_vocab",
        "label": "Practice GRE vocab",
        "to": "/gre-vocab/read",
        "reason": "Safe fallback — build vocab review cards.",
        "due_count": 0,
    }
