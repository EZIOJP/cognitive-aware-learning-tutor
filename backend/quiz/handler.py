"""Global quiz handler — vocab, math, study, code, mixed review, and custom decks."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from backend.hub.services.knowledge_graph import log_observation, upsert_node
from backend.math.answer_grade import answers_equivalent
from backend.math.services.randomizer import pick_from_bank, pick_n_from_bank
from backend.models import MathAttempt, QuizSession, User, WordProgress
from backend.models.review_card import QuizDeck, ReviewCard
from backend.quiz import review_cards as rc_mod
from backend.quiz import srs as srs_mod
from backend.quiz.store import (
    complete_global_session,
    create_global_session,
    load_global_session,
    save_global_session,
)
from backend.vocab.quiz_store import (
    complete_quiz_session,
    create_quiz_session,
    get_quiz_session,
    save_quiz_session,
)
from backend.vocab.words import load_words

MASTERY_MASTERED = 6


def _is_vocab_session(sess: dict[str, Any]) -> bool:
    row = sess.get("row")
    if row is None:
        return "words" in sess
    qt = getattr(row, "quiz_type", "") or ""
    return not str(qt).startswith("global_")


def _normalize_answer(text: str) -> str:
    return re.sub(r"\s+", "", text.strip().lower())


def _mcq_options(word: dict[str, Any], all_words: list[dict[str, Any]]) -> list[str]:
    import random

    correct = str(word.get("meaning", ""))
    pool = [str(w.get("meaning", "")) for w in all_words if w.get("meaning") and w["id"] != word["id"]]
    random.shuffle(pool)
    distractors = [d for d in pool if d != correct][:3]
    while len(distractors) < 3:
        distractors.append(f"(distractor {len(distractors) + 1})")
    options = distractors + [correct]
    random.shuffle(options)
    return options


def _attach_session_meta(question: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    meta = dict(question.get("meta") or {})
    if payload.get("time_limit_sec"):
        meta["time_limit_sec"] = int(payload["time_limit_sec"])
    if payload.get("per_question_sec"):
        meta["per_question_sec"] = int(payload["per_question_sec"])
    if payload.get("session_deadline_ms"):
        meta["session_deadline_ms"] = int(payload["session_deadline_ms"])
    question["meta"] = meta
    return question


def _vocab_question(sess: dict[str, Any], db: Session) -> dict[str, Any] | None:
    from backend.vocab.gref_import import has_usable_meaning

    words = sess["words"]
    idx = sess["index"]
    if idx >= len(words):
        return None
    word = words[idx]
    all_words = [w for w in load_words(db) if has_usable_meaning(w)]
    options = _mcq_options(word, all_words)
    q = {
        "domain": "vocab",
        "format": "mcq",
        "index": idx + 1,
        "total": len(words),
        "item_id": str(word["id"]),
        "prompt": f"What is the meaning of **{word.get('word', '')}**?",
        "options": options,
        "meta": {"word": word.get("word"), "pronunciation": word.get("pronunciation")},
    }
    return _attach_session_meta(q, sess.get("payload") or {})


def _word_by_id(db: Session, word_id: int) -> dict[str, Any] | None:
    for w in load_words(db):
        if int(w["id"]) == word_id:
            return w
    return None


def _item_to_question(
    item: dict[str, Any],
    idx: int,
    total: int,
    note_path: str,
    db: Session,
    payload: dict[str, Any],
) -> dict[str, Any]:
    kind = item.get("kind") or item.get("domain")
    if kind == "vocab" or item.get("word_id"):
        word = _word_by_id(db, int(item.get("word_id") or item.get("id")))
        if not word:
            word = {"id": item.get("word_id"), "word": item.get("word", "?"), "meaning": ""}
        all_words = load_words(db)
        q = {
            "domain": "vocab",
            "format": "mcq",
            "index": idx + 1,
            "total": total,
            "item_id": str(word["id"]),
            "prompt": f"What is the meaning of **{word.get('word', '')}**?",
            "options": _mcq_options(word, all_words),
            "meta": {"word": word.get("word"), "review_card_id": item.get("review_card_id")},
        }
        return _attach_session_meta(q, payload)

    if kind == "math":
        q = {
            "domain": "math",
            "format": "free_text",
            "index": idx + 1,
            "total": total,
            "item_id": str(item.get("id") or f"math-{idx}"),
            "prompt": item.get("prompt") or "Solve the problem.",
            "meta": {
                "topic": item.get("topic"),
                "expected": item.get("expected_answer"),
                "hint": item.get("hint"),
                "review_card_id": item.get("review_card_id"),
            },
        }
        return _attach_session_meta(q, payload)

    if kind == "code" or "starter_code" in item:
        q = {
            "domain": "code",
            "format": "code",
            "index": idx + 1,
            "total": total,
            "item_id": str(item.get("id") or f"code-{idx}"),
            "prompt": item.get("prompt") or item.get("title") or "Complete the exercise.",
            "starter_code": item.get("starter_code") or "# your code\n",
            "meta": {
                "language": item.get("language") or "python",
                "hint": item.get("hint"),
                "note_path": note_path,
                "review_card_id": item.get("review_card_id"),
                "source_chunk_id": item.get("source_chunk_id"),
                "citation": item.get("citation"),
                "entry_point": item.get("entry_point") or "",
                "test_case_count": len(item.get("test_cases") or []),
            },
        }
        return _attach_session_meta(q, payload)

    opts = item.get("options") or []
    domain = item.get("domain") or "study"
    q = {
        "domain": domain if domain in ("study", "code") else "study",
        "format": "mcq",
        "index": idx + 1,
        "total": total,
        "item_id": str(item.get("id") or f"q-{idx}"),
        "prompt": item.get("question") or item.get("prompt") or "Answer the question.",
        "options": opts,
        "meta": {
            "note_path": note_path,
            "answer_index": item.get("answer_index", 0),
            "hint": item.get("hint") or item.get("explanation"),
            "concept": item.get("concept") or item.get("topic"),
            "review_card_id": item.get("review_card_id"),
            "topic": item.get("concept") or item.get("topic"),
            "source_chunk_id": item.get("source_chunk_id"),
            "citation": item.get("citation"),
        },
    }
    return _attach_session_meta(q, payload)


def _study_question_from_payload(
    items: list[dict],
    idx: int,
    note_path: str,
    db: Session,
    payload: dict[str, Any],
) -> dict[str, Any]:
    return _item_to_question(items[idx], idx, len(items), note_path, db, payload)


def _build_session_payload(
    config: dict[str, Any],
    *,
    items: list[dict[str, Any]] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "items": items or [],
        "note_path": str(config.get("note_path") or ""),
        "topic": config.get("topic") or "",
    }
    learning_tag = str(config.get("learning_tag") or config.get("note_topic_id") or "").strip()
    if learning_tag:
        payload["learning_tag"] = learning_tag
    if config.get("time_limit_sec"):
        payload["time_limit_sec"] = int(config["time_limit_sec"])
    if config.get("per_question_sec"):
        payload["per_question_sec"] = int(config["per_question_sec"])
    if payload.get("time_limit_sec"):
        payload["session_deadline_ms"] = int(datetime.now(UTC).timestamp() * 1000) + int(
            payload["time_limit_sec"]
        ) * 1000
    if extra:
        payload.update(extra)
    return payload


def start_review_session(
    db: Session,
    *,
    user: User,
    limit: int = 20,
    domains: list[str] | None = None,
    time_limit_sec: int | None = None,
    per_question_sec: int | None = None,
) -> dict[str, Any]:
    cards = rc_mod.list_due_cards(db, user_id=user.id, limit=limit, domains=domains)
    if not cards:
        raise ValueError("No cards due for review right now.")
    items = rc_mod.expand_cards_to_quiz_items(cards)
    config: dict[str, Any] = {"time_limit_sec": time_limit_sec, "per_question_sec": per_question_sec}
    payload = _build_session_payload(config, items=items, extra={"review_mode": True})
    session_id = create_global_session(db, user_id=user.id, domain="mixed", payload=payload)
    q = _study_question_from_payload(items, 0, payload.get("note_path", ""), db, payload)
    return {"session_id": session_id, "domain": "mixed", "question": q, "card_count": len(items)}


def start_low_mastery_session(
    db: Session,
    *,
    user: User,
    tag: str | None = None,
    count: int | None = None,
) -> dict[str, Any]:
    from backend.quiz import importance as imp_mod

    n = 15 if count is None else int(count)
    n = max(1, min(40, n))
    cards = db.query(ReviewCard).filter(ReviewCard.user_id == user.id).all()
    store = imp_mod.load_store()
    session_tag = (tag or "").strip() or None
    weak = imp_mod.weak_cards_for_session(cards, tag=session_tag, store=store)
    weak = imp_mod.sort_cards_for_queue(weak, session_tag=session_tag, store=store)[:n]
    if not weak:
        raise ValueError("No low-mastery cards for this drill.")
    items = rc_mod.expand_cards_to_quiz_items(weak)
    config: dict[str, Any] = {}
    if session_tag:
        config["learning_tag"] = session_tag
    payload = _build_session_payload(
        config,
        items=items,
        extra={"low_mastery": True, "learning_tag": session_tag} if session_tag else {"low_mastery": True},
    )
    session_id = create_global_session(db, user_id=user.id, domain="mixed", payload=payload)
    q = _study_question_from_payload(items, 0, payload.get("note_path", ""), db, payload)
    return {"session_id": session_id, "domain": "mixed", "question": q, "card_count": len(items)}


def start_deck_session(db: Session, *, user: User, deck_id: int) -> dict[str, Any]:
    deck = db.query(QuizDeck).filter(QuizDeck.id == deck_id, QuizDeck.user_id == user.id).first()
    if not deck:
        raise ValueError("Quiz deck not found.")
    items = json.loads(deck.items_json or "[]")
    if not items:
        raise ValueError("Deck has no questions.")
    for i, item in enumerate(items):
        if isinstance(item, dict):
            item.setdefault("id", f"q{i + 1}")
            item.setdefault("kind", "code" if item.get("starter_code") else "mcq")
    config = {
        "topic": deck.topic or deck.title,
        "time_limit_sec": deck.time_limit_sec,
    }
    payload = _build_session_payload(config, items=items, extra={"deck_id": deck.id})
    domain = deck.domain if deck.domain in ("study", "code") else "study"
    session_id = create_global_session(db, user_id=user.id, domain=domain, payload=payload)
    q = _study_question_from_payload(items, 0, "", db, payload)
    return {"session_id": session_id, "domain": domain, "question": q}


def _auto_generate_study_questions(
    db: Session,
    user: User,
    *,
    note_path: str,
    topic: str,
    count: int = 12,
    expand_siblings: bool = True,
    llm: Any | None = None,
    llm_tier: str | None = None,
    confirm_heavy_budget: bool = False,
) -> list[dict[str, Any]]:
    """Build MCQs from an on-disk note via the global AI handler (task=quiz_gen)."""
    from backend.core.ollama_client import LlmOptions
    from backend.quiz.review_cards import weak_concepts_for_retrieval
    from backend.transcripts.study_intel import (
        expand_quiz_source_paths,
        generate_quiz_items,
        load_note_text,
    )

    rel = note_path.strip().replace("\\", "/")
    if not rel:
        return []
    paths = expand_quiz_source_paths([rel]) if expand_siblings else [rel]
    texts: list[str] = []
    for path in paths[:8]:
        try:
            texts.append(load_note_text(db, user.id, path))
        except (OSError, ValueError):
            continue
    if not any((t or "").strip() for t in texts):
        return []

    llm_opts = None
    if isinstance(llm, LlmOptions):
        llm_opts = llm
    elif isinstance(llm, dict):
        provider = llm.get("llm_provider") or llm.get("provider")
        base_url = llm.get("llm_base_url") or llm.get("base_url")
        model = llm.get("llm_model") or llm.get("model")
        if any([provider, base_url, model]):
            llm_opts = LlmOptions(provider=provider, base_url=base_url, model=model)

    boost = weak_concepts_for_retrieval(db, user.id)
    result = generate_quiz_items(
        texts,
        count=count,
        topic=topic or rel.split("/")[-1].replace(".md", ""),
        prefer_notes=True,
        boost_concepts=boost or None,
        source_labels=paths,
        llm=llm_opts,
        llm_tier=(llm_tier or "").strip() or None,
        confirm_heavy_budget=bool(confirm_heavy_budget),
    )
    return list(result.get("questions") or [])


def _is_low_quality_study_item(item: dict[str, Any]) -> bool:
    prompt = str(item.get("question") or item.get("prompt") or "").casefold()
    options = [str(option).casefold().strip() for option in item.get("options") or []]
    junk_options = {
        "description",
        "why they matter",
        "python list vs numpy array",
        "housekeeping",
        "setup",
    }
    return (
        "which statement best matches" in prompt
        or "which statement best describes the note section" in prompt
        or "completes this claim" in prompt
        or "____" in prompt
        or any(option.startswith(("it relates to:", "mainly about:")) for option in options)
        or any(option in junk_options for option in options)
    )


def start_session(
    db: Session,
    *,
    user: User,
    domain: str,
    config: dict[str, Any],
) -> dict[str, Any]:
    domain = domain.strip().lower()

    if config.get("low_mastery"):
        return start_low_mastery_session(
            db,
            user=user,
            tag=str(config.get("tag") or config.get("note_topic_id") or "").strip() or None,
            count=config.get("count"),
        )

    if domain == "review":
        return start_review_session(
            db,
            user=user,
            limit=int(config.get("limit") or 20),
            domains=config.get("domains"),
            time_limit_sec=config.get("time_limit_sec"),
            per_question_sec=config.get("per_question_sec"),
        )

    if domain == "deck":
        return start_deck_session(db, user=user, deck_id=int(config.get("deck_id")))

    if domain == "vocab":
        from backend.vocab.gref_import import has_usable_meaning

        words = [w for w in load_words(db) if has_usable_meaning(w)]
        group_number = config.get("group_number")
        word_ids = config.get("word_ids") or []
        if word_ids:
            ids = {int(i) for i in word_ids}
            words = [w for w in words if int(w["id"]) in ids]
        elif group_number is not None:
            gn = int(group_number)
            words = [w for w in words if int(w.get("group_number", 0)) == gn]
        if not words:
            raise ValueError("No vocab words with meanings found for this quiz.")
        session_id = create_quiz_session(db, user_id=user.id, quiz_type="adaptive_group", words=words)
        sess = get_quiz_session(db, session_id, user.id)
        assert sess is not None
        if config.get("time_limit_sec"):
            sess["payload"] = {
                "time_limit_sec": int(config["time_limit_sec"]),
                "session_deadline_ms": int(datetime.now(UTC).timestamp() * 1000)
                + int(config["time_limit_sec"]) * 1000,
            }
            save_quiz_session(db, sess)
        q = _vocab_question(sess, db)
        return {"session_id": session_id, "domain": "vocab", "question": q}

    if domain == "math":
        topic = str(config.get("topic") or "Arithmetic")
        count = int(config.get("count") or config.get("question_count") or 5)
        skill_id = config.get("node_id") or config.get("skill_id")
        skill_id_s = str(skill_id).strip() if skill_id else None
        content_topic_id = str(config.get("topic_id") or "").strip() or None
        note_topic_id = str(config.get("note_topic_id") or "").strip() or None
        prefer_topic_ids = [
            str(t).strip()
            for t in (config.get("prefer_topic_ids") or [])
            if str(t).strip()
        ]

        items: list[dict[str, Any]] = []
        use_generator = bool(config.get("use_generator")) or (
            content_topic_id or ""
        ).startswith("math.gen.")
        gen_id_cfg = config.get("gen_id")
        adaptive_aptitude = bool(
            config.get("adaptive_aptitude")
            or config.get("adaptive")
            or config.get("core_math_drill")
        )

        # Hybrid bank:
        # 0) adaptive core aptitude → mathgenerator only, weighted by weak tags
        # 1) explicit generator / use_generator
        # 2) curated content_bank packs
        # 3) generator fill for MT tag
        # 4) legacy skill nodes / DB bank
        if adaptive_aptitude:
            from backend.quiz import math_generators as mg

            items = mg.generate_quiz_items(
                db,
                count=count,
                adaptive=True,
                aptitude_only=True,
                user_id=user.id,
                note_topic_id=note_topic_id,
                boost_note_topics=list(config.get("boost_note_topics") or []) or None,
            )
            topic = "Core math (adaptive)"
        elif use_generator or gen_id_cfg is not None:
            from backend.quiz import math_generators as mg

            recipe = None
            if gen_id_cfg is not None:
                for r in mg.list_recipes():
                    if r.gen_id == int(gen_id_cfg):
                        recipe = r
                        break
            items = mg.generate_quiz_items(
                db,
                recipe=recipe,
                topic_id=None if recipe else content_topic_id,
                note_topic_id=None if (recipe or content_topic_id) else note_topic_id,
                count=count,
                adaptive=bool(config.get("adaptive")),
                user_id=user.id,
            )
            topic = str(items[0].get("topic_title") or items[0].get("topic_id") or topic)
        elif content_topic_id or note_topic_id or prefer_topic_ids:
            from backend.quiz import content_bank as cb
            from backend.quiz import math_generators as mg

            gathered: list[dict[str, Any]] = []
            # Generator topic_id alone
            if content_topic_id and content_topic_id.startswith("math.gen."):
                gathered = mg.generate_quiz_items(
                    db, topic_id=content_topic_id, count=count
                )
            else:
                if prefer_topic_ids:
                    for tid in prefer_topic_ids:
                        if tid.startswith("math.gen."):
                            gathered.extend(
                                mg.generate_quiz_items(db, topic_id=tid, count=max(2, count // 2))
                            )
                        else:
                            gathered.extend(
                                cb.build_quiz_items(kind="math", topic_id=tid, shuffle=True)
                            )
                else:
                    gathered = cb.build_quiz_items(
                        kind="math",
                        topic_id=content_topic_id,
                        note_topic_id=note_topic_id,
                        shuffle=True,
                    )
                # Fill shortfall from generators mapped to the same MT tag
                if len(gathered) < count and note_topic_id:
                    try:
                        extra_gen = mg.generate_quiz_items(
                            db,
                            note_topic_id=note_topic_id,
                            count=count - len(gathered),
                        )
                        gathered.extend(extra_gen)
                    except ValueError:
                        pass
            if not gathered:
                # Last resort: generators for MT tag or any recipe
                try:
                    gathered = mg.generate_quiz_items(
                        db,
                        note_topic_id=note_topic_id,
                        topic_id=content_topic_id,
                        count=count,
                    )
                except ValueError as exc:
                    raise ValueError(
                        "No math questions for that topic in content bank or mathgenerator."
                    ) from exc
            items = gathered[: max(1, count)]
            topic = str(
                items[0].get("topic_title")
                or items[0].get("topic_id")
                or content_topic_id
                or note_topic_id
                or topic
            )
        elif skill_id_s:
            from backend.math.skills import generate_drill_items, get_node, node_status

            node = get_node(skill_id_s)
            if not node:
                raise ValueError(f"Unknown math skill node: {skill_id_s}")
            st = node_status(db, user_id=user.id, node=node)
            if st == "locked":
                raise ValueError(f"Skill '{skill_id_s}' is locked. Master prerequisites first.")
            items = generate_drill_items(skill_id_s, count, db=db, user_id=user.id)
            topic = str(node.get("topic") or topic)
        else:
            problems = pick_n_from_bank(db, topic, count, skill_id=None)
            if not problems and topic:
                problems = pick_n_from_bank(db, None, count, skill_id=None)
            if not problems:
                problem = pick_from_bank(db, topic) or pick_from_bank(db, None)
                if not problem:
                    raise ValueError("No math questions in bank. Add templates or import questions first.")
                problems = [problem]
            items = [
                {
                    "kind": "math",
                    "id": str(p.get("question_id") or f"{topic}-{i}"),
                    "prompt": p.get("prompt") or f"Solve: {topic}",
                    "expected_answer": p.get("expected_answer"),
                    "topic": p.get("topic") or topic,
                    "hint": p.get("explanation"),
                    "question_id": p.get("question_id"),
                    "generated_id": p.get("generated_id"),
                    "skill_id": None,
                }
                for i, p in enumerate(problems)
            ]

        extra: dict[str, Any] = {"topic": topic}
        if skill_id_s:
            extra["skill_id"] = skill_id_s
            extra["node_id"] = skill_id_s
        if content_topic_id:
            extra["topic_id"] = content_topic_id
        if note_topic_id:
            extra["note_topic_id"] = note_topic_id
        payload = _build_session_payload(config, items=items, extra=extra)
        session_id = create_global_session(db, user_id=user.id, domain="math", payload=payload)
        q = _study_question_from_payload(items, 0, "", db, payload)
        return {"session_id": session_id, "domain": "math", "question": q}

    if domain in ("study", "code", "mixed"):
        questions = [
            q
            for q in list(config.get("questions") or [])
            if isinstance(q, dict) and not _is_low_quality_study_item(q)
        ]
        drills = list(config.get("drills") or [])
        items: list[dict[str, Any]] = list(config.get("items") or [])
        note_path = str(config.get("note_path") or "")

        if not questions and not drills and not items and note_path and config.get("auto_generate", True):
            count = int(config.get("count") or config.get("question_count") or 5)
            topic = str(config.get("topic") or note_path.split("/")[-1].replace(".md", ""))
            llm_cfg = {
                "llm_provider": config.get("llm_provider"),
                "llm_base_url": config.get("llm_base_url"),
                "llm_model": config.get("llm_model"),
            }
            generated = _auto_generate_study_questions(
                db,
                user,
                note_path=note_path,
                topic=topic,
                count=count,
                expand_siblings=bool(config.get("expand_siblings", True)),
                llm=llm_cfg,
                llm_tier=str(config.get("llm_tier") or "").strip() or None,
                confirm_heavy_budget=bool(config.get("confirm_heavy_budget")),
            )
            if not generated:
                raise ValueError(
                    "Could not auto-generate quiz from note. Open Lecture Notes and use Generate quiz first."
                )
            questions = generated

        for q in questions:
            items.append({"kind": "mcq", **q})
        for d in drills:
            items.append({"kind": "code", **d})
        if not items:
            raise ValueError(
                "Provide questions/drills, or set note_path with auto_generate for study quizzes."
            )
        payload = _build_session_payload(config, items=items, extra={"note_path": note_path})
        session_domain = domain if domain != "mixed" else "mixed"
        if session_domain == "mixed":
            pass
        elif drills and not questions:
            session_domain = "code"
        payload["topic"] = config.get("topic") or ""
        session_id = create_global_session(
            db,
            user_id=user.id,
            domain=session_domain,
            payload=payload,
        )
        q = _study_question_from_payload(items, 0, note_path, db, payload)
        return {"session_id": session_id, "domain": session_domain, "question": q}

    raise ValueError(f"Unsupported quiz domain: {domain}")


def get_question(db: Session, *, user: User, session_id: str) -> dict[str, Any] | None:
    vocab_sess = get_quiz_session(db, session_id, user.id)
    if vocab_sess and _is_vocab_session(vocab_sess):
        return _vocab_question(vocab_sess, db)

    sess = load_global_session(db, session_id, user.id)
    if not sess:
        return None
    payload = sess["payload"]
    items = payload.get("items") or []
    if sess["domain"] == "math" and not items:
        problem = payload.get("problem") or {}
        return _item_to_question(
            {
                "kind": "math",
                "id": problem.get("question_id") or payload.get("topic"),
                "prompt": problem.get("prompt") or problem.get("question"),
                "expected_answer": problem.get("expected_answer"),
                "topic": payload.get("topic"),
            },
            0,
            1,
            "",
            db,
            payload,
        )
    if sess["index"] >= len(items):
        return None
    return _study_question_from_payload(items, sess["index"], payload.get("note_path", ""), db, payload)


def _record_review_card(
    db: Session,
    *,
    user: User,
    domain: str,
    item_id: str,
    label: str,
    payload: dict[str, Any],
    correct: bool,
    time_taken_ms: int,
    topic: str | None = None,
    note_path: str | None = None,
    fmt: str = "mcq",
    deck_id: int | None = None,
    session_tag: str | None = None,
) -> tuple[int, int]:
    card = rc_mod.upsert_review_card(
        db,
        user_id=user.id,
        domain=domain,
        item_id=item_id,
        label=label,
        payload=payload,
        correct=correct,
        elapsed_ms=time_taken_ms,
        topic=topic,
        note_path=note_path,
        fmt=fmt,
        deck_id=deck_id,
        session_tag=session_tag,
    )
    state = srs_mod.srs_from_metadata(json.loads(card.srs_json or "{}"))
    return int(state.mastery), int(state.owes_corrects or 0)


def submit_answer(
    db: Session,
    *,
    user: User,
    session_id: str,
    item_id: str,
    response: str,
    time_taken_ms: int = 0,
) -> dict[str, Any]:
    vocab_sess = get_quiz_session(db, session_id, user.id)
    if vocab_sess and _is_vocab_session(vocab_sess):
        return _submit_vocab(db, user, vocab_sess, session_id, item_id, response, time_taken_ms)

    sess = load_global_session(db, session_id, user.id)
    if not sess:
        raise ValueError("Quiz session not found.")

    if sess["domain"] == "math" and not (sess["payload"].get("items")):
        return _submit_math(db, user, sess, session_id, response, time_taken_ms)

    return _submit_study(db, user, sess, session_id, item_id, response, time_taken_ms)


def _submit_vocab(
    db: Session,
    user: User,
    sess: dict[str, Any],
    session_id: str,
    item_id: str,
    response: str,
    time_taken_ms: int,
) -> dict[str, Any]:
    words = sess["words"]
    idx = sess["index"]
    if idx >= len(words):
        raise ValueError("Quiz already complete.")
    word = words[idx]
    correct = response.strip().lower() == str(word.get("meaning", "")).strip().lower()
    p = db.query(WordProgress).filter(WordProgress.user_id == user.id, WordProgress.word_id == word["id"]).first()
    if not p:
        p = WordProgress(user_id=user.id, word_id=int(word["id"]))
        db.add(p)
    p.times_asked = int(p.times_asked or 0) + 1
    if correct:
        p.times_correct = int(p.times_correct or 0) + 1
        p.consecutive_correct = int(p.consecutive_correct or 0) + 1
        p.mastery = int(p.mastery or 0) + 1
    else:
        p.consecutive_correct = 0
        p.mastery = max(-2, int(p.mastery or 0) - 2)
    if correct and int(p.mastery or 0) >= 3:
        fsrs = srs_mod.schedule_after_answer(srs_mod.SrsState(mastery=int(p.mastery or 0)), correct=True)
        p.due_date = fsrs.due_date
        p.interval_days = fsrs.interval_days
    db.commit()

    mastery, _owes = _record_review_card(
        db,
        user=user,
        domain="vocab",
        item_id=str(word["id"]),
        label=str(word.get("word", "")),
        payload={"word_id": word["id"], "word": word.get("word"), "meaning": word.get("meaning")},
        correct=correct,
        time_taken_ms=time_taken_ms,
        fmt="mcq",
    )

    sess["attempts"].append(
        {
            "item_id": item_id,
            "domain": "vocab",
            "correct": correct,
            "response": response,
            "time_taken_ms": time_taken_ms,
            "label": word.get("word"),
        }
    )
    sess["index"] += 1
    save_quiz_session(db, sess)
    next_q = _vocab_question(sess, db)
    return {
        "correct": correct,
        "feedback": "Correct!" if correct else f"Expected: {word.get('meaning')}",
        "mastery": mastery,
        "complete": next_q is None,
        "next_question": next_q,
        "added_to_review": True,
    }


def _submit_math(
    db: Session,
    user: User,
    sess: dict[str, Any],
    session_id: str,
    response: str,
    time_taken_ms: int,
) -> dict[str, Any]:
    problem = sess["payload"].get("problem") or {}
    expected = str(problem.get("expected_answer") or problem.get("answer") or "")
    correct = answers_equivalent(expected, response)
    topic = str(sess["payload"].get("topic") or "Arithmetic")
    attempt = MathAttempt(
        user_id=user.id,
        topic=topic,
        prompt=str(problem.get("prompt") or ""),
        user_answer=response,
        expected_answer=expected,
        is_correct=correct,
        question_id=problem.get("question_id"),
        generated_id=problem.get("generated_id"),
    )
    db.add(attempt)
    db.commit()

    node = upsert_node(db, user_id=user.id, label=topic, node_type="math_topic")
    meta = json.loads(node.metadata_json or "{}") if node.metadata_json else {}
    state = srs_mod.schedule_after_answer(
        srs_mod.srs_from_metadata(meta.get("srs")), correct=correct, elapsed_ms=time_taken_ms
    )
    meta["srs"] = srs_mod.srs_to_metadata(state)
    node.metadata_json = json.dumps(meta)
    db.commit()
    log_observation(
        db,
        node_id=node.id,
        user_id=user.id,
        interaction_type="math_pass" if correct else "math_fail",
        value=1.0 if correct else 0.0,
    )

    item_id = str(problem.get("question_id") or topic)
    mastery, _owes = _record_review_card(
        db,
        user=user,
        domain="math",
        item_id=item_id,
        label=str(problem.get("prompt") or topic)[:300],
        payload={
            "id": item_id,
            "prompt": problem.get("prompt"),
            "expected_answer": expected,
            "topic": topic,
        },
        correct=correct,
        time_taken_ms=time_taken_ms,
        topic=topic,
        fmt="free_text",
    )

    sess["attempts"].append(
        {
            "item_id": item_id,
            "domain": "math",
            "correct": correct,
            "response": response,
            "time_taken_ms": time_taken_ms,
            "label": topic,
        }
    )
    sess["index"] = 1
    save_global_session(db, sess)
    return {
        "correct": correct,
        "feedback": "Correct!" if correct else f"Expected: {expected}",
        "mastery": mastery,
        "complete": True,
        "next_question": None,
        "added_to_review": True,
    }


def _submit_study(
    db: Session,
    user: User,
    sess: dict[str, Any],
    session_id: str,
    item_id: str,
    response: str,
    time_taken_ms: int,
) -> dict[str, Any]:
    items = sess["payload"].get("items") or []
    idx = sess["index"]
    if idx >= len(items):
        raise ValueError("Quiz already complete.")
    item = items[idx]
    note_path = str(sess["payload"].get("note_path") or "")
    kind = item.get("kind") or item.get("domain") or "mcq"
    deck_id = sess["payload"].get("deck_id")

    if kind == "vocab" or item.get("word_id"):
        word = _word_by_id(db, int(item.get("word_id") or item.get("id")))
        if not word:
            raise ValueError("Vocab word not found.")
        correct = response.strip().lower() == str(word.get("meaning", "")).strip().lower()
        feedback = "Correct!" if correct else f"Expected: {word.get('meaning')}"
        label = str(word.get("word", ""))
        domain = "vocab"
        payload = {"word_id": word["id"], "word": word.get("word"), "meaning": word.get("meaning")}
        fmt = "mcq"
        topic = word.get("word")
    elif kind == "math":
        expected = str(item.get("expected_answer") or "")
        open_ended = (
            not expected.strip()
            or str(item.get("answer_format") or "").lower() == "open"
            or "no-answer" in [str(t).lower() for t in (item.get("tags") or [])]
        )
        if open_ended:
            # Self-check: any non-empty attempt counts; show solution if present.
            correct = bool(response.strip())
            strategy = str(item.get("hint") or item.get("explanation") or "").strip()
            steps = item.get("solution_steps") or []
            sol = strategy or ("\n".join(str(s) for s in steps[:8] if s))
            feedback = "Recorded (open problem — check the solution)."
            if sol:
                feedback = f"{feedback}\n\nSolution:\n{sol}"
            elif not correct:
                feedback = "Write any attempt / outline, then continue."
        else:
            correct = answers_equivalent(expected, response)
            strategy = str(item.get("hint") or item.get("explanation") or "").strip()
            if correct:
                feedback = "Correct!"
                if time_taken_ms and time_taken_ms <= 3000:
                    feedback = "Correct — instant!"
                elif time_taken_ms and time_taken_ms <= 8000:
                    feedback = "Correct — solid pace."
                else:
                    feedback = "Correct — aim for under 8s next time."
            else:
                feedback = f"Expected: {expected}"
                if strategy:
                    feedback = f"{feedback}\n\nStrategy: {strategy}"
        label = str(item.get("prompt") or item.get("topic") or "Math")[:300]
        domain = "math"
        payload = dict(item)
        fmt = "free_text"
        topic = str(item.get("topic") or sess["payload"].get("topic") or "math")
        attempt = MathAttempt(
            user_id=user.id,
            topic=topic,
            prompt=str(item.get("prompt") or ""),
            user_answer=response,
            expected_answer=expected or "(open)",
            is_correct=correct,
            question_id=item.get("question_id"),
            generated_id=item.get("generated_id"),
        )
        db.add(attempt)
        db.commit()
        math_node = upsert_node(db, user_id=user.id, label=topic, node_type="math_topic")
        math_meta = json.loads(math_node.metadata_json or "{}") if math_node.metadata_json else {}
        math_state = srs_mod.schedule_after_answer(
            srs_mod.srs_from_metadata(math_meta.get("srs")), correct=correct, elapsed_ms=time_taken_ms
        )
        math_meta["srs"] = srs_mod.srs_to_metadata(math_state)
        # Speed samples for mastery unlock
        recent_ms = list(math_meta.get("recent_ms") or [])
        if time_taken_ms > 0:
            recent_ms.append(int(time_taken_ms) if correct else int(time_taken_ms * 1.15))
            math_meta["recent_ms"] = recent_ms[-40:]
        factors = item.get("factors") or []
        if not correct and factors:
            weak = list(math_meta.get("weak_factors") or [])
            weak.extend(int(f) for f in factors if isinstance(f, (int, float)) or str(f).isdigit())
            math_meta["weak_factors"] = weak[-60:]
        math_node.metadata_json = json.dumps(math_meta)
        db.commit()
        log_observation(
            db,
            node_id=math_node.id,
            user_id=user.id,
            interaction_type="math_pass" if correct else "math_fail",
            value=1.0 if correct else 0.0,
        )
    elif kind == "code" or "starter_code" in item:
        starter = str(item.get("starter_code") or "").strip()
        submitted = response.strip()
        changed = submitted != starter
        substantive = len(submitted) >= 12 and not submitted.lstrip().startswith("# TODO")
        correct = changed and substantive
        feedback = "Submitted for review." if correct else "Edit the starter code with a real attempt before submitting."
        label = str(item.get("title") or item.get("prompt") or "Code drill")[:300]
        domain = "code"
        payload = dict(item)
        fmt = "code"
        topic = str(item.get("title") or sess["payload"].get("topic") or "code")[:120]
    else:
        opts = item.get("options") or []
        ans_idx = int(item.get("answer_index", 0))
        expected = opts[ans_idx] if opts and 0 <= ans_idx < len(opts) else ""
        correct = response.strip() == expected.strip()
        concept = str(item.get("concept") or item.get("topic") or "").strip()
        base_fb = item.get("explanation") or ("Correct!" if correct else f"Expected: {expected}")
        if correct:
            feedback = str(base_fb)
        elif concept:
            feedback = f"{base_fb}\n\nTopic to review: {concept}"
        else:
            feedback = str(base_fb)
        label = str(item.get("question") or item.get("prompt") or "Question")[:300]
        domain = str(item.get("domain") or sess["domain"] or "study")
        if domain == "mixed":
            domain = "study"
        payload = dict(item)
        fmt = "mcq"
        topic = concept or str(sess["payload"].get("topic") or "study")[:120]

    source_chunk_id = str(item.get("source_chunk_id") or payload.get("source_chunk_id") or "").strip()
    eligible_for_review = not (
        kind not in ("vocab", "math", "code")
        and _is_low_quality_study_item(item)
    )

    if kind != "math" and eligible_for_review:
        if source_chunk_id:
            node = upsert_node(
                db,
                user_id=user.id,
                label=f"chunk:{source_chunk_id}",
                node_type="chunk",
                metadata={"chunk_id": source_chunk_id},
                note_path=note_path or None,
            )
        else:
            node = upsert_node(
                db, user_id=user.id, label=topic or label, node_type="concept", note_path=note_path or None
            )
        meta = json.loads(node.metadata_json or "{}") if node.metadata_json else {}
        state = srs_mod.schedule_after_answer(
            srs_mod.srs_from_metadata(meta.get("srs")), correct=correct, elapsed_ms=time_taken_ms
        )
        meta["srs"] = srs_mod.srs_to_metadata(state)
        meta["domain"] = domain
        node.metadata_json = json.dumps(meta)
        db.commit()
        log_observation(
            db,
            node_id=node.id,
            user_id=user.id,
            interaction_type="quiz_pass" if correct else "quiz_fail",
            value=1.0 if correct else 0.0,
        )

    mastery = 0
    owes = 0
    card_id = str(item.get("id") or item_id)
    if item.get("schedule_topic_pack"):
        pack_id = str(item.get("review_card_id") or "")
        scores = sess["payload"].setdefault("topic_pack_scores", {})
        if pack_id:
            scores.setdefault(pack_id, []).append(bool(correct))
        pack_size = int(item.get("pack_size") or 1)
        pack_index = int(item.get("pack_index") or 0)
        if pack_id and pack_index + 1 >= pack_size:
            pack_results = scores.get(pack_id) or []
            pack_ok = sum(1 for x in pack_results if x) * 2 >= max(1, len(pack_results))
            topic_id = str(item.get("topic_id") or topic or "topic")
            mastery, _owes = _record_review_card(
                db,
                user=user,
                domain=domain,
                item_id=f"topic-{topic_id}",
                label=str(item.get("topic") or topic_id)[:300],
                payload={
                    "kind": "topic_pack",
                    "topic_id": topic_id,
                    "questions": [it for it in items if str(it.get("review_card_id")) == pack_id],
                },
                correct=pack_ok,
                time_taken_ms=time_taken_ms,
                topic=topic_id[:160],
                note_path=note_path or None,
                fmt="mcq",
                deck_id=int(deck_id) if deck_id else None,
                session_tag=str(sess["payload"].get("learning_tag") or "") or None,
            )
    elif eligible_for_review:
        card_id = str(item.get("_card_item_id") or item.get("id") or item_id)
        for sep in ("-recycle", "-retry"):
            if sep in card_id:
                card_id = card_id.split(sep)[0]
                break
        mastery, owes = _record_review_card(
            db,
            user=user,
            domain=domain,
            item_id=card_id,
            label=label,
            payload=payload,
            correct=correct,
            time_taken_ms=time_taken_ms,
            topic=topic,
            note_path=note_path or None,
            fmt=fmt,
            deck_id=int(deck_id) if deck_id else None,
            session_tag=str(sess["payload"].get("learning_tag") or "") or None,
        )

    sess["attempts"].append(
        {
            "item_id": item_id,
            "domain": domain,
            "correct": correct,
            "response": response,
            "time_taken_ms": time_taken_ms,
            "label": label,
        }
    )
    requeued = False
    retry_count = int(item.get("_retry_count") or 0)
    if owes > 0 and eligible_for_review and not item.get("schedule_topic_pack"):
        from backend.quiz import importance as imp_mod

        retry = dict(item)
        retry["_card_item_id"] = str(item.get("_card_item_id") or card_id)
        retry["_retry_count"] = retry_count + 1
        retry["_requeued"] = True
        if kind == "math":
            try:
                retry = imp_mod.ephemeral_math_recycle(retry)
            except Exception:  # noqa: BLE001
                pass
        retry["id"] = f"{retry['_card_item_id']}-recycle{retry['_retry_count']}"
        pos = imp_mod.recycle_insert_index(sess["index"], len(items))
        items.insert(pos, retry)
        sess["payload"]["items"] = items
        requeued = True
    else:
        max_retries = 8 if (kind == "math" or item.get("repeat_until_correct")) else 1
        if (
            not correct
            and eligible_for_review
            and not item.get("schedule_topic_pack")
            and retry_count < max_retries
            and (
                (fmt == "mcq" and kind not in ("vocab", "math", "code"))
                or kind == "math"
                or item.get("repeat_until_correct")
            )
        ):
            retry = dict(item)
            retry["id"] = f"{item.get('id') or item_id}-retry{retry_count + 1}"
            retry["_retry_count"] = retry_count + 1
            retry["_requeued"] = True
            items.append(retry)
            sess["payload"]["items"] = items
            requeued = True

            if kind == "math" and item.get("gen_id") is not None:
                try:
                    from backend.quiz import math_generators as mg

                    extra = mg.generate_quiz_items(
                        db,
                        topic_id=str(item.get("topic_id") or ""),
                        count=1,
                        user_id=user.id,
                    )
                    for ex in extra:
                        ex["repeat_until_correct"] = True
                        ex["_retry_count"] = 0
                        items.append(ex)
                    sess["payload"]["items"] = items
                except Exception:  # noqa: BLE001
                    pass

    sess["index"] += 1
    save_global_session(db, sess)
    next_q = (
        None
        if sess["index"] >= len(items)
        else _study_question_from_payload(items, sess["index"], note_path, db, sess["payload"])
    )
    return {
        "correct": correct,
        "feedback": feedback,
        "mastery": mastery,
        "complete": next_q is None,
        "next_question": next_q,
        "added_to_review": eligible_for_review,
        "requeued": requeued,
    }


def complete_session(db: Session, *, user: User, session_id: str) -> dict[str, Any]:
    from backend.quiz.next_step import compute_next_step

    vocab_sess = get_quiz_session(db, session_id, user.id)
    if vocab_sess and _is_vocab_session(vocab_sess):
        hub_id = complete_quiz_session(db, session_id, user.id)
        attempts = vocab_sess.get("attempts") or []
        correct = sum(1 for a in attempts if a.get("correct"))
        total_ms = sum(int(a.get("time_taken_ms") or 0) for a in attempts)
        return {
            "complete": True,
            "correct": correct,
            "total": len(attempts),
            "accuracy_pct": round(100 * correct / len(attempts)) if attempts else 0,
            "total_time_ms": total_ms,
            "attempts": attempts,
            "hub_session_id": hub_id,
            "next_step": compute_next_step(db, user_id=user.id),
        }

    hub_id = complete_global_session(db, session_id, user.id)
    sess = load_global_session(db, session_id, user.id)
    attempts = (sess or {}).get("attempts") or []
    correct = sum(1 for a in attempts if a.get("correct"))
    total_ms = sum(int(a.get("time_taken_ms") or 0) for a in attempts)
    from backend.vocab.hub_hooks import on_global_quiz_complete

    on_global_quiz_complete(
        db,
        user.id,
        correct,
        len(attempts),
        domain=(sess or {}).get("domain"),
        hub_session_id=hub_id,
    )
    return {
        "complete": True,
        "correct": correct,
        "total": len(attempts),
        "accuracy_pct": round(100 * correct / len(attempts)) if attempts else 0,
        "total_time_ms": total_ms,
        "attempts": attempts,
        "domain": (sess or {}).get("domain"),
        "hub_session_id": hub_id,
        "next_step": compute_next_step(db, user_id=user.id),
    }


def list_due_items(db: Session, *, user: User, limit: int = 40) -> list[dict[str, Any]]:
    """Due review cards (primary) plus legacy vocab progress rows."""
    cards = rc_mod.list_due_cards(db, user_id=user.id, limit=limit)
    due = [rc_mod.card_to_due_item(c) for c in cards]
    if due:
        return due

    now = datetime.now(UTC)
    words = load_words(db)
    progress_rows = db.query(WordProgress).filter(WordProgress.user_id == user.id).all()
    prog_by_word = {int(p.word_id): p for p in progress_rows}
    for w in words:
        p = prog_by_word.get(int(w["id"]))
        if not p or p.is_suspended:
            continue
        if p.due_date and p.due_date.replace(tzinfo=UTC) <= now:
            due.append(
                {
                    "card_id": None,
                    "domain": "vocab",
                    "item_id": str(w["id"]),
                    "label": w.get("word"),
                    "mastery": int(p.mastery or 0),
                    "due_date": p.due_date.isoformat(),
                }
            )
    return due[:limit]


def get_backlog(db: Session, *, user: User) -> dict[str, Any]:
    return rc_mod.backlog_summary(db, user_id=user.id)


def list_decks(db: Session, *, user: User) -> list[dict[str, Any]]:
    rows = db.query(QuizDeck).filter(QuizDeck.user_id == user.id).order_by(QuizDeck.updated_at.desc()).all()
    out = []
    for row in rows:
        items = json.loads(row.items_json or "[]")
        out.append(
            {
                "id": row.id,
                "title": row.title,
                "topic": row.topic,
                "domain": row.domain,
                "item_count": len(items),
                "time_limit_sec": row.time_limit_sec,
                "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            }
        )
    return out


def save_deck(
    db: Session,
    *,
    user: User,
    title: str,
    items: list[dict[str, Any]],
    domain: str = "study",
    topic: str = "",
    time_limit_sec: int | None = None,
    deck_id: int | None = None,
) -> dict[str, Any]:
    if not items:
        raise ValueError("Add at least one question.")
    if deck_id:
        row = db.query(QuizDeck).filter(QuizDeck.id == deck_id, QuizDeck.user_id == user.id).first()
        if not row:
            raise ValueError("Deck not found.")
    else:
        row = QuizDeck(user_id=user.id)
        db.add(row)
    row.title = title.strip() or "My Quiz"
    row.topic = topic.strip() or None
    row.domain = domain if domain in ("study", "code", "mixed") else "study"
    row.items_json = json.dumps(items)
    row.time_limit_sec = time_limit_sec
    row.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(row)
    seeded = rc_mod.seed_deck_cards(db, user_id=user.id, deck=row)
    return {"id": row.id, "title": row.title, "item_count": len(items), "cards_seeded": seeded}


def delete_deck(db: Session, *, user: User, deck_id: int) -> None:
    row = db.query(QuizDeck).filter(QuizDeck.id == deck_id, QuizDeck.user_id == user.id).first()
    if not row:
        raise ValueError("Deck not found.")
    db.delete(row)
    db.commit()


def wipe_practice_history(
    db: Session,
    *,
    user: User | None = None,
    all_users: bool = False,
) -> dict[str, int]:
    """Delete decks, ReviewCards, and quiz sessions (vocab word bank untouched)."""
    from backend.models.review_card import ReviewCard

    if not all_users and user is None:
        raise ValueError("user required unless all_users=True")

    uid = None if all_users else user.id

    cards_q = db.query(ReviewCard)
    decks_q = db.query(QuizDeck)
    sess_q = db.query(QuizSession)
    if uid is not None:
        cards_q = cards_q.filter(ReviewCard.user_id == uid)
        decks_q = decks_q.filter(QuizDeck.user_id == uid)
        sess_q = sess_q.filter(QuizSession.user_id == uid)

    cards = cards_q.delete(synchronize_session=False)
    decks = decks_q.delete(synchronize_session=False)
    sessions = sess_q.delete(synchronize_session=False)
    db.commit()
    return {
        "review_cards": int(cards),
        "quiz_decks": int(decks),
        "quiz_sessions": int(sessions),
    }


def clear_review_cards(
    db: Session,
    *,
    user: User,
    domain: str | None = None,
    all_users: bool = False,
) -> dict[str, int]:
    deleted = rc_mod.clear_review_cards(
        db,
        user_id=None if all_users else user.id,
        domain=domain,
    )
    return {"deleted": deleted}


def list_recent_results(db: Session, *, user: User, limit: int = 10) -> list[dict[str, Any]]:
    rows = (
        db.query(QuizSession)
        .filter(QuizSession.user_id == user.id, QuizSession.completed_at.isnot(None))
        .order_by(QuizSession.completed_at.desc())
        .limit(limit)
        .all()
    )
    results = []
    for row in rows:
        attempts = json.loads(row.attempts_json or "[]")
        correct = sum(1 for a in attempts if a.get("correct"))
        meta = json.loads(row.word_ids_json or "{}")
        results.append(
            {
                "session_id": row.external_id,
                "domain": meta.get("domain") or row.quiz_type.replace("global_", ""),
                "correct": correct,
                "total": len(attempts),
                "accuracy_pct": round(100 * correct / len(attempts)) if attempts else 0,
                "completed_at": row.completed_at.isoformat() if row.completed_at else None,
            }
        )
    return results
