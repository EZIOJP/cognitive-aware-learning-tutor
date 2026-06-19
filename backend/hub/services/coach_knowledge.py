"""On-demand knowledge retrieval for the AI coach (DB + note files + transcripts)."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from backend.models import LectureNote, MathAttempt, WordProgress
from backend.paths import NOTES_DIR, TRANSCRIPTS_DIR
from backend.vocab.words import load_words

MASTERY_MASTERED = 6
_MAX_KB_CHARS = 14_000
_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "or",
        "but",
        "in",
        "on",
        "at",
        "to",
        "for",
        "of",
        "is",
        "it",
        "my",
        "me",
        "i",
        "you",
        "we",
        "what",
        "how",
        "when",
        "where",
        "why",
        "about",
        "this",
        "that",
        "with",
        "from",
        "can",
        "do",
        "did",
        "was",
        "are",
        "be",
        "have",
        "has",
        "had",
        "tell",
        "help",
        "please",
        "app",
        "coach",
    }
)


def _tokenize_query(query: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9]{3,}", (query or "").lower())
    return [t for t in tokens if t not in _STOPWORDS][:12]


def _trim(text: str, limit: int) -> str:
    text = re.sub(r"\n{3,}", "\n\n", text.strip())
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _word_lookup(db: Session) -> dict[int, dict[str, Any]]:
    return {int(w["id"]): w for w in load_words(db) if w.get("id") is not None}


def _vocab_entries(
    db: Session,
    user_id: int,
    *,
    keywords: list[str],
    limit: int = 18,
) -> list[dict[str, Any]]:
    words_by_id = _word_lookup(db)
    now = datetime.now(timezone.utc)
    rows = db.query(WordProgress).filter(WordProgress.user_id == user_id).all()

    scored: list[tuple[int, dict[str, Any]]] = []
    for prog in rows:
        word = words_by_id.get(prog.word_id)
        if not word:
            continue
        label = str(word.get("word", "")).lower()
        meaning = str(word.get("meaning", ""))[:160]
        mastery = prog.mastery or 0
        asked = prog.times_asked or 0
        due = (
            prog.due_date is not None
            and prog.due_date.replace(tzinfo=timezone.utc) <= now
            and not prog.is_suspended
        )
        keyword_hit = any(k in label or k in meaning.lower() for k in keywords)
        weak = asked > 0 and mastery <= 0
        score = 0
        if keyword_hit:
            score += 10
        if due:
            score += 6
        if weak:
            score += 4
        if mastery < MASTERY_MASTERED and asked > 0:
            score += 2
        if score == 0 and not keywords:
            continue
        if score == 0:
            continue
        scored.append(
            (
                score,
                {
                    "word": word.get("word"),
                    "meaning": meaning,
                    "mastery": mastery,
                    "due": due,
                    "times_asked": asked,
                    "accuracy_pct": round((prog.times_correct or 0) / max(1, asked) * 100, 1),
                },
            )
        )

    scored.sort(key=lambda x: x[0], reverse=True)
    if not scored and not keywords:
        for prog in rows:
            word = words_by_id.get(prog.word_id)
            if not word:
                continue
            asked = prog.times_asked or 0
            mastery = prog.mastery or 0
            if asked == 0 or mastery >= MASTERY_MASTERED:
                continue
            due = (
                prog.due_date is not None
                and prog.due_date.replace(tzinfo=timezone.utc) <= now
                and not prog.is_suspended
            )
            scored.append(
                (
                    3 if due else 1,
                    {
                        "word": word.get("word"),
                        "meaning": str(word.get("meaning", ""))[:160],
                        "mastery": mastery,
                        "due": due,
                        "times_asked": asked,
                        "accuracy_pct": round((prog.times_correct or 0) / max(1, asked) * 100, 1),
                    },
                )
            )
        scored.sort(key=lambda x: x[0], reverse=True)

    return [item for _, item in scored[:limit]]


def _extract_sections(text: str, keywords: list[str], *, max_chars: int) -> str:
    if not keywords:
        return _trim(text, max_chars)

    sections = re.split(r"(?=^## )", text, flags=re.MULTILINE)
    hits: list[str] = []
    for section in sections:
        lower = section.lower()
        if any(k in lower for k in keywords):
            hits.append(section.strip())
    if hits:
        return _trim("\n\n".join(hits), max_chars)

    lines = [ln for ln in text.splitlines() if any(k in ln.lower() for k in keywords)]
    if lines:
        return _trim("\n".join(lines[:40]), max_chars)

    return _trim(text, min(max_chars, 1200))


def _lecture_note_entries(
    db: Session,
    user_id: int,
    *,
    keywords: list[str],
    limit: int = 3,
    section_chars: int = 2200,
) -> list[dict[str, Any]]:
    rows = (
        db.query(LectureNote)
        .filter(LectureNote.user_id == user_id)
        .order_by(LectureNote.created_at.desc())
        .limit(24)
        .all()
    )
    if not rows:
        return []

    scored: list[tuple[int, LectureNote]] = []
    for row in rows:
        hay = f"{row.title} {row.topic or ''}".lower()
        score = sum(2 for k in keywords if k in hay) if keywords else 0
        if not keywords:
            score = 1
        elif score == 0:
            from backend.transcripts.library import note_storage_path
            from backend.transcripts.notes_generator import resolve_notes_path

            path = resolve_notes_path(note_storage_path(row))
            if path.is_file():
                try:
                    preview = path.read_text(encoding="utf-8")[:4000].lower()
                    score = sum(1 for k in keywords if k in preview)
                except OSError:
                    score = 0
        if score > 0:
            scored.append((score, row))

    scored.sort(key=lambda x: x[0], reverse=True)
    picked = [row for _, row in scored[:limit]] if scored else rows[: min(limit, 2)]

    entries: list[dict[str, Any]] = []
    for row in picked:
        from backend.transcripts.library import note_storage_path
        from backend.transcripts.notes_generator import resolve_notes_path

        path = resolve_notes_path(note_storage_path(row))
        excerpt = ""
        if path.is_file():
            try:
                raw = path.read_text(encoding="utf-8")
                excerpt = _extract_sections(raw, keywords, max_chars=section_chars)
            except OSError:
                excerpt = ""
        entries.append(
            {
                "title": row.title,
                "topic": row.topic,
                "filename": row.filename,
                "source": row.source,
                "excerpt": excerpt,
            }
        )
    return entries


def _math_entries(db: Session, user_id: int, *, keywords: list[str], limit: int = 8) -> list[dict[str, Any]]:
    rows = (
        db.query(MathAttempt)
        .filter(MathAttempt.user_id == user_id)
        .order_by(MathAttempt.created_at.desc())
        .limit(30)
        .all()
    )
    if not rows:
        return []

    if keywords:
        filtered = [
            r
            for r in rows
            if any(k in r.topic.lower() or k in r.prompt.lower() for k in keywords)
        ]
        rows = filtered or rows[:limit]
    else:
        rows = rows[:limit]

    return [
        {
            "topic": r.topic,
            "prompt": _trim(r.prompt, 120),
            "your_answer": _trim(r.user_answer, 80),
            "correct": r.is_correct,
            "when": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows[:limit]
    ]


def _transcript_snippets(*, keywords: list[str], limit_lines: int = 12, file_limit: int = 2) -> list[dict[str, Any]]:
    if not keywords or not TRANSCRIPTS_DIR.is_dir():
        return []

    files = sorted(TRANSCRIPTS_DIR.glob("*.txt"), key=lambda p: p.stat().st_mtime, reverse=True)
    snippets: list[dict[str, Any]] = []
    for path in files[:file_limit]:
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        hits = [ln.strip() for ln in lines if ln.strip() and any(k in ln.lower() for k in keywords)]
        if hits:
            snippets.append(
                {
                    "file": path.name,
                    "lines": hits[:limit_lines],
                }
            )
    return snippets


def knowledge_index(db: Session, user_id: int) -> dict[str, Any]:
    from backend.behavior.coach_activity import browser_activity_for_coach

    note_count = db.query(LectureNote).filter(LectureNote.user_id == user_id).count()
    vocab_rows = db.query(WordProgress).filter(WordProgress.user_id == user_id).count()
    math_count = db.query(MathAttempt).filter(MathAttempt.user_id == user_id).count()
    transcript_count = len(list(TRANSCRIPTS_DIR.glob("*.txt"))) if TRANSCRIPTS_DIR.is_dir() else 0
    browser = browser_activity_for_coach(db, user_id, limit=1)
    return {
        "lecture_notes": note_count,
        "vocab_progress_rows": vocab_rows,
        "math_attempts": math_count,
        "transcripts_on_disk": transcript_count,
        "browser_events_today": browser.get("events_parsed", 0),
        "browser_source": browser.get("source"),
        "retrieval": (
            "Chat pulls matching note excerpts, weak/due vocab, math history, transcript lines, "
            "and browser activity (YouTube titles, page titles, domains)."
        ),
    }


def _graph_rag_context(
    db: Session,
    user_id: int,
    query: str,
    *,
    top_k: int = 3,
    hops: int = 2,
    max_chars: int = 4000,
) -> dict[str, Any]:
    """GraphRAG retrieval: embed query → cosine node lookup → 2-hop traversal."""
    try:
        from backend.hub.services.knowledge_graph import (  # noqa: PLC0415
            find_nodes_by_query,
            find_related_nodes,
        )
        from backend.models.knowledge_graph import KgObservation  # noqa: PLC0415
    except Exception:  # noqa: BLE001
        return {}

    top_nodes = find_nodes_by_query(db, query, user_id=user_id, top_k=top_k)
    if not top_nodes:
        return {}

    context_parts: list[str] = []
    struggle_hints: list[str] = []

    for node, score in top_nodes:
        # Collect observations for this node
        obs_rows = (
            db.query(KgObservation)
            .filter(KgObservation.node_id == node.id)
            .order_by(KgObservation.timestamp.desc())  # type: ignore[arg-type]
            .limit(10)
            .all()
        )
        fail_count = sum(1 for o in obs_rows if "fail" in (o.interaction_type or ""))
        drop_count = sum(1 for o in obs_rows if o.interaction_type == "focus_drop")

        obs_text = ""
        if fail_count:
            obs_text += f" — {fail_count} quiz/math failures"
        if drop_count:
            obs_text += f", {drop_count} focus drops"
        if fail_count >= 2 or drop_count >= 2:
            struggle_hints.append(node.label)

        # Pull excerpt from note file
        excerpt = ""
        if node.note_path:
            from pathlib import Path  # noqa: PLC0415

            note_path = Path(node.note_path)
            if note_path.is_file():
                try:
                    raw = note_path.read_text(encoding="utf-8")
                    excerpt = _trim(_extract_sections(raw, _tokenize_query(query), max_chars=1200), 1200)
                except OSError:
                    excerpt = ""

        context_parts.append(
            f"[Node: {node.label}] (score={score:.2f}) tag={node.tag_path or '-'}"
            + obs_text
            + (f"\nSource: {node.note_path}" if node.note_path else "")
            + (f"\n{excerpt}" if excerpt else "")
        )

        # 2-hop traversal
        related = find_related_nodes(db, node.id, hops=hops)
        for rel_node in related[:4]:
            context_parts.append(
                f"  [Related: {rel_node.label}] tag={rel_node.tag_path or '-'}"
            )

    return {
        "graph_nodes_matched": len(top_nodes),
        "context": _trim("\n\n".join(context_parts), max_chars),
        "struggle_topics": struggle_hints,
    }


def retrieve_coach_knowledge(
    db: Session,
    user_id: int,
    query: str = "",
    *,
    max_chars: int = _MAX_KB_CHARS,
) -> dict[str, Any]:
    """Build a query-aware knowledge payload for the local LLM.

    Now includes GraphRAG context from the knowledge graph when available.
    """
    keywords = _tokenize_query(query)
    kb: dict[str, Any] = {
        "query": query.strip()[:500] if query else "",
        "query_keywords": keywords,
        "index": knowledge_index(db, user_id),
        "vocab": _vocab_entries(db, user_id, keywords=keywords),
        "lecture_notes": _lecture_note_entries(db, user_id, keywords=keywords),
        "math_recent": _math_entries(db, user_id, keywords=keywords),
        "transcript_snippets": _transcript_snippets(keywords=keywords),
    }

    from backend.behavior.coach_activity import browser_activity_for_coach

    kb["browser_activity"] = browser_activity_for_coach(db, user_id, query, limit=18)

    # GraphRAG augmentation — add silently if knowledge graph is populated
    if query:
        try:
            graph_ctx = _graph_rag_context(db, user_id, query)
            if graph_ctx:
                kb["graph_context"] = graph_ctx
        except Exception:  # noqa: BLE001
            pass

    blob = str(kb)
    if len(blob) > max_chars:
        kb["lecture_notes"] = kb["lecture_notes"][:2]
        for note in kb["lecture_notes"]:
            note["excerpt"] = _trim(note.get("excerpt", ""), 1500)
        kb["vocab"] = kb["vocab"][:12]
        kb["math_recent"] = kb["math_recent"][:5]
        kb["transcript_snippets"] = kb["transcript_snippets"][:1]
        ba = kb.get("browser_activity") or {}
        ba["recent"] = (ba.get("recent") or [])[:8]
        kb["browser_activity"] = ba

    return kb
