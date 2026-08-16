"""Live Captions attach must fail fast — never UIA-scan by title (hangs on Chrome/DeLive)."""

from __future__ import annotations

import time

import pytest

from backend.transcripts import live_captions as lc


def test_connect_does_not_title_scan_when_lc_missing(monkeypatch):
    monkeypatch.setattr(lc, "find_live_captions_hwnd", lambda: None)
    monkeypatch.setattr(lc, "find_live_captions_pid", lambda: None)
    if hasattr(lc, "launch_live_captions"):
        monkeypatch.setattr(lc, "launch_live_captions", lambda: False)

    connects: list[dict] = []

    class FakeApp:
        def __init__(self, backend=None):
            pass

        def connect(self, **kwargs):
            connects.append(kwargs)
            raise RuntimeError("no window")

    monkeypatch.setattr("pywinauto.application.Application", FakeApp)

    scraper = lc.LiveCaptionsScraper()
    started = time.monotonic()
    with pytest.raises(RuntimeError, match="Win\\+Ctrl\\+L"):
        scraper._connect_uia()
    assert time.monotonic() - started < 2.0
    assert not any("title" in c for c in connects)


def test_connect_tries_launch_then_attaches(monkeypatch):
    state = {"hwnd": None}

    monkeypatch.setattr(lc, "find_live_captions_hwnd", lambda: state["hwnd"])
    monkeypatch.setattr(lc, "find_live_captions_pid", lambda: None)

    launched = {"n": 0}

    def fake_launch() -> bool:
        launched["n"] += 1
        state["hwnd"] = 4242
        return True

    monkeypatch.setattr(lc, "launch_live_captions", fake_launch)
    monkeypatch.setattr(lc, "_open_uia_caption_block", lambda hwnd: f"block-{hwnd}")

    scraper = lc.LiveCaptionsScraper()
    assert scraper._connect_uia() == "block-4242"
    assert launched["n"] == 1
