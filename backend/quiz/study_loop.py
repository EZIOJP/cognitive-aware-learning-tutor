"""Study Loop session gate: read cards → content-inspected practice → FSRS quiz."""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from backend.models.study_loop import StudyLoopSession
from backend.quiz import handler
from backend.quiz.read_cards import list_read_cards
from backend.transcripts.note_topics import canonicalize_topic_id

_VOCAB_GROUP = re.compile(r"^vocab\.group\.(\d+)$", re.I)


@dataclass
class PracticeRoute:
    domain: str  # vocab | math | study | code | mixed
    config: dict[str, Any] = field(default_factory=dict)
    reason: str = ""


def list_bank_items_for_tag(tag: str, *, kinds: list[str] | None = None) -> list[dict]:
    from backend.quiz.question_crud import list_questions

    items = list_questions(tag=tag, kind=None)
    if kinds:
        want = {str(k).strip().lower() for k in kinds if str(k).strip()}
        items = [
            it
            for it in items
            if (it.get("content_kind") or it.get("kind") or "").lower() in want
        ]
    return items


def math_generators_for_tag(tag: str) -> list:
    """Thin wrapper; empty for non-MT tags or when no recipes exist."""
    raw = (tag or "").strip()
    canon = (canonicalize_topic_id(raw) or raw).upper()
    if not canon.startswith("MT"):
        return []
    try:
        from backend.quiz import math_generators as mg

        return list(mg.recipes_for_note_topic(canon))
    except Exception:
        return []


def resolve_practice_route(tag: str, *, count: int = 5, kinds: list[str] | None = None) -> PracticeRoute:
    tid = (tag or "").strip()
    m = _VOCAB_GROUP.match(tid)
    if m:
        return PracticeRoute("vocab", {"group_number": int(m.group(1)), "count": count}, "vocab_group")

    items = list_bank_items_for_tag(tid, kinds=kinds)
    buckets: dict[str, int] = {}
    for it in items:
        k = (it.get("content_kind") or it.get("kind") or "").lower()
        if k in ("mcq", "study"):
            b = "mcq"
        elif k == "coding_mcq":
            b = "coding_mcq"
        elif k in ("coding", "code"):
            b = "coding"
        elif k == "math":
            b = "math"
        else:
            b = "other"
        buckets[b] = buckets.get(b, 0) + 1

    has_math_gen = bool(math_generators_for_tag(tid))
    mathish = buckets.get("math", 0) > 0 or has_math_gen
    coding = buckets.get("coding", 0) > 0
    mcq = buckets.get("mcq", 0) + buckets.get("coding_mcq", 0) > 0

    if mathish and not coding and not mcq:
        return PracticeRoute("math", {"note_topic_id": tid, "count": count}, "math_only")
    if coding and not mathish and not mcq:
        return PracticeRoute("code", {"items": items[:count], "auto_generate": False}, "coding_only")
    if mcq and not mathish and not coding:
        return PracticeRoute("study", {"items": items[:count], "auto_generate": False}, "mcq_only")
    if mathish or coding or mcq:
        if not items and mathish:
            return PracticeRoute("math", {"note_topic_id": tid, "count": count}, "math_gen_fill")
        return PracticeRoute("mixed", {"items": items[:count], "auto_generate": False}, "mixed_kinds")
    raise ValueError("no_practice_content")


def _card_ids(cards: list[dict[str, Any]]) -> list[str]:
    out: list[str] = []
    for card in cards:
        cid = str(card.get("card_id") or "").strip()
        if cid:
            out.append(cid)
    return out


def _parse_card_ids(raw: str | None) -> list[str]:
    try:
        data = json.loads(raw or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    return [str(x) for x in data if str(x).strip()]


def session_to_dict(row: StudyLoopSession) -> dict[str, Any]:
    created = row.created_at.isoformat() if row.created_at else None
    updated = row.updated_at.isoformat() if row.updated_at else None
    return {
        "session_id": row.session_id,
        "user_id": row.user_id,
        "tag": row.tag,
        "read_completed": bool(row.read_completed),
        "read_card_ids": _parse_card_ids(row.read_card_ids_json),
        "practice_quiz_session_id": row.practice_quiz_session_id,
        "created_at": created,
        "updated_at": updated,
    }


def _get_row(db: Session, *, user_id: int, session_id: str) -> StudyLoopSession:
    row = (
        db.query(StudyLoopSession)
        .filter(StudyLoopSession.session_id == session_id, StudyLoopSession.user_id == user_id)
        .one_or_none()
    )
    if row is None:
        raise ValueError("session_not_found")
    return row


def create_loop_session(*, user_id: int, tag: str, db: Session) -> dict:
    tid = (tag or "").strip()
    if not tid:
        raise ValueError("tag is required")
    cards = list_read_cards(tag=tid)
    card_ids = _card_ids(cards)
    read_completed = len(cards) == 0
    now = datetime.now(UTC)
    row = StudyLoopSession(
        session_id=str(uuid.uuid4()),
        user_id=int(user_id),
        tag=tid,
        read_completed=read_completed,
        read_card_ids_json=json.dumps(card_ids),
        practice_quiz_session_id=None,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return session_to_dict(row)


def mark_read(*, user_id: int, session_id: str, db: Session) -> dict:
    row = _get_row(db, user_id=user_id, session_id=session_id)
    row.read_completed = True
    row.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(row)
    return session_to_dict(row)


def get_session(*, user_id: int, session_id: str, db: Session) -> dict:
    return session_to_dict(_get_row(db, user_id=user_id, session_id=session_id))


def start_practice(
    *,
    db: Session,
    user: Any,
    session_id: str,
    count: int = 5,
    kinds: list[str] | None = None,
) -> dict:
    q = db.query(StudyLoopSession).filter(StudyLoopSession.session_id == session_id)
    if user is not None and getattr(user, "id", None) is not None:
        q = q.filter(StudyLoopSession.user_id == user.id)
    row = q.one_or_none()
    if row is None:
        raise ValueError("session_not_found")
    if not row.read_completed:
        raise ValueError("read_required")
    route = resolve_practice_route(row.tag, count=count, kinds=kinds)
    quiz = handler.start_session(db, user=user, domain=route.domain, config=route.config)
    practice_id = str((quiz or {}).get("session_id") or "") or None
    row.practice_quiz_session_id = practice_id
    row.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(row)
    payload = session_to_dict(row)
    payload["domain"] = route.domain
    payload["config"] = route.config
    payload["reason"] = route.reason
    payload["quiz"] = quiz
    return payload
