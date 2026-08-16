"""Soft-lock must never kill Edge; Pear/YouTube Music is music, not a browser."""

from __future__ import annotations

from backend.behavior.browser_catalog import (
    is_music_player_exe,
    is_unauthorized_browser,
    protected_browser_exes,
    unauthorized_kind,
)
from backend.behavior.distraction_gate import (
    is_protected_exe,
    should_hard_block,
    terminate_blocked_process,
)


def test_pear_youtube_music_not_unauthorized_browser():
    for exe in (
        "YouTube Music.exe",
        "youtube-music.exe",
        "Pear Desktop.exe",
        "pear-desktop.exe",
        "YouTube Music",
    ):
        assert is_music_player_exe(exe), exe
        assert not is_unauthorized_browser(exe), exe
        assert unauthorized_kind(exe) is None, exe
        assert is_protected_exe(exe), exe


def test_pear_never_hard_blocked_even_if_listed():
    policy = {
        "hard_block_enabled": True,
        "hard_block_gaming": True,
        "hard_block_exes": [
            "YouTube Music.exe",
            "pear-desktop.exe",
            "msedge.exe",
            "msedgewebview2.exe",
        ],
    }
    assert not should_hard_block("YouTube Music.exe", "Music / Media", policy)
    assert not should_hard_block("pear-desktop.exe", "Music / Media", policy)
    assert not should_hard_block("msedge.exe", "Browser", policy)
    assert not should_hard_block("msedgewebview2.exe", "Other", policy)


def test_terminate_never_targets_edge_or_pear():
    assert terminate_blocked_process(1, exe="msedge.exe") is False
    assert terminate_blocked_process(1, exe="msedgewebview2.exe") is False
    assert terminate_blocked_process(1, exe="msedge_proxy.exe") is False
    assert terminate_blocked_process(1, exe="YouTube Music.exe") is False
    assert terminate_blocked_process(1, exe="pear-desktop.exe") is False
    protected = protected_browser_exes()
    assert "msedge.exe" in protected
    assert "youtube music.exe" in protected or "youtube-music.exe" in protected


def test_watch_leak_skips_music_players():
    """Title 'YouTube Music' must not soft-lock / storm Edge when Pear is foreground."""
    from backend.behavior.tracker_service import TrackerService
    from backend.behavior.tracker_storage import TrackerConfig

    svc = TrackerService(TrackerConfig())
    svc._user_id = 1
    svc._gate = {
        "browser": {"mode": "study", "block_watch_sites": True, "enforce": True},
    }
    svc._gate_policy = {"hard_block_enabled": True}
    # Should no-op for music players even with YouTube in the title.
    assert (
        svc._maybe_watch_title_leak("YouTube Music.exe", "Lo-fi beats - YouTube Music")
        is False
    )
    assert svc._maybe_watch_title_leak("pear-desktop.exe", "YouTube Music") is False
    # Real Edge YouTube tab still flagged as watch leak (overlay only; no kill).
    assert svc._maybe_watch_title_leak("msedge.exe", "Rick Roll - YouTube") is True


def test_watch_leak_skips_scaler_and_study_titles():
    """Scaler Edge titles must never soft-lock as YouTube watch-leak."""
    from backend.behavior.tracker_service import TrackerService
    from backend.behavior.tracker_storage import TrackerConfig

    svc = TrackerService(TrackerConfig())
    svc._user_id = 1
    svc._gate = {
        "browser": {"mode": "study", "block_watch_sites": True, "enforce": True},
    }
    svc._gate_policy = {"hard_block_enabled": True}
    for title in (
        "Scaler and 2 more pages - Personal - Microsoft Edge",
        "Home | Scaler Academy - Personal - Microsoft Edge",
        "Watch | Module 3 | Scaler Topics — Microsoft Edge",
        "Food Delivery Data Exploration and analysis 4 - Class | Scaler Academy",
        "Colab - Personal - Microsoft Edge",
        "github.com/obra/superpowers - Personal - Microsoft Edge",
    ):
        svc._last_watch_leak_at = 0.0
        assert svc._maybe_watch_title_leak("msedge.exe", title) is False, title
    # Pure YouTube still leaks
    svc._last_watch_leak_at = 0.0
    assert svc._maybe_watch_title_leak("msedge.exe", "Rick Roll - YouTube") is True


def test_title_keyword_skips_scaler_titles():
    from backend.behavior.tracker_service import TrackerService
    from backend.behavior.tracker_storage import TrackerConfig

    svc = TrackerService(TrackerConfig())
    svc._user_id = 1
    svc._gate = {
        "browser": {
            "mode": "study",
            "block_keywords": True,
            "enforce": True,
        },
    }
    svc._gate_policy = {"hard_block_enabled": True}
    assert (
        svc._maybe_title_keyword_block(
            "msedge.exe",
            "Food Delivery Data Exploration and analysis 4 - Class | Scaler Academy",
        )
        is False
    )
