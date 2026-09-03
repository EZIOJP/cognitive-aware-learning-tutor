"""Study Loop session gate + content-inspected practice routing."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.db.base import Base
from backend.models.study_loop import StudyLoopSession
from backend.quiz import study_loop as sl


@pytest.fixture()
def db_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[StudyLoopSession.__table__])
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


def test_practice_blocked_until_mark_read(db_session, monkeypatch):
    monkeypatch.setattr(sl, "list_read_cards", lambda **kw: [{"card_id": "n.md::L5-T05", "tag": "L5-T05"}])
    sess = sl.create_loop_session(user_id=1, tag="L5-T05", db=db_session)
    assert sess["read_completed"] is False
    with pytest.raises(ValueError, match="read_required"):
        sl.start_practice(db=db_session, user=None, session_id=sess["session_id"])
    sl.mark_read(user_id=1, session_id=sess["session_id"], db=db_session)
    assert sl.get_session(user_id=1, session_id=sess["session_id"], db=db_session)["read_completed"] is True
    row = db_session.query(StudyLoopSession).filter_by(session_id=sess["session_id"]).one()
    assert row.read_completed is True
    assert "n.md::L5-T05" in (sess.get("read_card_ids") or [])


def test_vocab_only_auto_completes_read(db_session, monkeypatch):
    monkeypatch.setattr(sl, "list_read_cards", lambda **kw: [])
    sess = sl.create_loop_session(user_id=1, tag="vocab.group.1", db=db_session)
    assert sess["read_completed"] is True


def test_resolve_l_tag_with_mcq_is_study_not_math(monkeypatch):
    monkeypatch.setattr(
        sl,
        "list_bank_items_for_tag",
        lambda tag, kinds=None: [{"id": "mcq.l5.q1", "kind": "mcq", "content_kind": "mcq"}],
    )
    monkeypatch.setattr(sl, "math_generators_for_tag", lambda tag: [])
    route = sl.resolve_practice_route("L5-T05")
    assert route.domain == "study"
    assert route.config.get("auto_generate") is False


def test_resolve_empty_l_tag_errors_not_math(monkeypatch):
    monkeypatch.setattr(sl, "list_bank_items_for_tag", lambda tag, kinds=None: [])
    monkeypatch.setattr(sl, "math_generators_for_tag", lambda tag: [])
    with pytest.raises(ValueError, match="no_practice_content"):
        sl.resolve_practice_route("L5-T05")


def test_resolve_coding_only_is_code(monkeypatch):
    monkeypatch.setattr(
        sl,
        "list_bank_items_for_tag",
        lambda tag, kinds=None: [{"id": "code.1", "kind": "coding", "content_kind": "coding"}],
    )
    monkeypatch.setattr(sl, "math_generators_for_tag", lambda tag: [])
    route = sl.resolve_practice_route("L5-T05")
    assert route.domain == "code"
    assert route.config.get("auto_generate") is False


def test_resolve_math_only_is_math(monkeypatch):
    monkeypatch.setattr(
        sl,
        "list_bank_items_for_tag",
        lambda tag, kinds=None: [{"id": "math.1", "kind": "math", "content_kind": "math"}],
    )
    monkeypatch.setattr(sl, "math_generators_for_tag", lambda tag: [])
    route = sl.resolve_practice_route("MT1-T02")
    assert route.domain == "math"
    assert route.config.get("note_topic_id") == "MT1-T02"


def test_resolve_mix_is_mixed(monkeypatch):
    monkeypatch.setattr(
        sl,
        "list_bank_items_for_tag",
        lambda tag, kinds=None: [
            {"id": "mcq.1", "kind": "mcq", "content_kind": "mcq"},
            {"id": "math.1", "kind": "math", "content_kind": "math"},
        ],
    )
    monkeypatch.setattr(sl, "math_generators_for_tag", lambda tag: [])
    route = sl.resolve_practice_route("L5-T05")
    assert route.domain == "mixed"
    assert route.config.get("auto_generate") is False


def test_start_practice_calls_handler_with_route(db_session, monkeypatch):
    monkeypatch.setattr(sl, "list_read_cards", lambda **kw: [])
    monkeypatch.setattr(
        sl,
        "list_bank_items_for_tag",
        lambda tag, kinds=None: [{"id": "mcq.l5.q1", "kind": "mcq", "content_kind": "mcq"}],
    )
    monkeypatch.setattr(sl, "math_generators_for_tag", lambda tag: [])
    called: dict = {}

    def fake_start(db, *, user, domain, config):
        called["domain"] = domain
        called["config"] = config
        called["user_id"] = getattr(user, "id", None)
        return {"session_id": "quiz-sess-1", "domain": domain, "question": {}}

    monkeypatch.setattr(sl.handler, "start_session", fake_start)
    sess = sl.create_loop_session(user_id=1, tag="L5-T05", db=db_session)
    user = type("U", (), {"id": 1})()
    out = sl.start_practice(db=db_session, user=user, session_id=sess["session_id"])
    assert called["domain"] == "study"
    assert called["config"].get("auto_generate") is False
    assert out["practice_quiz_session_id"] == "quiz-sess-1"
    assert out["domain"] == "study"
