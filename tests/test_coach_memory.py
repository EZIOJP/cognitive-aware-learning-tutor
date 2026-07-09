"""Coach memory — bounded facts + per-day summaries."""

from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.db.base import Base
from backend.hub.services import coach_memory as cm
from backend.models import CoachMemory


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


def _daily(day: str, minutes: int = 60) -> dict:
    return {
        "date": day,
        "life_score": 70,
        "study_minutes": minutes,
        "productive_minutes": 45,
        "sleep_minutes": 420,
        "vocab_events": 3,
        "math_attempts": 1,
        "overall_performance": "good",
    }


def test_day_summary_upsert_is_one_row_per_day(db):
    today = date.today().isoformat()
    cm.upsert_today_summary(db, 1, _daily(today, minutes=30))
    cm.upsert_today_summary(db, 1, _daily(today, minutes=90))
    rows = db.query(CoachMemory).filter(CoachMemory.kind == "day_summary").all()
    assert len(rows) == 1
    assert "study 90m" in rows[0].content


def test_day_summaries_pruned_to_cap(db):
    for i in range(cm.MAX_DAY_SUMMARIES + 5):
        day = (date.today() - timedelta(days=i)).isoformat()
        cm.upsert_today_summary(db, 1, _daily(day))
    count = db.query(CoachMemory).filter(CoachMemory.kind == "day_summary").count()
    assert count == cm.MAX_DAY_SUMMARIES


def test_store_facts_dedupes_and_caps(db):
    added = cm.store_facts(db, 1, ["Exam on July 20", "exam on july 20!", "Prefers morning study"])
    assert added == 2

    many = [f"Unique durable fact number {i} about studying" for i in range(cm.MAX_FACTS + 10)]
    cm.store_facts(db, 1, many)
    count = db.query(CoachMemory).filter(CoachMemory.kind == "fact").count()
    assert count == cm.MAX_FACTS


def test_store_facts_skips_junk(db):
    added = cm.store_facts(db, 1, ["", "ok", "   "])
    assert added == 0


def test_get_memory_context_shape(db):
    cm.store_facts(db, 1, ["Exam on July 20"])
    cm.upsert_today_summary(db, 1, _daily(date.today().isoformat()))
    ctx = cm.get_memory_context(db, 1)
    assert ctx["remembered_facts"] == ["Exam on July 20"]
    assert len(ctx["recent_days"]) == 1
    assert ctx["recent_days"][0]["day"] == date.today().isoformat()


def test_extract_returns_empty_when_llm_off(monkeypatch):
    monkeypatch.setattr("backend.core.ollama_client.ollama_available", lambda *a, **k: False)
    assert cm.extract_facts_from_exchange("I have an exam on the 20th of July", "Good luck!") == []


def test_extract_parses_json(monkeypatch):
    monkeypatch.setattr("backend.core.ollama_client.ollama_available", lambda *a, **k: True)
    monkeypatch.setattr(
        "backend.core.ollama_client.ollama_generate",
        lambda *a, **k: '{"facts": ["Exam on July 20", 42, "Prefers morning study"]}',
    )
    facts = cm.extract_facts_from_exchange("I have an exam on the 20th and I study best in mornings", "Noted!")
    assert facts == ["Exam on July 20", "Prefers morning study"]
