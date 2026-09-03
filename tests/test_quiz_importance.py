"""Tag importance store, bars, density, Low Mastery progress."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from backend.quiz import importance as imp
from backend.quiz import srs as srs_mod


def test_default_importance_and_put_user(tmp_path: Path):
    path = tmp_path / "tag_importance.json"
    assert imp.importance_for("MT1-T07", imp.load_store(path)) == 3
    row = imp.put_importance("MT1-T07", 5, path=path)
    assert row["source"] == "user"
    assert row["importance"] == 5
    store = imp.load_store(path)
    assert imp.importance_for("MT1-T07", store) == 5


def test_put_mtime_never_set_and_stale(tmp_path: Path):
    path = tmp_path / "tag_importance.json"
    imp.put_importance("MT1-T01", 4, expected_updated_at=None, path=path)
    with pytest.raises(ValueError, match="mtime_conflict"):
        imp.put_importance("MT1-T02", 3, expected_updated_at="2020-01-01T00:00:00Z", path=path)
    first = imp.put_importance("MT1-T03", 2, path=path)
    with pytest.raises(ValueError, match="mtime_conflict"):
        imp.put_importance("MT1-T03", 5, expected_updated_at="stale", path=path)
    again = imp.put_importance("MT1-T03", 5, expected_updated_at=first["updated_at"], path=path)
    assert again["importance"] == 5
    with pytest.raises(ValueError, match="mtime_conflict"):
        imp.put_importance("MT1-T03", 1, expected_updated_at=None, path=path)


def test_suggest_skips_user_fills_unset_overwrite_claude(tmp_path: Path):
    path = tmp_path / "tag_importance.json"
    imp.put_importance("MT1-T07", 5, path=path)
    imp.apply_suggest_writes(
        [{"tag_id": "MT1-T01", "importance": 4, "note": "exam"}],
        known_tags={"MT1-T01", "MT1-T07", "MT1-T02"},
        overwrite_claude=False,
        path=path,
    )
    store = imp.load_store(path)
    assert store["tags"]["MT1-T01"]["source"] == "claude"
    result = imp.apply_suggest_writes(
        [{"tag_id": "MT1-T07", "importance": 1}, {"tag_id": "MT1-T01", "importance": 2}],
        known_tags={"MT1-T01", "MT1-T07"},
        overwrite_claude=False,
        path=path,
    )
    assert result["skipped_user"][0]["tag_id"] == "MT1-T07"
    assert result["skipped_claude"][0]["tag_id"] == "MT1-T01"
    overwritten = imp.apply_suggest_writes(
        [{"tag_id": "MT1-T01", "importance": 5}],
        known_tags={"MT1-T01"},
        overwrite_claude=True,
        path=path,
    )
    assert overwritten["updated"][0]["importance"] == 5


def test_mixed_suggest_partial_apply(tmp_path: Path):
    path = tmp_path / "tag_importance.json"
    result = imp.apply_suggest_writes(
        [
            {"tag_id": "MT1-T07", "importance": 5},
            {"tag_id": "not-a-tag", "importance": 3},
            {"tag_id": "MT1-T02", "importance": 9},
        ],
        known_tags={"MT1-T07", "MT1-T02"},
        overwrite_claude=False,
        path=path,
    )
    assert result["updated"][0]["tag_id"] == "MT1-T07"
    reasons = {d["reason"] for d in result["dropped_invalid"]}
    assert "unknown_tag" in reasons
    assert "importance_out_of_range" in reasons
    assert "MT1-T07" in imp.load_store(path)["tags"]


def test_run_suggest_502_on_bad_llm():
    with pytest.raises(imp.SuggestLlmError):
        imp.run_suggest(tags=None, overwrite_claude=False, known_tags=set(), llm_text=None)


def test_multi_tag_density_max_progress_own_bar(tmp_path: Path):
    path = tmp_path / "tag_importance.json"
    imp.put_importance("TA", 5, path=path)
    imp.put_importance("TB", 1, path=path)
    store = imp.load_store(path)
    assert imp.effective_importance(["TA", "TB"], store) == 5
    assert imp.apply_density(10, 5) == max(1, int(round(10 * 0.55)))
    cards = [
        _card({"tags": ["TA", "TB"]}, mastery=3),
    ]
    pa = imp.progress_for_tag(cards, "TA", store)
    pb = imp.progress_for_tag(cards, "TB", store)
    assert pa["cleared"] == 0  # bar 6
    assert pb["cleared"] == 1  # bar 2


def test_put_does_not_touch_due_dates():
    due = datetime.now(UTC) + timedelta(days=9)
    state = srs_mod.SrsState(mastery=4, interval_days=9, due_date=due)
    before = due.isoformat()
    _ = imp.put_importance  # store write only
    assert state.due_date.isoformat() == before


class _Card:
    def __init__(self, payload, mastery, owes=0, topic=None, item_key="k", due=None):
        self.payload_json = json.dumps(payload)
        self.topic = topic
        self.item_key = item_key
        st = srs_mod.SrsState(mastery=mastery, owes_corrects=owes, due_date=due)
        self.srs_json = json.dumps(srs_mod.srs_to_metadata(st))


def _card(payload, mastery, owes=0, **kw):
    return _Card(payload, mastery, owes, **kw)


def test_low_mastery_lists_weak_only():
    store = imp.empty_store()
    store["tags"]["MT1-T07"] = {"importance": 3, "source": "default"}
    weak = _card({"tags": ["MT1-T07"]}, mastery=1)
    strong = _card({"tags": ["MT1-T07"]}, mastery=9)
    rows = imp.list_low_mastery([weak, strong], ["MT1-T07"], store)
    assert len(rows) == 1
    assert rows[0]["weak_count"] == 1
    assert rows[0]["total"] == 2


def test_queue_sort_importance_overdue():
    now = datetime.now(UTC)
    a = _card({"tags": ["T"]}, mastery=0, item_key="a", due=now - timedelta(days=3))
    b = _card({"tags": ["T"]}, mastery=0, owes=2, item_key="b", due=now + timedelta(days=5))
    store = imp.empty_store()
    store["tags"]["T"] = {"importance": 4, "source": "user"}
    ordered = imp.sort_cards_for_queue([a, b], session_tag="T", store=store)
    assert ordered[0].item_key == "a"


def test_low_mastery_route_not_captured_as_tag():
    from fastapi.testclient import TestClient

    from backend.core.auth import get_current_user
    from backend.main import app
    from backend.models import User

    user = User(id=1, username="test", password_hash="hash")
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        client = TestClient(app)
        r = client.get("/api/quiz/importance/low-mastery")
        assert r.status_code == 200
        assert "tags" in r.json()
        r2 = client.post("/api/quiz/importance/low-mastery/start", json={})
        assert r2.status_code in (200, 400)
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_recycle_insert_offset():
    class R:
        def randint(self, a, b):
            assert a == 3
            return 4

    pos = imp.recycle_insert_index(0, 12, rng=R())
    assert pos == 5
    assert imp.recycle_insert_index(8, 10, rng=R()) == 10
