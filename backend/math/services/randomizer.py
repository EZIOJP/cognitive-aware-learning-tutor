"""Pick practice problems — bank first, then template generator (caller)."""

import json
import random
import uuid
from typing import Any, Callable

from sqlalchemy.orm import Session

from backend.models import MathQuestion


def pick_from_bank(db: Session, topic: str | None = None) -> dict[str, Any] | None:
    """
    Random active question from imported bank.
    Returns API-shaped problem dict or None if bank empty for topic.
    """
    q = db.query(MathQuestion).filter(MathQuestion.is_active == True)
    if topic:
        q = q.filter(MathQuestion.topic == topic)
    rows = q.all()
    if not rows:
        return None

    row = random.choice(rows)
    tags = json.loads(row.tags_json or "[]")
    return {
        "generated_id": str(uuid.uuid4()),
        "question_id": row.id,
        "template_id": None,
        "title": row.topic,
        "topic": row.topic,
        "operation": "imported",
        "prompt": row.prompt,
        "latex": row.latex or "",
        "expected_answer": row.expected_answer,
        "points": 10,
        "explanation": row.explanation or "",
        "sympy_enabled": False,
        "source": "question_bank",
        "difficulty": row.difficulty,
        "tags": tags,
    }


def pick_practice_problem(
    db: Session,
    topic: str | None,
    template_fallback: Callable[[], dict[str, Any]],
) -> dict[str, Any]:
    """Bank randomizer with template generator fallback."""
    from_bank = pick_from_bank(db, topic)
    if from_bank:
        return from_bank
    problem = template_fallback()
    problem["source"] = problem.get("source", "template")
    problem["question_id"] = None
    return problem
