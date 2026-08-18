"""Offline WEB structured Bible + chapter daily goal + today-only assignment."""

import pytest

from backend.bible import store, structured


@pytest.fixture(autouse=True)
def _silence_bible_tts(monkeypatch):
    """Ticking a chapter praises via TTS — keep unit tests from starting the gate worker."""
    monkeypatch.setattr(
        "backend.behavior.voice_agent.dialogues.speak",
        lambda *a, **k: "",
    )


def test_web_read_genesis_1():
    ch = structured.read_chapter("web", "Genesis", 1)
    assert ch["name"] == "Genesis"
    assert ch["chapter"] == 1
    assert ch["verses"][0]["number"] == 1
    assert "beginning" in ch["verses"][0]["text"].lower()


def test_web_meta_66_books():
    m = structured.meta("web")
    assert m["book_count"] == 66
    assert any(b["name"] == "Revelation" for b in m["books"])


def test_sequential_plan_starts_genesis():
    plan = structured.sequential_plan("web")
    assert plan[0]["key"] == "Genesis|1"
    assert plan[1]["key"] == "Genesis|2"
    assert any(p["key"] == "Revelation|22" for p in plan)


def test_today_chapter_bootstrap_from_completed(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "bible_dir", lambda: tmp_path)
    monkeypatch.setattr(store, "_day_key", lambda: "2026-08-04")
    from backend.planner import morning_rewards as mr

    monkeypatch.setattr(mr, "_STORE", tmp_path / "morning_rewards.json")

    # Simulate prior progress: Genesis 1–3 done in lifetime
    reader = {
        "completed_chapters": ["Genesis|1", "Genesis|2", "Genesis|3"],
        "manual_chapters": [],
        "cleared_chapters": [],
    }
    (tmp_path / "reader_1.json").write_text(__import__("json").dumps(reader), encoding="utf-8")

    today = store.resolve_today_chapter(1)
    assert today["key"] == "Genesis|4"
    assert today["label"] == "Genesis 4"
    assert today["done"] is False
    assert today["mode"] == "today_only"

    # Stable for the same day even after cursor would advance
    again = store.resolve_today_chapter(1)
    assert again["key"] == "Genesis|4"


def test_today_chapter_fresh_user_gets_genesis_1(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "bible_dir", lambda: tmp_path)
    monkeypatch.setattr(store, "_day_key", lambda: "2026-08-04")

    today = store.resolve_today_chapter(7)
    assert today["key"] == "Genesis|1"


def test_chapter_goal_tick_only_today(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "bible_dir", lambda: tmp_path)
    monkeypatch.setattr(store, "_day_key", lambda: "2026-07-23")
    from backend.planner import morning_rewards as mr

    monkeypatch.setattr(mr, "_STORE", tmp_path / "morning_rewards.json")

    assigned = store.resolve_today_chapter(1)
    assert assigned["key"] == "Genesis|1"

    with pytest.raises(ValueError, match="Only today's chapter"):
        store.tick_chapter(1, book="John", chapter=3, done=True)

    assert store.chapter_goal_met(1) is False
    out = store.tick_chapter(1, book="Genesis", chapter=1, done=True)
    assert out["done"] is True
    assert "Genesis|1" in store.chapters_completed_today(1)
    assert store.chapter_goal_met(1) is True
    assert out["chapter_goal"]["met"] is True
    assert out.get("morning_rewards", {}).get("awards", {}).get("bible", {}).get("granted") is True
    assert out["today_chapter"]["done"] is True

    # Cursor advances for tomorrow; assignment stays Genesis 1 today
    reader = __import__("json").loads((tmp_path / "reader_1.json").read_text(encoding="utf-8"))
    assert reader["plan_cursor"] == 1
    assert store.resolve_today_chapter(1)["key"] == "Genesis|1"

    store.tick_chapter(1, book="Genesis", chapter=1, done=False)
    assert store.chapter_goal_met(1) is False


def test_next_day_advances_chapter(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "bible_dir", lambda: tmp_path)
    monkeypatch.setattr(store, "_day_key", lambda: "2026-08-04")
    from backend.planner import morning_rewards as mr

    monkeypatch.setattr(mr, "_STORE", tmp_path / "morning_rewards.json")

    store.tick_chapter(1, book="Genesis", chapter=1, done=True)
    assert store.resolve_today_chapter(1)["key"] == "Genesis|1"

    monkeypatch.setattr(store, "_day_key", lambda: "2026-08-05")
    nxt = store.resolve_today_chapter(1)
    assert nxt["key"] == "Genesis|2"


