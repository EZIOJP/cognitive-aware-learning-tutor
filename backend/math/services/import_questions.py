import json
from typing import Any

from sqlalchemy.orm import Session

from backend.math.schemas import MathImportBundle, MathImportResult, MathQuestionIn
from backend.models import MathQuestion


def _normalize_row(raw: dict[str, Any], default_topic: str | None) -> MathQuestionIn | None:
    if not raw:
        return None
    merged = dict(raw)
    if "question" in merged and "prompt" not in merged:
        merged["prompt"] = merged["question"]
    if "answer" in merged and "expected_answer" not in merged:
        merged["expected_answer"] = merged["answer"]
    try:
        item = MathQuestionIn.model_validate(merged)
    except Exception:
        return None
    if not item.prompt or not item.expected_answer:
        return None
    if not item.topic and default_topic:
        item.topic = default_topic
    if not item.topic:
        return None
    return item


def parse_import_payload(data: Any) -> tuple[list[MathQuestionIn], list[str]]:
    """Accept bundle object, bare list, or { questions: [...] }."""
    errors: list[str] = []
    items: list[MathQuestionIn] = []
    default_topic: str | None = None

    if isinstance(data, list):
        for i, row in enumerate(data):
            if not isinstance(row, dict):
                errors.append(f"Row {i}: expected object")
                continue
            parsed = _normalize_row(row, row.get("topic"))
            if parsed:
                items.append(parsed)
            else:
                errors.append(f"Row {i}: missing topic, prompt, or expected_answer")
        return items, errors

    if not isinstance(data, dict):
        return [], ["Root must be a JSON object or array"]

    default_topic = data.get("topic")
    bundle = MathImportBundle.model_validate(data)
    default_topic = bundle.topic or default_topic
    for i, q in enumerate(bundle.questions):
        parsed = _normalize_row(q.model_dump(by_alias=True), default_topic)
        if parsed:
            items.append(parsed)
        else:
            errors.append(f"questions[{i}]: invalid or incomplete")
    return items, errors


def upsert_questions(db: Session, items: list[MathQuestionIn], *, default_source: str | None = None) -> MathImportResult:
    inserted = updated = skipped = 0
    errors: list[str] = []

    for item in items:
        topic = (item.topic or "").strip()
        prompt = (item.prompt or "").strip()
        expected = (item.expected_answer or "").strip()
        if not topic or not prompt or not expected:
            skipped += 1
            continue

        row: MathQuestion | None = None
        if item.external_id:
            row = (
                db.query(MathQuestion)
                .filter(MathQuestion.topic == topic, MathQuestion.external_id == item.external_id)
                .first()
            )

        tags_json = json.dumps(item.tags or [])
        meta_json = json.dumps(item.metadata or {}) if item.metadata else None
        source = item.source or default_source or "import"

        if row:
            row.prompt = prompt
            row.expected_answer = expected
            row.explanation = item.explanation
            row.latex = item.latex
            row.difficulty = item.difficulty
            row.answer_format = item.answer_format
            row.tags_json = tags_json
            row.metadata_json = meta_json
            row.source = source
            row.is_active = item.is_active
            updated += 1
        else:
            db.add(
                MathQuestion(
                    external_id=item.external_id,
                    topic=topic,
                    prompt=prompt,
                    expected_answer=expected,
                    explanation=item.explanation,
                    latex=item.latex,
                    difficulty=item.difficulty,
                    answer_format=item.answer_format,
                    tags_json=tags_json,
                    metadata_json=meta_json,
                    source=source,
                    is_active=item.is_active,
                )
            )
            inserted += 1

    db.commit()
    total = db.query(MathQuestion).filter(MathQuestion.is_active == True).count()
    return MathImportResult(
        inserted=inserted,
        updated=updated,
        skipped=skipped,
        errors=errors,
        total_in_bank=total,
    )
