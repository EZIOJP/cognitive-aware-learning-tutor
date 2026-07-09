"""Bounded long-term memory for the AI coach.

Two kinds of rows, both hard-capped so context never balloons:
- day_summary: one compact line per day linking that day's hub data (last 14 days kept)
- fact: durable items extracted from chat by a light-tier LLM (max 30 kept)

Injected into the coach context as a small `memory` block (~2-3k chars max).
"""

from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from backend.models import CoachMemory

log = logging.getLogger(__name__)

MAX_FACTS = 30
MAX_DAY_SUMMARIES = 14
FACT_MAX_CHARS = 200
DAY_SUMMARY_MAX_CHARS = 300
_JSON_BLOCK = re.compile(r"\{[\s\S]*\}")

_EXTRACT_PROMPT = """From this study-coach chat exchange, extract durable facts worth remembering
about the student for future sessions: goals, exam/assignment deadlines, preferences,
recurring struggles, life events that affect studying.

Rules:
- Only facts that stay relevant beyond today. Skip small talk, one-off questions, and anything already obvious from metrics.
- Each fact one short sentence, max 20 words.
- If nothing is worth remembering, return an empty list.

Return JSON only: {"facts": ["...", "..."]}

Student: {user_msg}
Coach: {reply}"""


def _day_summary_line(daily: dict) -> str:
    """Deterministic one-line link of the day's hub data — free and always available."""
    parts = [
        f"life {daily.get('life_score', 0)}",
        f"study {daily.get('study_minutes', 0)}m",
        f"productive {daily.get('productive_minutes', 0)}m",
        f"sleep {daily.get('sleep_minutes', 0)}m",
        f"vocab {daily.get('vocab_events', 0)}",
        f"math {daily.get('math_attempts', 0)}",
        str(daily.get("overall_performance", "")),
    ]
    return " · ".join(p for p in parts if p)[:DAY_SUMMARY_MAX_CHARS]


def upsert_today_summary(db: Session, user_id: int, daily: dict) -> None:
    """Keep one row per day with the latest metrics line; prune beyond MAX_DAY_SUMMARIES."""
    today = (daily.get("date") or date.today().isoformat())[:10]
    line = _day_summary_line(daily)
    row = (
        db.query(CoachMemory)
        .filter(CoachMemory.user_id == user_id, CoachMemory.kind == "day_summary", CoachMemory.day == today)
        .first()
    )
    if row is None:
        db.add(CoachMemory(user_id=user_id, kind="day_summary", day=today, content=line))
    else:
        row.content = line
        row.updated_at = datetime.now(timezone.utc)
    _prune(db, user_id, kind="day_summary", keep=MAX_DAY_SUMMARIES)
    db.commit()


def _prune(db: Session, user_id: int, *, kind: str, keep: int) -> None:
    rows = (
        db.query(CoachMemory)
        .filter(CoachMemory.user_id == user_id, CoachMemory.kind == kind)
        .order_by(CoachMemory.updated_at.desc(), CoachMemory.id.desc())
        .all()
    )
    for stale in rows[keep:]:
        db.delete(stale)


def _normalize(text: str) -> str:
    return re.sub(r"\W+", " ", text.lower()).strip()


def store_facts(db: Session, user_id: int, facts: list[str]) -> int:
    """Add new facts, skipping near-duplicates; prune oldest beyond MAX_FACTS."""
    existing = (
        db.query(CoachMemory)
        .filter(CoachMemory.user_id == user_id, CoachMemory.kind == "fact")
        .all()
    )
    known = {_normalize(r.content) for r in existing}
    added = 0
    for fact in facts:
        clean = str(fact).strip()[:FACT_MAX_CHARS]
        if len(clean) < 8:
            continue
        norm = _normalize(clean)
        if not norm or norm in known:
            continue
        db.add(CoachMemory(user_id=user_id, kind="fact", content=clean))
        known.add(norm)
        added += 1
    if added:
        _prune(db, user_id, kind="fact", keep=MAX_FACTS)
    db.commit()
    return added


def extract_facts_from_exchange(user_msg: str, reply: str) -> list[str]:
    """Light-tier LLM pass; returns [] when the LLM is off or finds nothing."""
    from backend.core.ollama_client import ollama_available, ollama_generate

    if not ollama_available() or len(user_msg.strip()) < 20:
        return []
    prompt = _EXTRACT_PROMPT.replace("{user_msg}", user_msg[:2000]).replace("{reply}", reply[:2000])
    raw = ollama_generate(prompt, timeout=45.0, task="memory_extract")
    if not raw:
        return []
    match = _JSON_BLOCK.search(raw)
    if not match:
        return []
    try:
        data = json.loads(match.group())
    except json.JSONDecodeError:
        return []
    facts = data.get("facts") or []
    return [str(f) for f in facts[:5] if isinstance(f, str)]


def remember_exchange(user_id: int, user_msg: str, reply: str) -> None:
    """Best-effort background task after a coach chat reply; owns its DB session."""
    from backend.db.base import SessionLocal

    try:
        facts = extract_facts_from_exchange(user_msg, reply)
        if not facts:
            return
        db = SessionLocal()
        try:
            n = store_facts(db, user_id, facts)
            if n:
                log.info("coach memory: stored %d new fact(s) for user %s", n, user_id)
        finally:
            db.close()
    except Exception:  # noqa: BLE001
        log.warning("coach memory extraction failed", exc_info=True)


def get_memory_context(db: Session, user_id: int) -> dict:
    """Compact memory block for the coach prompt — bounded regardless of history size."""
    facts = (
        db.query(CoachMemory)
        .filter(CoachMemory.user_id == user_id, CoachMemory.kind == "fact")
        .order_by(CoachMemory.updated_at.desc())
        .limit(MAX_FACTS)
        .all()
    )
    days = (
        db.query(CoachMemory)
        .filter(CoachMemory.user_id == user_id, CoachMemory.kind == "day_summary")
        .order_by(CoachMemory.day.desc())
        .limit(MAX_DAY_SUMMARIES)
        .all()
    )
    return {
        "remembered_facts": [r.content for r in facts],
        "recent_days": [{"day": r.day, "summary": r.content} for r in days],
    }