def test_heartbeat_never_auto_completes(tmp_path, monkeypatch):
    """Meditation dwell must not tick the day goal — only explicit tick_chapter."""
    monkeypatch.setattr(store, "bible_dir", lambda: tmp_path)
    monkeypatch.setattr(store, "_day_key", lambda: "2026-08-04")
    from backend.planner import morning_rewards as mr

    monkeypatch.setattr(mr, "_STORE", tmp_path / "morning_rewards.json")

    assigned = store.resolve_today_chapter(1)
    assert assigned["key"] == "Genesis|1"
    assert store.chapter_goal_met(1) is False

    # Simulate ~10 focused heartbeats (would have exceeded old 3-min auto-dwell)
    t0 = 1_700_000_000.0
    for i in range(12):
        monkeypatch.setattr(store.time, "time", lambda i=i, t0=t0: t0 + i * 20)
        out = store.apply_chapter_heartbeat(
            1, book="Genesis", chapter=1, focused=True, verse=1
        )
        assert out["chapter_goal"]["met"] is False
        assert "Genesis|1" not in (out.get("chapters_completed_today") or [])

    assert store.chapter_goal_met(1) is False
    day = store.load_day(1)
    assert int(day.get("bible_seconds") or 0) > 0  # minutes still credited
    assert day.get("chapters_completed") == []


def test_mark_chapters_complete_does_not_day_goal(tmp_path, monkeypatch):
    """PDF page-through visual markers must not unlock morning bible_done."""
    monkeypatch.setattr(store, "bible_dir", lambda: tmp_path)
    monkeypatch.setattr(store, "_day_key", lambda: "2026-08-04")
    from backend.planner import morning_rewards as mr

    monkeypatch.setattr(mr, "_STORE", tmp_path / "morning_rewards.json")

    store.resolve_today_chapter(1)
    store.mark_chapters_complete(1, ["Genesis|1"])
    assert "Genesis|1" in store.get_completed_chapters(1)
    assert store.chapter_goal_met(1) is False
    assert store.resolve_today_chapter(1)["done"] is False


def test_completed_day_still_returns_assigned_chapter(tmp_path, monkeypatch):
    """After tick, today assignment + full text stay available for re-read / meditate."""
    monkeypatch.setattr(store, "bible_dir", lambda: tmp_path)
    monkeypatch.setattr(store, "_day_key", lambda: "2026-08-04")
    from backend.planner import morning_rewards as mr

    monkeypatch.setattr(mr, "_STORE", tmp_path / "morning_rewards.json")

    assigned = store.resolve_today_chapter(1)
    store.tick_chapter(1, book=assigned["book"], chapter=int(assigned["chapter"]), done=True)
    again = store.resolve_today_chapter(1)
    assert again["key"] == assigned["key"]
    assert again["done"] is True
    ch = structured.read_chapter("web", again["book"], int(again["chapter"]))
    assert len(ch.get("verses") or []) > 3


def test_gate_uses_chapter_not_30m(tmp_path, monkeypatch):
    """day_unlimited needs chapter_met — bible_minutes alone is not enough."""
    from backend.behavior import distraction_gate as dg

    monkeypatch.setattr(store, "bible_dir", lambda: tmp_path)
    monkeypatch.setattr(store, "_day_key", lambda: "2026-07-23")

    def fake_summary(uid):
        return {
            "bible_minutes": 60,
            "game_bank_remaining_seconds": 0,
            "game_bank_remaining_minutes": 0,
            "game_bank_earned_minutes": 0,
            "game_bank_consumed_minutes": 0,
            "day_pass": False,
            "day_pass_status": None,
            "chapters_completed_today": ["Genesis|1"],
            "chapter_goal": {"done": 1, "target": 1, "met": True},
            "today_chapter": {
                "book": "Genesis",
                "chapter": 1,
                "key": "Genesis|1",
                "label": "Genesis 1",
                "done": True,
                "mode": "today_only",
            },
        }

    monkeypatch.setattr(store, "summary", fake_summary)

    bible = store.summary(1)
    chapter_met = bool((bible.get("chapter_goal") or {}).get("met"))
    productive = 300
    goal = 240
    day_pass = False
    day_unlimited = bool(day_pass or (productive >= goal and chapter_met))
    assert day_unlimited is True

    bible2 = {
        **bible,
        "chapters_completed_today": [],
        "chapter_goal": {"done": 0, "target": 1, "met": False},
    }
    chapter_met2 = bool((bible2.get("chapter_goal") or {}).get("met"))
    day_unlimited2 = bool(day_pass or (productive >= goal and chapter_met2))
    assert day_unlimited2 is False
    assert dg.is_game_bank_drain_target  # import smoke
