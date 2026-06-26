"""Review card persistence and backlog queries."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from backend.models.review_card import QuizDeck, ReviewCard
from backend.quiz import srs as srs_mod


def _item_key(domain: str, item_id: str, note_path: str = "") -> str:
    suffix = note_path.replace("\\", "/").strip()
    if suffix:
        return f"{domain}:{item_id}:{suffix}"
    return f"{domain}:{item_id}"


def upsert_review_card(
    db: Session,
    *,
    user_id: int,
    domain: str,
    item_id: str,
    label: str,
    payload: dict[str, Any],
    correct: bool,
    elapsed_ms: int = 0,
    topic: str | None = None,
    note_path: str | None = None,
    fmt: str = "mcq",
    deck_id: int | None = None,
) -> ReviewCard:
    key = _item_key(domain, item_id, note_path or "")
    row = (
        db.query(ReviewCard)
        .filter(ReviewCard.user_id == user_id, ReviewCard.item_key == key)
        .first()
    )
    if not row:
        row = ReviewCard(
            user_id=user_id,
            domain=domain,
            item_key=key,
            label=label[:300],
            topic=(topic or "")[:160] or None,
            note_path=note_path,
            format=fmt,
            payload_json=json.dumps(payload),
            srs_json=json.dumps(srs_mod.srs_to_metadata(srs_mod.SrsState())),
            deck_id=deck_id,
        )
        db.add(row)
    else:
        row.label = label[:300] or row.label
        row.payload_json = json.dumps(payload)
        if topic:
            row.topic = topic[:160]
        if note_path:
            row.note_path = note_path

    state = srs_mod.srs_from_metadata(json.loads(row.srs_json or "{}"))
    state = srs_mod.schedule_after_answer(state, correct=correct, elapsed_ms=elapsed_ms)
    row.srs_json = json.dumps(srs_mod.srs_to_metadata(state))
    row.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(row)
    return row


def card_to_quiz_item(card: ReviewCard) -> dict[str, Any]:
    payload = json.loads(card.payload_json or "{}")
    kind = payload.get("kind") or ("code" if card.format == "code" else "mcq")
    if kind == "code" or card.format == "code":
        return {
            "kind": "code",
            "id": payload.get("id") or card.item_key,
            "title": payload.get("title") or card.label,
            "prompt": payload.get("prompt") or card.label,
            "starter_code": payload.get("starter_code", "# your code\n"),
            "hint": payload.get("hint"),
            "language": payload.get("language", "python"),
            "review_card_id": card.id,
            "domain": card.domain,
        }
    if card.domain == "vocab" and payload.get("word_id"):
        return {
            "kind": "vocab",
            "id": str(payload["word_id"]),
            "word_id": int(payload["word_id"]),
            "review_card_id": card.id,
            "domain": "vocab",
        }
    if card.domain == "math":
        return {
            "kind": "math",
            "id": payload.get("id") or card.item_key,
            "prompt": payload.get("prompt") or card.label,
            "expected_answer": payload.get("expected_answer") or payload.get("answer", ""),
            "topic": payload.get("topic") or card.topic,
            "review_card_id": card.id,
            "domain": "math",
        }
    return {
        "kind": "mcq",
        "id": payload.get("id") or card.item_key,
        "question": payload.get("question") or payload.get("prompt") or card.label,
        "options": payload.get("options") or [],
        "answer_index": int(payload.get("answer_index", 0)),
        "explanation": payload.get("explanation"),
        "hint": payload.get("hint"),
        "review_card_id": card.id,
        "domain": card.domain,
    }


def list_due_cards(
    db: Session,
    *,
    user_id: int,
    limit: int = 40,
    domains: list[str] | None = None,
) -> list[ReviewCard]:
    now = datetime.now(UTC)
    rows = db.query(ReviewCard).filter(ReviewCard.user_id == user_id).all()
    due: list[ReviewCard] = []
    weak_topics = _weak_topic_labels(db, user_id)

    for row in rows:
        if domains and row.domain not in domains:
            continue
        state = srs_mod.srs_from_metadata(json.loads(row.srs_json or "{}"))
        if srs_mod.is_due(state, now=now):
            due.append(row)

    def _sort_key(card: ReviewCard) -> tuple[int, str, str]:
        topic = (card.topic or card.label or "").lower()
        boosted = 1 if any(w and w in topic for w in weak_topics) else 0
        state = srs_mod.srs_from_metadata(json.loads(card.srs_json or "{}"))
        due_s = state.due_date.isoformat() if state.due_date else ""
        return (-boosted, due_s, card.domain)

    due.sort(key=_sort_key)
    return due[:limit]


def _weak_topic_labels(db: Session, user_id: int) -> set[str]:
    try:
        from backend.models.knowledge_graph import KgNode, KgObservation
    except ImportError:
        return set()

    rows = (
        db.query(KgObservation, KgNode)
        .join(KgNode, KgObservation.node_id == KgNode.id)
        .filter(KgObservation.user_id == user_id)
        .order_by(KgObservation.timestamp.desc())
        .limit(120)
        .all()
    )
    weak: set[str] = set()
    for obs, node in rows:
        if "fail" not in (obs.interaction_type or ""):
            continue
        label = (node.tag_path or node.label or "").strip().lower()
        if label:
            weak.add(label)
            for part in label.replace("_", " ").split():
                if len(part) > 3:
                    weak.add(part)
    return weak


def weak_concepts_for_retrieval(db: Session, user_id: int, *, limit: int = 6) -> list[str]:
    """Topic labels from recent quiz failures — boosts corpus retrieval for quiz/drills."""
    return sorted(_weak_topic_labels(db, user_id))[:limit]


def backlog_summary(db: Session, *, user_id: int) -> dict[str, Any]:
    now = datetime.now(UTC)
    rows = db.query(ReviewCard).filter(ReviewCard.user_id == user_id).all()
    by_domain: dict[str, int] = {}
    due_total = 0
    next_due: datetime | None = None
    for row in rows:
        state = srs_mod.srs_from_metadata(json.loads(row.srs_json or "{}"))
        by_domain[row.domain] = by_domain.get(row.domain, 0) + 1
        if srs_mod.is_due(state, now=now):
            due_total += 1
        elif state.due_date:
            if next_due is None or state.due_date < next_due:
                next_due = state.due_date

    decks = db.query(QuizDeck).filter(QuizDeck.user_id == user_id).count()

    recommended = "sign_in"
    if due_total > 0:
        recommended = "review_due"
    elif by_domain.get("vocab", 0) == 0:
        recommended = "start_vocab"
    elif decks == 0:
        recommended = "lecture_notes"

    weak_topics = sorted(_weak_topic_labels(db, user_id))[:12]

    return {
        "total_cards": len(rows),
        "due_count": due_total,
        "by_domain": by_domain,
        "deck_count": decks,
        "next_due": next_due.isoformat() if next_due else None,
        "recommended_action": recommended,
        "weak_topics": weak_topics,
    }


def card_to_due_item(card: ReviewCard) -> dict[str, Any]:
    state = srs_mod.srs_from_metadata(json.loads(card.srs_json or "{}"))
    payload = json.loads(card.payload_json or "{}")
    return {
        "card_id": card.id,
        "domain": card.domain,
        "item_id": card.item_key.split(":")[1] if ":" in card.item_key else str(card.id),
        "label": card.label,
        "topic": card.topic,
        "mastery": state.mastery,
        "stability": round(state.stability, 1),
        "difficulty": round(state.difficulty, 1),
        "due_date": state.due_date.isoformat() if state.due_date else None,
        "format": card.format,
        "note_path": card.note_path,
        "hint": payload.get("hint") or payload.get("explanation"),
        "payload": payload,
    }


def seed_deck_cards(db: Session, *, user_id: int, deck: QuizDeck) -> int:
    items = json.loads(deck.items_json or "[]")
    count = 0
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        item_id = str(item.get("id") or f"d{deck.id}-q{i + 1}")
        label = str(item.get("question") or item.get("title") or item.get("prompt") or f"Q{i + 1}")[:300]
        fmt = "code" if item.get("starter_code") else "mcq"
        key = _item_key(deck.domain, f"deck{deck.id}-{item_id}")
        existing = (
            db.query(ReviewCard)
            .filter(ReviewCard.user_id == user_id, ReviewCard.item_key == key)
            .first()
        )
        if existing:
            continue
        row = ReviewCard(
            user_id=user_id,
            domain=deck.domain,
            item_key=key,
            label=label,
            topic=deck.topic,
            format=fmt,
            payload_json=json.dumps({**item, "id": item_id}),
            srs_json=json.dumps(srs_mod.srs_to_metadata(srs_mod.SrsState())),
            deck_id=deck.id,
        )
        db.add(row)
        count += 1
    db.commit()
    return count
