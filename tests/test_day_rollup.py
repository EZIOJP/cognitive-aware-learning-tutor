"""P5c day_rollup reader — prefer enforcer mirror when fresh."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta

from backend.behavior.day_rollup import (
    load_fresh_day_rollup,
    productive_minutes_from_rollup,
    productive_seconds_from_rollup,
)


def _write_rollup(path, *, day: date, mins: int, updated: datetime):
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "local_date": day.isoformat(),
                "updated_at": updated.strftime("%Y-%m-%dT%H:%M:%S"),
                "productive_minutes": mins,
                "productive_seconds": mins * 60,
                "threshold": 60,
                "source": "calt_enforcer",
            }
        ),
        encoding="utf-8",
    )


def test_fresh_rollup_preferred(tmp_path, monkeypatch):
    today = date.today()
    path = tmp_path / "day_rollup.json"
    _write_rollup(path, day=today, mins=77, updated=datetime.now())
    monkeypatch.setattr("backend.behavior.day_rollup._PATH", path)

    hit = load_fresh_day_rollup(today)
    assert hit is not None
    assert hit["productive_minutes"] == 77
    assert productive_minutes_from_rollup(today) == 77
    assert productive_seconds_from_rollup(today) == 77 * 60


def test_stale_rollup_falls_back(tmp_path, monkeypatch):
    today = date.today()
    path = tmp_path / "day_rollup.json"
    stale = datetime.now() - timedelta(seconds=500)
    _write_rollup(path, day=today, mins=99, updated=stale)
    monkeypatch.setattr("backend.behavior.day_rollup._PATH", path)

    assert load_fresh_day_rollup(today, max_age_s=120) is None
    assert productive_minutes_from_rollup(today) is None


def test_wrong_day_falls_back(tmp_path, monkeypatch):
    path = tmp_path / "day_rollup.json"
    _write_rollup(path, day=date(2020, 1, 1), mins=50, updated=datetime.now())
    monkeypatch.setattr("backend.behavior.day_rollup._PATH", path)

    assert load_fresh_day_rollup(date.today()) is None


def test_goals_alerts_uses_rollup_productive(db_session, tmp_path, monkeypatch):
    from datetime import date as date_cls

    from backend.behavior.goals_alerts import build_goals_status

    today = date_cls.today()
    path = tmp_path / "day_rollup.json"
    _write_rollup(path, day=today, mins=12, updated=datetime.now())
    monkeypatch.setattr("backend.behavior.day_rollup._PATH", path)

    status = build_goals_status(db_session, [1], today, user_id=1)
    assert status["productive_seconds"] == 12 * 60
    assert status["productive_source"] == "day_rollup"
    assert status["goals"][0]["current_seconds"] == 12 * 60
