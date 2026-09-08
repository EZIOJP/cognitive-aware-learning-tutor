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
    """Thin wrapper; empty for non-MT tags or when no recipes/drills exist."""
    raw = (tag or "").strip()
    try:
        from backend.quiz import math_core as mc
        from backend.quiz import math_core_drills as mcd

        canon = mc.canonical_tag(raw) or (canonicalize_topic_id(raw) or raw).upper()
        if mcd.supports_worksheet_drills(canon):
            return ["math_core_drill"]  # truthy sentinel for route mathish
    except Exception:
        pass
    canon = (canonicalize_topic_id(raw) or raw).upper()
    if not canon.startswith("MT"):
        return []
    try:
        from backend.quiz import math_generators as mg

        return list(mg.recipes_for_note_topic(canon))
    except Exception:
        return []


def _vocab_word_ids_for_free_tag(tag: str) -> list[int]:
    """Word ids whose tags[] include this free tag (case-insensitive)."""
    key = (tag or "").strip().lower()
    if not key or _VOCAB_GROUP.match(tag or ""):
        return []
    try:
        from backend.quiz import tag_index as ti

        words = ti._load_vocab_words()
    except Exception:
        return []
    out: list[int] = []
    for w in words or []:
        tags = w.get("tags") or []
        if not isinstance(tags, list):
            continue
        if any(str(t).strip().lower() == key for t in tags):
            try:
                out.append(int(w["id"]))
            except (KeyError, TypeError, ValueError):
                continue
    return out


def resolve_practice_route(tag: str, *, count: int = 5, kinds: list[str] | None = None) -> PracticeRoute:
    from backend.quiz import math_core as mc

    # Keep the user's topic — do not silently remap worksheets to MT1-T01.
    tid = mc.canonical_tag((tag or "").strip()) or (tag or "").strip()
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
        cfg: dict[str, Any] = {"note_topic_id": tid, "count": count}
        try:
            from backend.quiz import math_core_drills as mcd

            if mcd.supports_worksheet_drills(tid):
                cfg["math_core_drill"] = True
        except Exception:
            pass
        return PracticeRoute("math", cfg, "math_only")
    if coding and not mathish and not mcq:
        return PracticeRoute("code", {"items": items[:count], "auto_generate": False}, "coding_only")
    if mcq and not mathish and not coding:
        return PracticeRoute("study", {"items": items[:count], "auto_generate": False}, "mcq_only")
    if mathish or coding or mcq:
        if not items and mathish:
            return PracticeRoute("math", {"note_topic_id": tid, "count": count}, "math_gen_fill")
        return PracticeRoute("mixed", {"items": items[:count], "auto_generate": False}, "mixed_kinds")

    # Free vocab tags (word.tags[]) with no bank/math content → vocab drill.
    word_ids = _vocab_word_ids_for_free_tag(tid)
    if word_ids:
        return PracticeRoute(
            "vocab",
            {"word_ids": word_ids[: max(count * 4, count)], "count": count},
            "vocab_free_tag",
        )
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
    from backend.quiz import math_core as mc

    if mc.is_math_core_tag(tid):
        # Daily Math Core step: full Shorts stack (warm-up + worksheets) in learn order.
        cards: list[dict[str, Any]] = []
        seen: set[str] = set()
        for t in mc.MATH_CORE_READ_TAGS:
            for c in list_read_cards(tag=t):
                cid = str(c.get("card_id") or "")
                if cid and cid not in seen:
                    cards.append(c)
                    seen.add(cid)
    else:
        # Single-topic focus (incl. one MT0 worksheet) — only that tag's flash cards.
        cards = list_read_cards(tag=tid)
        if not cards:
            canon = mc.canonical_tag(tid)
            if canon and canon != tid.upper():
                cards = list_read_cards(tag=canon)
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
    from backend.quiz import math_core as mc

    # Practice the focused tag only (no silent jump to another topic).
    topic = mc.canonical_tag(row.tag) or (row.tag or "").strip()
    practice_count = mc.practice_count_for_tag(topic, default=count)
    route = resolve_practice_route(topic, count=practice_count, kinds=kinds)
    config = dict(route.config)
    difficulty_level = None
    prefer: list[str] = []
    if route.domain in ("math", "mixed") and topic.upper().startswith("MT"):
        from backend.quiz import topic_level as tl

        uid = int(user.id)
        difficulty_level = tl.effective_level(uid, topic)
        config["difficulty_level"] = difficulty_level
        config["note_topic_id"] = topic
        config["learning_tag"] = (row.tag or "").strip() or topic
        config["allow_generators"] = tl.allow_generators(difficulty_level)
        if difficulty_level == "easy":
            prefer = tl.curriculum_prefer_ids(topic, level=difficulty_level)
            if prefer and not config.get("prefer_topic_ids"):
                config["prefer_topic_ids"] = prefer
        # Math-only route: keep domain math so handler applies level filter.
        if route.domain == "mixed" and config.get("items"):
            config = {
                "note_topic_id": topic,
                "learning_tag": (row.tag or "").strip() or topic,
                "count": practice_count,
                "difficulty_level": difficulty_level,
                "allow_generators": tl.allow_generators(difficulty_level),
                "prefer_topic_ids": prefer if difficulty_level == "easy" else [],
            }
            route = PracticeRoute("math", config, "math_level_gate")
        else:
            route = PracticeRoute(route.domain, config, route.reason + "+level")
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
    payload["difficulty_level"] = difficulty_level
    return payload
