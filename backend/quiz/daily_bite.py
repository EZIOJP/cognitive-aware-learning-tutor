"""Daily bite: freeze top-2 eligible tags, sequential B / stub-gated C."""

from __future__ import annotations

import json
import logging
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from backend.models.review_card import ReviewCard
from backend.models.study_loop import StudyLoopDay, StudyLoopSession
from backend.quiz import importance as imp
from backend.quiz import math_core as mc
from backend.quiz import srs as srs_mod
from backend.quiz import study_loop as sl
from backend.quiz import topic_stub_flags as stubs
from backend.quiz.read_cards import list_read_cards
from backend.quiz.tag_index import list_tags

logger = logging.getLogger(__name__)

N_TAGS = 2
PRACTICE_COUNT = 15


def practice_count(tag: str) -> int:
    items = sl.list_bank_items_for_tag(tag)
    n = len(items)
    if sl.math_generators_for_tag(tag):
        n = max(n, 1)
    if n > 0:
        return n
    try:
        sl.resolve_practice_route(tag, count=1)
        return 1
    except ValueError:
        return 0


def _tag_score(
    tag: str,
    cards: list[ReviewCard],
    store: dict[str, Any],
) -> tuple[float, int, str]:
    i = imp.importance_for(tag, store)
    max_d = 0
    owes_n = 0
    for card in cards:
        payload = json.loads(card.payload_json or "{}")
        if not imp.card_linked_to_tag(payload, card.topic, tag):
            continue
        state = srs_mod.srs_from_metadata(json.loads(card.srs_json or "{}"))
        due = None
        if state.due_date is not None:
            due = state.due_date.isoformat()
        d = imp.days_overdue(due, owes=int(state.owes_corrects or 0))
        max_d = max(max_d, d)
        if int(state.owes_corrects or 0) > 0:
            owes_n += 1
    score = i * (1 + max_d)
    return (-score, -owes_n, tag)


def eligible_tags(
    db: Session,
    *,
    user_id: int,
    tag_ids: list[str] | None = None,
) -> list[str]:
    ids = tag_ids if tag_ids is not None else [str(t["id"]) for t in list_tags()]
    cards = db.query(ReviewCard).filter(ReviewCard.user_id == user_id).all()
    store = imp.load_store()
    out: list[str] = []
    for tid in ids:
        if practice_count(tid) <= 0:
            continue
        prog = imp.progress_for_tag(cards, tid, store)
        if prog["mastered"]:
            continue
        out.append(tid)
    return out


def rank_tags(db: Session, *, user_id: int, tags: list[str]) -> list[str]:
    cards = db.query(ReviewCard).filter(ReviewCard.user_id == user_id).all()
    store = imp.load_store()
    return sorted(tags, key=lambda t: _tag_score(t, cards, store))


def _mode_for(tags: list[str]) -> str:
    if not tags:
        return "B"
    # Math Core needs its own 20Q floor — never fold into a Mode-C bundle.
    if any(mc.is_math_core_tag(t) for t in tags):
        return "B"
    stub_store = stubs.load_store()
    if all(not stubs.is_stub(t, stub_store) for t in tags):
        return "C"
    return "B"


def _payload(row: StudyLoopDay) -> dict[str, Any]:
    try:
        data = json.loads(row.payload_json or "{}")
    except json.JSONDecodeError:
        data = {}
    if not isinstance(data, dict):
        data = {}
    data.setdefault("steps", [])
    return data


def _save_payload(db: Session, row: StudyLoopDay, payload: dict[str, Any]) -> None:
    row.payload_json = json.dumps(payload)
    db.commit()
    db.refresh(row)


def _quiz_attempted_ids(db: Session, *, user_id: int, quiz_session_id: str | None) -> set[str]:
    if not quiz_session_id:
        return set()
    from backend.quiz.store import load_global_session

    sess = load_global_session(db, quiz_session_id, user_id)
    if not sess:
        from backend.vocab.quiz_store import get_quiz_session

        vs = get_quiz_session(db, quiz_session_id, user_id)
        attempts = (vs or {}).get("attempts") or []
        return {str(a.get("item_id") or "") for a in attempts if a.get("item_id")}
    return {str(a.get("item_id") or "") for a in (sess.get("attempts") or []) if a.get("item_id")}


