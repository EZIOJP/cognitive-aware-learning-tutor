"""Live caption idle-stop behavior."""

from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock

from backend.transcripts.live_captions import LiveCaptionsScraper


def test_idle_stop_after_no_new_segments(monkeypatch):
    scraper = LiveCaptionsScraper(poll_interval=0.05)
    calls = {"n": 0}

    def fake_poll(_block) -> bool:
        calls["n"] += 1
        if calls["n"] == 1:
            scraper._record("hello world")
            return True
        return False

    monkeypatch.setattr(scraper, "_connect_uia", lambda: MagicMock())
    monkeypatch.setattr(scraper, "poll_once", fake_poll)

    started = time.monotonic()
    scraper.run(max_seconds=30.0, idle_seconds=0.15)
    elapsed = time.monotonic() - started

    assert len(scraper.segments) >= 1
    assert elapsed < 2.0


def test_stop_event_ends_capture(monkeypatch):
    scraper = LiveCaptionsScraper(poll_interval=0.05)
    stop = threading.Event()

    monkeypatch.setattr(scraper, "_connect_uia", lambda: MagicMock())
    monkeypatch.setattr(scraper, "poll_once", lambda _b: False)

    def trigger_stop() -> None:
        time.sleep(0.1)
        stop.set()

    threading.Thread(target=trigger_stop, daemon=True).start()
    scraper.run(idle_seconds=None, max_seconds=60.0, stop_event=stop)
    assert stop.is_set()


def test_doubt_phrase_inserts_session_break():
    scraper = LiveCaptionsScraper()
    scraper._record("Any questions on this slide?")
    assert "--- session break ---" in scraper.segments
    assert any("questions" in s.lower() for s in scraper.segments)
