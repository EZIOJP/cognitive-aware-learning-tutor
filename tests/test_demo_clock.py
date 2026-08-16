"""Demo clock — read-only time travel."""

from __future__ import annotations

from datetime import datetime

from backend.behavior import demo_clock as dc
from backend.planner.service import local_tz


def test_demo_clock_set_and_clear(tmp_path, monkeypatch):
    path = tmp_path / "demo_clock.json"
    monkeypatch.setattr(dc, "_STATE_PATH", path)
    dc.clear()
    assert dc.is_demo() is False
    real = datetime.now(local_tz())
    st = dc.set_clock(enabled=True, now_iso=real.replace(hour=5, minute=30).isoformat())
    assert st["enabled"] is True
    assert dc.is_demo() is True
    assert dc.now_local().hour == 5
    dc.clear()
    assert dc.is_demo() is False


def test_demo_blocks_writes(tmp_path, monkeypatch):
    path = tmp_path / "demo_clock.json"
    monkeypatch.setattr(dc, "_STATE_PATH", path)
    dc.set_clock(enabled=True, now_iso=datetime.now(local_tz()).isoformat())
    try:
        dc.assert_not_demo_writes()
        assert False, "expected RuntimeError"
    except RuntimeError:
        pass
    finally:
        dc.clear()