def _step_done(db: Session, *, user_id: int, step: dict[str, Any]) -> bool:
    sid = str(step.get("loop_session_id") or "")
    if not sid:
        return False
    row = (
        db.query(StudyLoopSession)
        .filter(StudyLoopSession.session_id == sid, StudyLoopSession.user_id == user_id)
        .one_or_none()
    )
    if row is None or not row.read_completed:
        return False
    gated = [str(x) for x in (step.get("gated_ids") or []) if str(x)]
    if not gated:
        return False
    attempted = _quiz_attempted_ids(db, user_id=user_id, quiz_session_id=step.get("quiz_session_id"))
    return all(gid in attempted for gid in gated)


def evaluate_state(db: Session, row: StudyLoopDay) -> str:
    tags = json.loads(row.tags_json or "[]")
    if not tags:
        return "empty"
    payload = _payload(row)
    steps = payload.get("steps") or []
    if row.mode == "C":
        if not any(s.get("loop_session_id") for s in steps):
            return "ready"
        reads_ok = True
        for s in steps:
            sid = str(s.get("loop_session_id") or "")
            if not sid:
                reads_ok = False
                break
            r = (
                db.query(StudyLoopSession)
                .filter(StudyLoopSession.session_id == sid, StudyLoopSession.user_id == row.user_id)
                .one_or_none()
            )
            if r is None or not r.read_completed:
                reads_ok = False
                break
        gated = [str(x) for x in (payload.get("bundle_gated_ids") or [])]
        if reads_ok and gated:
            attempted = _quiz_attempted_ids(
                db, user_id=row.user_id, quiz_session_id=payload.get("bundle_quiz_id")
            )
            if all(g in attempted for g in gated):
                return "done"
        return "in_progress"
    if not steps:
        return "ready"
    if all(_step_done(db, user_id=row.user_id, step=s) for s in steps):
        return "done"
    if any(s.get("loop_session_id") for s in steps):
        return "in_progress"
    return "ready"


def current_step_index(db: Session, row: StudyLoopDay) -> int:
    payload = _payload(row)
    steps = payload.get("steps") or []
    for i, step in enumerate(steps):
        if not _step_done(db, user_id=row.user_id, step=step):
            return i
    return max(0, len(steps) - 1)


