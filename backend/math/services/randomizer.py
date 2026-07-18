"""Pick practice problems — bank first, then template generator (caller)."""

import json
import random
import uuid
from typing import Any, Callable

from sqlalchemy.orm import Session

from backend.models import MathQuestion


def _row_to_problem(row: MathQuestion) -> dict[str, Any]:
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
    return _row_to_problem(random.choice(rows))


def pick_n_from_bank(
    db: Session,
    topic: str | None = None,
    n: int = 5,
    *,
    skill_id: str | None = None,
) -> list[dict[str, Any]]:
    """
    Sample up to N distinct active bank questions (without replacement).
    Optional skill_id matches tags or metadata_json.skill_id when present.
    """
    n = max(1, min(int(n or 5), 50))
    q = db.query(MathQuestion).filter(MathQuestion.is_active == True)
    if topic:
        q = q.filter(MathQuestion.topic == topic)
    rows = list(q.all())
    if skill_id:
        sid = skill_id.strip().lower()
        filtered: list[MathQuestion] = []
        for row in rows:
            tags = [str(t).lower() for t in json.loads(row.tags_json or "[]")]
            meta = json.loads(row.metadata_json or "{}") if row.metadata_json else {}
            meta_skill = str(meta.get("skill_id") or "").lower()
            if sid in tags or meta_skill == sid:
                filtered.append(row)
        rows = filtered or rows
    if not rows:
        return []
    if len(rows) <= n:
        chosen = rows[:]
        random.shuffle(chosen)
    else:
        chosen = random.sample(rows, n)
    return [_row_to_problem(r) for r in chosen]


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
