"""Extension URL sessions + CALT SPA productive lanes (notes / quiz / vocab / math)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.behavior.category_scores import seed_category_scores
from backend.behavior.distraction_gate import compute_distraction_gate
from backend.behavior.study_presence import (
    apply_study_presence,
    path_is_study,
    resolve_calt_lane,
)
from backend.behavior.tracker_classify import classify_app
from backend.db.base import Base
from backend.models.user import User
from backend.timetable.tracker_bridge import ingest_behavior_session


def _db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    db.add(User(id=1, username="study_credit", password_hash="x"))
    db.commit()
    seed_category_scores(db)
    return db


def test_path_is_study_lecture_notes_only():
    assert path_is_study("/lecture-notes")
    assert path_is_study("/lecture-notes/foo")
    assert not path_is_study("/bible")
    assert not path_is_study("/quiz")
    assert not path_is_study("/gre")
    assert not path_is_study("/vocab")
    assert not path_is_study("/productivity")
    assert not path_is_study("/login")


def test_resolve_calt_lane_productive_only():
    assert resolve_calt_lane("/lecture-notes") == "lecture_notes"
    assert resolve_calt_lane("/review") == "quiz"
    assert resolve_calt_lane("/gre-vocab") == "vocab"
    assert resolve_calt_lane("/math-tutor") == "math"
    assert resolve_calt_lane("/bible") is None
    assert resolve_calt_lane("/productivity") is None
    assert resolve_calt_lane("/login") is None


def test_extension_scaler_url_ingested_and_counts():
    db = _db()
    now = datetime.now(UTC)
    start_ms = int((now - timedelta(minutes=20)).timestamp() * 1000)
    end_ms = int(now.timestamp() * 1000)
    row = ingest_behavior_session(
        db,
        user_id=1,
        payload={
            "type": "SESSION_END",
            "source": "extension",
            "timestamp": start_ms,
            "end_timestamp": end_ms,
            "duration_seconds": 20 * 60,
            "url": "https://www.scaler.com/topics/course/numpy/",
            "domain": "scaler.com",
            "title": "Topics | NumPy",
            "category": "Browsing",  # wrong client label — server reclassifies
        },
    )
    assert row is not None
    assert row.source == "extension"
    assert row.app_name == "scaler.com"
    assert row.window_title and "NumPy" in row.window_title
    assert "/topics/course/numpy" in (row.window_title or "")
    assert "Coursework" in (row.category or "") or "Study" in (row.category or "")
    gate = compute_distraction_gate(db, 1)
    assert gate["productive_minutes"] >= 15


def test_spa_without_notes_loaded_credits_zero():
    db = _db()
    out = apply_study_presence(
        db, user_id=1, path="/lecture-notes", focused=True, client="web", title="Lecture Notes"
    )
    assert out["ok"] is True
    assert out["credited_seconds"] == 0
    assert out.get("reason") == "notes_not_reading"


def test_spa_bible_path_credits_zero_spiritual():
    db = _db()
    out = apply_study_presence(
        db,
        user_id=1,
        path="/bible",
        focused=True,
        client="web",
        notes_loaded=True,
        reading=True,
    )
    assert out["credited_seconds"] == 0
    assert out.get("reason") == "spiritual_not_productive"


def test_spa_unfocused_credits_zero():
    db = _db()
    out = apply_study_presence(
        db,
        user_id=1,
        path="/review",
        focused=False,
        client="web",
    )
    assert out["credited_seconds"] == 0
    assert out.get("reason") == "unfocused"


def test_spa_quiz_vocab_math_credit():
    db = _db()
    for path, lane in (
        ("/review", "quiz"),
        ("/gre-vocab", "vocab"),
        ("/math-tutor", "math"),
    ):
        out = apply_study_presence(
            db,
            user_id=1,
            path=path,
            focused=True,
            client="web",
            title=path,
        )
        assert out["ok"] is True, path
        assert out["credited_seconds"] >= 15, path
        assert out.get("lane") == lane, path


def test_spa_presence_credits_when_notes_reading():
    db = _db()
    out = apply_study_presence(
        db,
        user_id=1,
        path="/lecture-notes",
        focused=True,
        client="ipad",
        title="NumPy notes",
        notes_loaded=True,
        reading=True,
        document_id="lecture_2/numpy_lecture_notes.md",
    )
    assert out["ok"] is True
    assert out["credited_seconds"] >= 15
    from backend.models.timetable import TrackedSession

    rows = db.query(TrackedSession).filter(TrackedSession.source == "calt_spa").all()
    assert len(rows) >= 1
    assert rows[0].category == "Study (Browser)"
    assert "Lecture Notes" in (rows[0].window_title or "")


def test_bible_pdf_classifies_spiritual_not_study():
    cat, score = classify_app("FoxitPDFReader.exe", "good-news-bible.pdf - Foxit")
    assert cat == "Spiritual"
    assert score < 60
