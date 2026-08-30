"""
Math intervention → quiz SRS bridge.

Maps recover / struggle outcomes onto existing ReviewCard SRS (binary correct).
Skips enqueue when OCR / structural confidence is too low (noise must not poison SRS).
"""

from __future__ import annotations

import hashlib
from typing import Any

from sqlalchemy.orm import Session

from backend.math.structure_verify import STRUCTURAL_SILENCE_THRESHOLD
from backend.quiz.review_cards import upsert_review_card

OCR_CONF_MIN = 0.45


def _item_id(snapshot_id: str, latex: str, topic: str) -> str:
    raw = f"{snapshot_id}|{latex}|{topic}"
    return "math_iv_" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def should_skip_srs(*, confidence: float, structural_confidence: float, tutor_silent: bool) -> bool:
    if tutor_silent:
        return True
    if confidence < OCR_CONF_MIN:
        return True
    if structural_confidence < STRUCTURAL_SILENCE_THRESHOLD:
        return True
    return False


def enqueue_math_review(
    db: Session,
    *,
    user_id: int,
    latex: str,
    topic: str = "",
    prompt: str = "",
    snapshot_id: str = "",
    correct: bool,
    confidence: float = 1.0,
    structural_confidence: float = 1.0,
    tutor_silent: bool = False,
    skill_id: str | None = None,
) -> dict[str, Any] | None:
    """
    Upsert a math review card. Returns card summary or None if skipped.

    ``topic`` / ``skill_id`` should be a skills.json node id when known
    (e.g. ``fractions_ops``); otherwise a free-text topic is fine.
    """
    latex = (latex or "").strip()
    if not latex:
        return None
    if should_skip_srs(
        confidence=confidence,
        structural_confidence=structural_confidence,
        tutor_silent=tutor_silent,
    ):
        return {"skipped": True, "reason": "low_confidence_or_silent"}

    skill = (skill_id or topic or "whiteboard").strip() or "whiteboard"
    item_id = _item_id(snapshot_id or latex, latex, skill)
    label = (prompt or latex)[:300]
    payload = {
        "id": item_id,
        "prompt": prompt or f"Re-solve: ${latex}$",
        "expected_answer": latex,
        "topic": skill,
        "skill_id": skill,
        "source": "math_intervention",
        "snapshot_id": snapshot_id,
    }
    card = upsert_review_card(
        db,
        user_id=user_id,
        domain="math",
        item_id=item_id,
        label=label,
        payload=payload,
        correct=correct,
        topic=skill[:160],
        fmt="free_text",
    )
    return {
        "skipped": False,
        "review_card_id": card.id,
        "item_key": card.item_key,
        "correct": correct,
        "topic": skill,
    }
