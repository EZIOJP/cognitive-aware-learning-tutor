from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from backend.models.review_card import ReviewCard
from backend.quiz import srs as srs_mod


def seed_mapped_questions(
    db: Session,
    *,
    user_id: int,
    packs: list[dict[str, Any]],
) -> int:
    """One ReviewCard per question (full MT* tags in payload)."""
    seeded = 0
    for pack in packs:
        topic = pack.get("topic") or {}
        topic_id = str(topic.get("topic_id") or "")
        for q in pack.get("questions") or []:
            qid = str(q.get("id") or "").strip()
            if not qid:
                continue
            item_key = f"math:{qid}"[:200]
            label = (str(q.get("problem") or qid)[:300]) or qid
            payload = {
                "kind": "math_question",
                "id": qid,
                "topic_id": topic_id,
                "source": q.get("source"),
                "source_id": q.get("source_id"),
                "problem": q.get("problem"),
                "answer": q.get("answer"),
                "answer_format": q.get("answer_format") or "open",
                "tags": list(q.get("tags") or []),
                "note_topic_ids": list(topic.get("note_topic_ids") or []),
            }
            existing = (
                db.query(ReviewCard)
                .filter(ReviewCard.user_id == user_id, ReviewCard.item_key == item_key)
                .first()
            )
            if existing:
                existing.label = label
                existing.payload_json = json.dumps(payload)
                existing.topic = (topic_id or None)
                existing.domain = "math"
                existing.format = "mcq"
                seeded += 1
                continue
            row = ReviewCard(
                user_id=user_id,
                domain="math",
                item_key=item_key,
                label=label,
                topic=(topic_id or None),
                note_path=None,
                format="mcq",
                payload_json=json.dumps(payload),
                srs_json=json.dumps(srs_mod.srs_to_metadata(srs_mod.SrsState())),
                deck_id=None,
            )
            db.add(row)
            seeded += 1
    db.commit()
    return seeded
