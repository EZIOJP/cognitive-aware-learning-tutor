"""Hard rewrite today: Other (Browser) Scaler → Coursework / Study."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.behavior.category_scores import seed_category_scores
from backend.behavior.distraction_gate import compute_distraction_gate
from backend.behavior.reclassify_today import derive_session_category, reclassify_today
from backend.db.base import Base
from backend.models.timetable import TrackedSession
from backend.models.user import User


def _db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    db.add(User(id=1, username="reclassify_test", password_hash="x"))
    db.commit()
    seed_category_scores(db)
    return db


def test_derive_scaler_domain_is_coursework():
    cat, src = derive_session_category(
        source="extension",
        app_name="scaler.com",
        window_title="Topics | NumPy",
        url="https://www.scaler.com/topics/course/numpy/",
        domain="scaler.com",
    )
    assert "Coursework" in cat or "Study" in cat
    assert src == "reclassify_today"


def test_derive_lecture_notes_title_is_study_browser():
    cat, _src = derive_session_category(
        source="desktop_tracker",
        app_name="msedge.exe",
        window_title="numpy lecture notes - Personal - Microsoft Edge",
    )
    assert cat == "Study (Browser)"


def test_reclassify_today_fixes_other_browser_scaler_session():
    db = _db()
    now = datetime.now(UTC)
    start = now - timedelta(minutes=30)
    row = TrackedSession(
        session_id="ext-fake-scaler-other",
        user_id=1,
        start_time=start,
        end_time=now,
        source="extension",
        category="Other (Browser)",
        app_name="scaler.com",
        window_title="Topics | NumPy · /topics/course/numpy",
        category_source="extension_label",
    )
    db.add(row)
    db.commit()

    before = compute_distraction_gate(db, 1)
    assert before["productive_minutes"] < 10  # Other (Browser) is not productive

    result = reclassify_today(db, user_id=1, commit=True)
    db.refresh(row)

    assert result["updated"] >= 1
    assert "Coursework" in (row.category or "") or "Study" in (row.category or "")
    assert row.category_source in ("reclassify_today", "policy_override")
    assert row.category != "Other (Browser)"

    after = compute_distraction_gate(db, 1)
    assert after["productive_minutes"] >= 20
    assert after["productive_minutes"] > before["productive_minutes"]
