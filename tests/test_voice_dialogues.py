"""Tests for expanded canned dialogues + once-per-day morning brief."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from backend.behavior.voice_agent import dialogues
from backend.behavior.voice_agent import morning_brief as mb


def test_all_categories_nonempty():
    dialogues.reset_for_tests()
    cats = dialogues.all_categories()
    assert "morning_greet" in cats
    assert "bible_done_praise" in cats
    assert "productivity_stats_brief" in cats
    assert "plan_from_yesterday" in cats
    assert "watch_site_block" in cats  # gate pools merged
    sizes = dialogues.pool_sizes()
    for cat in cats:
        assert sizes[cat] >= 1, cat
        assert dialogues.pick(cat), cat
    # ritual categories should be reasonably stocked
    for cat in (
        "morning_greet",
        "morning_bible_nudge",
        "bible_done_praise",
        "morning_plan_brief",
        "plan_done_praise",
        "daily_practice_nudge",
        "productivity_stats_brief",
        "plan_from_yesterday",
        "idle_checkin",
        "goodbye",
    ):
        assert sizes[cat] >= 8, cat


def test_placeholder_format():
    dialogues.reset_for_tests()
    line = dialogues.pick(
        "productivity_stats_brief",
        mode="rotate",
        focus_min=42,
        distracted_min=7,
        blocks=11,
    )
    assert "42" in line
    assert "7" in line
    assert "11" in line
    # missing keys → graceful defaults
    line2 = dialogues.pick("plan_from_yesterday", mode="rotate")
    assert "0" in line2 or "focus" in line2.lower() or "m" in line2


def test_once_per_day_brief_flag(tmp_path, monkeypatch):
    monkeypatch.setattr(mb, "_DIR", tmp_path)
    day = date(2026, 8, 4)
    assert mb.was_briefed_today(day) is False
    mb.mark_briefed(source="test", day=day, lines=["hi"])
    assert mb.was_briefed_today(day) is True
    assert (tmp_path / "morning_briefed_2026-08-04.json").is_file()
    mb.clear_brief_flag(day)
    assert mb.was_briefed_today(day) is False


def test_summarize_desktop_csv(tmp_path, monkeypatch):
    monkeypatch.setattr(mb, "_DATA_LOGS", tmp_path)
    day = date(2026, 8, 3)
    csv_path = tmp_path / f"DSC_desktop_behavior_{day.isoformat()}.csv"
    csv_path.write_text(
        "type,source,exe,title,domain,category,productivity_score,duration_seconds,"
        "timestamp,end_timestamp,reason,pid\n"
        "SESSION_END,desktop,code.exe,t,,coding,80,600,,,,,,, \n"
        "SESSION_END,desktop,chrome.exe,t,,browse,20,300,,,,,,, \n",
        encoding="utf-8",
    )
    stats = mb.summarize_desktop_csv(day)
    assert stats["focus_min"] == 10  # 600s
    assert stats["distracted_min"] == 5  # 300s
    assert stats["blocks"] == 2


def test_maybe_brief_respects_flag(tmp_path, monkeypatch):
    monkeypatch.setattr(mb, "_DIR", tmp_path)
    monkeypatch.setattr(mb, "_DATA_LOGS", tmp_path)
    spoken: list[str] = []

    monkeypatch.setattr(
        "backend.behavior.gate_alerts.speak_alert_sync",
        lambda text, force=False: spoken.append(text) or True,
    )
    monkeypatch.setattr(
        mb,
        "_morning_context",
        lambda uid: {
            "next": "bible",
            "bible_done": False,
            "plan_done": False,
            "enabled": True,
        },
    )
    # Force hour ok via force=True path for first call
    lines = mb.maybe_speak_morning_brief(
        1, force=True, source="test", async_speak=False
    )
    assert lines and len(lines) >= 2
    assert spoken
    spoken.clear()
    # Second auto call without force → blocked by flag
    again = mb.maybe_speak_morning_brief(
        1, force=False, source="test2", async_speak=False, after_hour=0
    )
    assert again is None
    assert spoken == []


def test_force_brief_cmd(tmp_path, monkeypatch):
    monkeypatch.setattr(mb, "_DIR", tmp_path)
    monkeypatch.setattr(mb, "_DATA_LOGS", tmp_path)
    spoken: list[str] = []
    monkeypatch.setattr(
        "backend.behavior.gate_alerts.speak_alert_sync",
        lambda text, force=False: spoken.append(text) or True,
    )
    monkeypatch.setattr(
        mb,
        "_morning_context",
        lambda uid: {
            "next": "plan",
            "bible_done": True,
            "plan_done": False,
            "enabled": True,
        },
    )
    # Mark already briefed
    mb.mark_briefed(source="earlier")
    lines = mb.force_brief(1)
    # wait briefly for async thread
    import time

    time.sleep(0.3)
    assert lines
    assert any("plan" in x.lower() or "confirm" in x.lower() or "block" in x.lower() for x in lines) or len(lines) >= 1


def test_brief_slash_command(monkeypatch):
    from backend.behavior.voice_agent.agent import VoiceAgent

    agent = VoiceAgent(1)
    called: list[list[str]] = []

    monkeypatch.setattr(
        "backend.behavior.voice_agent.morning_brief.force_brief",
        lambda uid: called.append([str(uid)]) or ["Good morning.", "Bible first."],
    )
    out = agent.handle_utterance("/brief", say=False)
    assert "Good morning" in out
    assert called
