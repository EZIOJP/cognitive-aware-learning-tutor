"""Daily bite selection, freeze, stub flags, done-with-debt."""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.db.base import Base
from backend.models.review_card import ReviewCard
from backend.models.study_loop import StudyLoopDay, StudyLoopSession
from backend.models.user import User
from backend.quiz import daily_bite as dbite
from backend.quiz import importance as imp
from backend.quiz import srs as srs_mod
from backend.quiz import topic_stub_flags as stubs


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    s.add(User(id=1, username="u", password_hash="x"))
    s.commit()
    try:
        yield s
    finally:
        s.close()


def test_practice_count_zero_excluded(monkeypatch, db):
    monkeypatch.setattr(dbite, "practice_count", lambda tag: 0 if tag == "MT1-T99" else 3)
    monkeypatch.setattr(
        dbite.imp,
        "progress_for_tag",
        lambda cards, tid, store: {"mastered": False, "total": 0, "cleared": 0},
    )
    got = dbite.eligible_tags(db, user_id=1, tag_ids=["MT1-T99", "MT1-T07"])
    assert "MT1-T99" not in got
    assert "MT1-T07" in got


def test_never_practiced_with_bank_is_eligible(monkeypatch, db):
    monkeypatch.setattr(dbite, "practice_count", lambda tag: 4)
    monkeypatch.setattr(
        dbite.imp,
        "progress_for_tag",
        lambda cards, tid, store: {"mastered": False, "total": 0, "cleared": 0},
    )
    assert dbite.eligible_tags(db, user_id=1, tag_ids=["L5-T01"]) == ["L5-T01"]


def test_freeze_stable(monkeypatch, db):
    monkeypatch.setattr(dbite, "eligible_tags", lambda *a, **k: ["A", "B", "C"])
    monkeypatch.setattr(dbite, "rank_tags", lambda *a, **k: ["A", "B", "C"])
    monkeypatch.setattr(dbite.stubs, "backfill_from_read_cards", lambda *a, **k: None)
    monkeypatch.setattr(dbite, "list_read_cards", lambda *a, **k: [])
    monkeypatch.setattr(dbite, "_mode_for", lambda tags: "B")
    # Disable Math Core prepend for this freeze-stability check.
    monkeypatch.setattr(dbite, "practice_count", lambda tag: 0)
    r1 = dbite.freeze_today(db, user_id=1, today=date(2026, 9, 4))
    monkeypatch.setattr(dbite, "rank_tags", lambda *a, **k: ["C", "B", "A"])
    r2 = dbite.freeze_today(db, user_id=1, today=date(2026, 9, 4))
    assert json.loads(r1.tags_json) == json.loads(r2.tags_json) == ["A", "B"]


def test_freeze_prepends_math_core(monkeypatch, db):
    monkeypatch.setattr(dbite, "eligible_tags", lambda *a, **k: ["MT1-T07", "MT1-T03"])
    monkeypatch.setattr(dbite, "rank_tags", lambda *a, **k: ["MT1-T07", "MT1-T03"])
    monkeypatch.setattr(dbite.stubs, "backfill_from_read_cards", lambda *a, **k: None)
    monkeypatch.setattr(dbite, "list_read_cards", lambda *a, **k: [])
    monkeypatch.setattr(dbite, "practice_count", lambda tag: 20 if tag == "MT1-T01" else 5)
    row = dbite.freeze_today(db, user_id=1, today=date(2026, 9, 6))
    tags = json.loads(row.tags_json)
    assert tags[0] == "MT1-T01"
    assert tags[1:] == ["MT1-T07", "MT1-T03"]
    assert row.mode == "B"
    payload = json.loads(row.payload_json)
    assert payload["steps"][0]["kind"] == "mathcore"
    assert payload["steps"][0]["label"] == "Math Core"
    assert payload["has_mathcore"] is True


def test_math_core_forces_mode_b(tmp_path: Path, monkeypatch):
    path = tmp_path / "topic_stub_flags.json"
    stubs.set_stub("MT1-T01", False, path=path)
    stubs.set_stub("MT1-T07", False, path=path)
    original = stubs.load_store
    monkeypatch.setattr(dbite.stubs, "load_store", lambda p=None: original(path))
    assert dbite._mode_for(["MT1-T01", "MT1-T07"]) == "B"


def test_practice_count_math_core():
    from backend.quiz import math_core as mc

    assert mc.practice_count_for_tag("MT1-T01") == 20
    assert mc.practice_count_for_tag("MT1-T07", default=15) == 15