def freeze_today(
    db: Session,
    *,
    user_id: int,
    today: date | None = None,
    tag_ids: list[str] | None = None,
) -> StudyLoopDay:
    day = (today or date.today()).isoformat()
    row = (
        db.query(StudyLoopDay)
        .filter(StudyLoopDay.user_id == user_id, StudyLoopDay.day == day)
        .one_or_none()
    )
    if row is not None:
        return row
    try:
        stubs.backfill_from_read_cards(list_read_cards())
    except OSError as exc:
        # Stub flags file may be briefly locked on Windows; Daily Learn must still freeze.
        logger.warning("topic stub backfill skipped: %s", exc)
    cand = eligible_tags(db, user_id=user_id, tag_ids=tag_ids)
    ranked = rank_tags(db, user_id=user_id, tags=cand)
    core = mc.MATH_CORE_TAG
    ordered: list[str] = []
    # Always lead with Math Core when generators/bank exist (daily must).
    if practice_count(core) > 0:
        ordered.append(core)
    for t in ranked:
        if (t or "").strip().upper() == core.upper():
            continue
        ordered.append(t)
        if len(ordered) >= (1 + N_TAGS if ordered and ordered[0].upper() == core.upper() else N_TAGS):
            # When core is first: core + N_TAGS others. Else: N_TAGS only.
            break
    if ordered and ordered[0].upper() == core.upper():
        ordered = ordered[: 1 + N_TAGS]
    else:
        ordered = ordered[:N_TAGS]
    mode = _mode_for(ordered)
    steps = [
        {
            "tag": t,
            "loop_session_id": None,
            "quiz_session_id": None,
            "gated_ids": [],
            "kind": "mathcore" if (t or "").strip().upper() == core.upper() else "bite",
            "label": mc.label_for_tag(t),
        }
        for t in ordered
    ]
    row = StudyLoopDay(
        user_id=user_id,
        day=day,
        tags_json=json.dumps(ordered),
        mode=mode,
        payload_json=json.dumps({"steps": steps, "has_mathcore": bool(ordered and ordered[0].upper() == core.upper())}),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def today_payload(db: Session, *, user_id: int, today: date | None = None) -> dict[str, Any]:
    row = freeze_today(db, user_id=user_id, today=today)
    tags = json.loads(row.tags_json or "[]")
    state = evaluate_state(db, row)
    payload = _payload(row)
    idx = current_step_index(db, row) if tags else 0
    empty_reason = None
    if not tags:
        empty_reason = "no_candidates"
    stub_store = stubs.load_store()
    return {
        "day": row.day,
        "tags": tags,
        "mode": row.mode,
        "state": state,
        "current_step": idx,
        "current_tag": tags[idx] if tags else None,
        "empty_reason": empty_reason,
        "stub_flags": {t: stubs.is_stub(t, stub_store) for t in tags},
        "steps": payload.get("steps") or [],
        "has_mathcore": bool(payload.get("has_mathcore"))
        or any(mc.is_math_core_tag(t) for t in tags),
    }


def bite_unfinished(db: Session, *, user_id: int, today: date | None = None) -> bool:
    """True when we should keep morning.next=study.

    Must stay cheap: distraction-gate polls this often. Never call ``eligible_tags``
    (full bank scan) here — freeze on Start / today_payload decides empty.
    """
    day = (today or date.today()).isoformat()
    row = (
        db.query(StudyLoopDay)
        .filter(StudyLoopDay.user_id == user_id, StudyLoopDay.day == day)
        .one_or_none()
    )
    if row is None:
        # Prefer study until freeze proves empty (avoids multi-minute gate hangs).
        return True
    return evaluate_state(db, row) not in ("done", "empty")


def start_today(
    db: Session,
    *,
    user: Any,
    today: date | None = None,
    mark_read: bool = False,
) -> dict[str, Any]:
    row = freeze_today(db, user_id=user.id, today=today)
    tags = json.loads(row.tags_json or "[]")
    if not tags:
        raise ValueError("no_candidates")
    payload = _payload(row)
    steps: list[dict[str, Any]] = payload.get("steps") or []
    while len(steps) < len(tags):
        steps.append({"tag": tags[len(steps)], "loop_session_id": None, "quiz_session_id": None, "gated_ids": []})

    if row.mode == "C":
        return _start_c(
            db, user=user, row=row, tags=tags, payload=payload, steps=steps, mark_read=mark_read
        )

    idx = current_step_index(db, row)
    step = steps[idx]
    tag = str(step.get("tag") or tags[idx])
    if not step.get("loop_session_id"):
        sess = sl.create_loop_session(user_id=user.id, tag=tag, db=db)
        step["loop_session_id"] = sess["session_id"]
        steps[idx] = step
        payload["steps"] = steps
        _save_payload(db, row, payload)
    loop_id = str(step["loop_session_id"])
    if mark_read:
        sl.mark_read(user_id=user.id, session_id=loop_id, db=db)
    loop_row = sl.get_session(user_id=user.id, session_id=loop_id, db=db)
    cards = list_read_cards(tag=tag)
    if (tag or "").strip().upper() == mc.MATH_CORE_TAG:
        # Worksheet companions (powers / squares / cubes cards).
        seen = {str(c.get("card_id") or "") for c in cards}
        for extra in mc.MATH_CORE_READ_TAGS:
            if (extra or "").strip().upper() == mc.MATH_CORE_TAG.upper():
                continue
            for c in list_read_cards(tag=extra):
                cid = str(c.get("card_id") or "")
                if cid and cid not in seen:
                    cards.append(c)
                    seen.add(cid)
    out = {
        **today_payload(db, user_id=user.id, today=today),
        "loop_session_id": loop_id,
        "read_completed": bool(loop_row.get("read_completed")),
        "read_cards": cards,
        "quiz": None,
        "step_kind": step.get("kind") or ("mathcore" if mc.is_math_core_tag(tag) else "bite"),
        "step_label": step.get("label") or mc.label_for_tag(tag),
        "practice_target": mc.practice_count_for_tag(tag, default=PRACTICE_COUNT),
        "encourage_more": mc.is_math_core_tag(tag),
        "difficulty_level": None,
    }
    if (tag or "").strip().upper().startswith("MT"):
        from backend.quiz import topic_level as tl

        out["difficulty_level"] = tl.effective_level(int(user.id), tag)
    if not loop_row.get("read_completed"):
        return out
    want_n = mc.practice_count_for_tag(tag, default=PRACTICE_COUNT)
    if not step.get("quiz_session_id"):
        practice = sl.start_practice(db=db, user=user, session_id=loop_id, count=want_n)
        quiz = practice.get("quiz") or {}
        step["quiz_session_id"] = practice.get("practice_quiz_session_id") or quiz.get("session_id")
        gated = _gated_ids_from_practice(
            db, user_id=user.id, quiz_session_id=step["quiz_session_id"], limit=want_n
        )
        step["gated_ids"] = gated
        steps[idx] = step
        payload["steps"] = steps
        _save_payload(db, row, payload)
        out["quiz"] = quiz
        out["read_completed"] = True
        out["difficulty_level"] = practice.get("difficulty_level") or out["difficulty_level"]
        return {
            **out,
            **today_payload(db, user_id=user.id, today=today),
            "quiz": quiz,
            "loop_session_id": loop_id,
            "practice_target": want_n,
            "encourage_more": mc.is_math_core_tag(tag),
            "step_kind": out["step_kind"],
            "step_label": out["step_label"],
            "difficulty_level": out["difficulty_level"],
        }
    from backend.quiz.handler import get_question

    q = get_question(db, user=user, session_id=str(step["quiz_session_id"]))
    out["quiz"] = {"session_id": step["quiz_session_id"], "question": q}
    return out


def _gated_ids_from_practice(
    db: Session, *, user_id: int, quiz_session_id: str | None, limit: int | None = None
) -> list[str]:
    if not quiz_session_id:
        return []
    from backend.quiz.store import load_global_session

    sess = load_global_session(db, str(quiz_session_id), user_id)
    if not sess:
        return []
    items = (sess.get("payload") or {}).get("items") or []
    ids: list[str] = []
    for it in items:
        iid = str(it.get("id") or it.get("_card_item_id") or "")
        if iid and "-recycle" not in iid and "-retry" not in iid:
            ids.append(iid)
    cap = limit if limit is not None else PRACTICE_COUNT
    return ids[:cap]


def _start_c(
    db: Session,
    *,
    user: Any,
    row: StudyLoopDay,
    tags: list[str],
    payload: dict[str, Any],
    steps: list[dict[str, Any]],
    mark_read: bool = False,
) -> dict[str, Any]:
    cards: list[dict[str, Any]] = []
    for i, tag in enumerate(tags):
        step = steps[i]
        if not step.get("loop_session_id"):
            sess = sl.create_loop_session(user_id=user.id, tag=tag, db=db)
            step["loop_session_id"] = sess["session_id"]
        loop_row = sl.get_session(user_id=user.id, session_id=str(step["loop_session_id"]), db=db)
        cards.extend(list_read_cards(tag=tag))
        steps[i] = step
    if mark_read:
        for step in steps:
            sl.mark_read(user_id=user.id, session_id=str(step["loop_session_id"]), db=db)
    payload["steps"] = steps
    _save_payload(db, row, payload)
    unread = []
    for step in steps:
        lr = sl.get_session(user_id=user.id, session_id=str(step["loop_session_id"]), db=db)
        if not lr.get("read_completed"):
            unread.append(step["tag"])
    base = today_payload(db, user_id=user.id)
    if unread:
        return {
            **base,
            "loop_session_ids": [s.get("loop_session_id") for s in steps],
            "read_completed": False,
            "read_cards": cards,
            "unread_tags": unread,
            "quiz": None,
        }
    if not payload.get("bundle_quiz_id"):
        items: list[dict[str, Any]] = []
        for tag in tags:
            items.extend(sl.list_bank_items_for_tag(tag))
        from backend.quiz import handler

        quiz = handler.start_session(
            db,
            user=user,
            domain="mixed",
            config={"items": items[:PRACTICE_COUNT], "auto_generate": False, "count": PRACTICE_COUNT},
        )
        payload["bundle_quiz_id"] = quiz.get("session_id")
        payload["bundle_gated_ids"] = _gated_ids_from_practice(
            db, user_id=user.id, quiz_session_id=quiz.get("session_id")
        )
        _save_payload(db, row, payload)
        return {**today_payload(db, user_id=user.id), "read_completed": True, "read_cards": cards, "quiz": quiz}
    from backend.quiz.handler import get_question

    q = get_question(db, user=user, session_id=str(payload["bundle_quiz_id"]))
    return {
        **today_payload(db, user_id=user.id),
        "read_completed": True,
        "read_cards": cards,
        "quiz": {"session_id": payload["bundle_quiz_id"], "question": q},
    }