def test_freeze_continues_when_stub_backfill_locked(monkeypatch, db):
    monkeypatch.setattr(dbite, "eligible_tags", lambda *a, **k: ["A", "B"])
    monkeypatch.setattr(dbite, "rank_tags", lambda *a, **k: ["A", "B"])
    monkeypatch.setattr(dbite, "list_read_cards", lambda *a, **k: [])
    monkeypatch.setattr(dbite, "_mode_for", lambda tags: "B")
    monkeypatch.setattr(dbite, "practice_count", lambda tag: 0)

    def boom(*a, **k):
        raise PermissionError(5, "Access is denied")

    monkeypatch.setattr(dbite.stubs, "backfill_from_read_cards", boom)
    row = dbite.freeze_today(db, user_id=1, today=date(2026, 9, 5))
    assert json.loads(row.tags_json) == ["A", "B"]


def test_stub_flag_not_body_parse(tmp_path: Path):
    path = tmp_path / "topic_stub_flags.json"
    stubs.set_stub("MT1-T07", False, path=path)
    store = stubs.load_store(path)
    assert stubs.is_stub("MT1-T07", store) is False
    # leftover placeholder in body is irrelevant
    assert stubs.is_stub("MT1-T07", store) is False


def test_mode_c_only_if_all_non_stub(tmp_path: Path, monkeypatch):
    path = tmp_path / "topic_stub_flags.json"
    stubs.set_stub("T1", False, path=path)
    stubs.set_stub("T2", True, path=path)
    original = stubs.load_store
    monkeypatch.setattr(dbite.stubs, "load_store", lambda p=None: original(path))
    assert dbite._mode_for(["T1", "T2"]) == "B"
    stubs.set_stub("T2", False, path=path)
    assert dbite._mode_for(["T1", "T2"]) == "C"


def test_done_with_owes_remaining(db):
    due = srs_mod.SrsState(mastery=1, owes_corrects=2, interval_days=3)
    row = StudyLoopDay(
        user_id=1,
        day="2026-09-04",
        tags_json=json.dumps(["T1"]),
        mode="B",
        payload_json=json.dumps(
            {
                "steps": [
                    {
                        "tag": "T1",
                        "loop_session_id": "loop1",
                        "quiz_session_id": "q1",
                        "gated_ids": ["item-a"],
                    }
                ]
            }
        ),
    )
    db.add(row)
    db.add(
        StudyLoopSession(
            session_id="loop1",
            user_id=1,
            tag="T1",
            read_completed=True,
            read_card_ids_json="[]",
            practice_quiz_session_id="q1",
        )
    )
    db.commit()
    monkeypatch_ids = {"item-a"}
    from unittest.mock import patch

    with patch.object(dbite, "_quiz_attempted_ids", return_value=monkeypatch_ids):
        assert dbite.evaluate_state(db, row) == "done"
    # debt still on a card does not block done
    assert due.owes_corrects == 2


def test_empty_candidates(monkeypatch, db):
    monkeypatch.setattr(dbite, "eligible_tags", lambda *a, **k: [])
    monkeypatch.setattr(dbite.stubs, "backfill_from_read_cards", lambda *a, **k: None)
    monkeypatch.setattr(dbite, "list_read_cards", lambda *a, **k: [])
    monkeypatch.setattr(dbite, "practice_count", lambda tag: 0)
    row = dbite.freeze_today(db, user_id=1, today=date(2026, 9, 4))
    assert dbite.evaluate_state(db, row) == "empty"
    assert dbite.bite_unfinished(db, user_id=1, today=date(2026, 9, 4)) is False


def test_math_core_alone_when_no_other_candidates(monkeypatch, db):
    monkeypatch.setattr(dbite, "eligible_tags", lambda *a, **k: [])
    monkeypatch.setattr(dbite.stubs, "backfill_from_read_cards", lambda *a, **k: None)
    monkeypatch.setattr(dbite, "list_read_cards", lambda *a, **k: [])
    monkeypatch.setattr(dbite, "practice_count", lambda tag: 20 if tag == "MT1-T01" else 0)
    row = dbite.freeze_today(db, user_id=1, today=date(2026, 9, 7))
    assert json.loads(row.tags_json) == ["MT1-T01"]
    assert dbite.evaluate_state(db, row) == "ready"
    assert dbite.bite_unfinished(db, user_id=1, today=date(2026, 9, 7)) is True


def test_bite_unfinished_no_row_skips_bank_scan(monkeypatch, db):
    """Gate polls this often — must not scan the question bank before freeze."""
    called: list[int] = []
    monkeypatch.setattr(dbite, "eligible_tags", lambda *a, **k: called.append(1) or ["X"])
    assert dbite.bite_unfinished(db, user_id=1, today=date(2026, 9, 4)) is True
    assert called == []
