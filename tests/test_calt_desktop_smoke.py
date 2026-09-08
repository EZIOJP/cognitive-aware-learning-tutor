"""Smoke tests for CALT Desktop shell (no live tracker)."""

from __future__ import annotations

import os

import pytest

pytest.importorskip("PySide6")


def test_calt_desktop_version() -> None:
    from backend.behavior.calt_desktop import __version__

    assert __version__


def test_rules_policy_helpers_roundtrip(monkeypatch: pytest.MonkeyPatch) -> None:
    """load/save helpers call productivity_policy with a session."""
    from backend.behavior.calt_desktop.tabs import rules as rules_mod

    calls: list[tuple] = []

    class _DB:
        def close(self) -> None:
            pass

    def fake_session():
        return _DB()

    def fake_load(db, user_id):
        calls.append(("load", user_id))
        return {"hard_block_enabled": True, "daily_goal_minutes": 240, "hard_block_exes": []}

    def fake_update(db, user_id, patch):
        calls.append(("update", user_id, patch))
        return {**patch, "ok": True}

    monkeypatch.setattr("backend.db.base.SessionLocal", fake_session)
    monkeypatch.setattr(
        "backend.behavior.productivity_policy.load_policy_dict",
        fake_load,
    )
    monkeypatch.setattr(
        "backend.behavior.productivity_policy.update_policy",
        fake_update,
    )

    assert rules_mod.load_policy_for_user(1)["hard_block_enabled"] is True
    out = rules_mod.save_policy_for_user(1, {"hard_block_enabled": False})
    assert out["hard_block_enabled"] is False
    assert calls[0][0] == "load"
    assert calls[1][0] == "update"


def test_main_window_builds_offscreen() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from backend.behavior.calt_desktop.main_window import MainWindow

    app = QApplication.instance() or QApplication([])

    class _FakeService:
        user_id = 0

        def latest_gate(self, *, force: bool = False):
            return {}

        def today_seconds(self):
            return 0

    win = MainWindow(_FakeService())  # type: ignore[arg-type]
    assert win.windowTitle() == "CALT Desktop"
    from PySide6.QtWidgets import QStackedWidget

    pages = win.findChild(QStackedWidget)
    assert pages is not None
    assert pages.count() == 10
    from backend.behavior.calt_desktop.widgets.sidebar_nav import SidebarNav

    sidebar = win.findChild(SidebarNav)
    assert sidebar is not None
    win.close()
    del win
    assert app is not None


def test_watch_probe_and_lan_hint() -> None:
    from backend.behavior.calt_desktop.tabs import watch as watch_mod

    hint = watch_mod.lan_base_hint()
    assert "8765" in hint
    # Probe may be down in CI — shape only
    result = watch_mod.probe_hub_health(timeout=0.3)
    assert "ok" in result


def test_voice_list_notes_shape(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.behavior import voice_notes as vn

    monkeypatch.setattr(vn, "NOTES_DIR", tmp_path)
    (tmp_path / "voice_20260831_120000.opus").write_bytes(b"abc")
    rows = vn.list_notes()
    assert len(rows) == 1
    assert rows[0]["name"].endswith(".opus")
    assert rows[0]["size"] == 3


def test_bible_chapter_html_escapes() -> None:
    from backend.behavior.calt_desktop.tabs.bible import _chapter_html

    html_out = _chapter_html(
        {
            "name": "Genesis",
            "chapter": 1,
            "version_name": "WEB",
            "verses": [{"number": 1, "text": "In the <beginning>"}],
        }
    )
    assert "Genesis" in html_out
    assert "&lt;beginning&gt;" in html_out


def test_planner_blocks_empty_without_user() -> None:
    from backend.behavior.calt_desktop.planner_data import blocks_for_day

    assert blocks_for_day(0) == []


def test_planner_block_dialog_values() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from datetime import date

    from PySide6.QtWidgets import QApplication

    from backend.behavior.calt_desktop.dialogs.planner_block import PlannerBlockDialog

    app = QApplication.instance() or QApplication([])
    dlg = PlannerBlockDialog(day=date(2026, 9, 1), title="Deep work", category="study")
    v = dlg.values()
    assert v["title"] == "Deep work"
    assert v["category"] == "study"
    assert app is not None


def test_block_local_span_clips_to_day() -> None:
    from datetime import date

    from backend.behavior.calt_desktop.widgets.native_calendar import block_local_span

    day = date(2026, 9, 1)
    block = {
        "start_at": "2026-09-01T09:00:00+05:30",
        "end_at": "2026-09-01T10:30:00+05:30",
        "planned_minutes": 90,
    }
    span = block_local_span(block, day)
    assert span is not None
    assert span[1] > span[0]


def test_hard_block_dialog_builds_offscreen() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from backend.behavior.calt_desktop.dialogs import (
        hard_block_bridge,
        show_hard_block_dialog,
    )

    app = QApplication.instance() or QApplication([])
    show_hard_block_dialog(
        None,
        exe="steam.exe",
        gate={"productive_minutes": 40, "daily_goal_minutes": 240, "remaining_minutes": 200},
    )
    br = hard_block_bridge()
    br.set_parent(None)
    br.request(exe="game.exe", gate={"productive_minutes": 10, "daily_goal_minutes": 240})
    assert app is not None


def test_plan_hour_segments_split_block() -> None:
    from datetime import date

    from backend.behavior.calt_desktop.planner_segments import plan_blocks_to_hour_segs

    day = date(2026, 9, 1)
    blocks = [
        {
            "id": 1,
            "title": "Study",
            "category": "study",
            "start_at": "2026-09-01T09:30:00+05:30",
            "end_at": "2026-09-01T10:45:00+05:30",
            "status": "scheduled",
        }
    ]
    segs = plan_blocks_to_hour_segs(blocks, day)
    assert len(segs) >= 2
    assert all(0 <= int(s["start_min"]) < int(s["end_min"]) <= 60 for s in segs)


def test_day_grid_2d_builds_offscreen() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from datetime import date

    from PySide6.QtWidgets import QApplication

    from backend.behavior.calt_desktop.widgets.day_grid_2d import DayGrid2DPanel

    app = QApplication.instance() or QApplication([])
    panel = DayGrid2DPanel()
    panel.set_data(date(2026, 9, 1), [], [])
    assert panel.grid().minimumHeight() > 100
    assert panel.grid().minimumWidth() >= 520
    assert app is not None


def test_desktop_nav_tab_names() -> None:
    from backend.behavior.calt_desktop.navigation import TAB_NAMES

    assert "Plan" in TAB_NAMES
    assert "Calendar" in TAB_NAMES
    assert "Bible" in TAB_NAMES


def test_voice_agent_ui_status_labels() -> None:
    from backend.behavior.calt_desktop.widgets.voice_agent_panel import describe_voice_agent_ui

    line, checked, enabled = describe_voice_agent_ui(
        env_enabled=False,
        free_paused=False,
        hotkey_enabled=True,
        hotkey_running=True,
    )
    assert "VOICE_AGENT_ENABLED" in line
    assert checked is False
    assert enabled is False

    line2, checked2, enabled2 = describe_voice_agent_ui(
        env_enabled=True,
        free_paused=True,
        hotkey_enabled=True,
        hotkey_running=False,
    )
    assert "FREE" in line2
    assert checked2 is False
    assert enabled2 is False

    line3, checked3, enabled3 = describe_voice_agent_ui(
        env_enabled=True,
        free_paused=False,
        hotkey_enabled=True,
        hotkey_running=True,
    )
    assert checked3 is True
    assert enabled3 is True
    assert "ON" in line3


def test_desktop_prefs_last_tab_roundtrip() -> None:
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    from backend.behavior.calt_desktop.desktop_prefs import load_last_tab, save_last_tab

    app = QApplication.instance() or QApplication([])
    save_last_tab("Calendar")
    assert load_last_tab() == "Calendar"
    save_last_tab("Today")
    assert app is not None


def test_propose_merge_resolves_overlaps() -> None:
    from backend.behavior.calt_desktop.planner_propose_merge import resolve_proposed_overlaps

    blocks = [
        {
            "title": "A",
            "start_at": "2026-09-01T09:00:00+05:30",
            "end_at": "2026-09-01T10:00:00+05:30",
            "source": "study",
        },
        {
            "title": "B",
            "start_at": "2026-09-01T09:30:00+05:30",
            "end_at": "2026-09-01T10:30:00+05:30",
            "source": "study",
        },
    ]
    out = resolve_proposed_overlaps(blocks)
    assert len(out) == 2
    assert out[0]["start_at"] != out[1]["start_at"]


def test_merge_propose_cascades_after_rhythm_breaks() -> None:
    from datetime import date

    from backend.behavior.calt_desktop.planner_propose_merge import merge_propose_result

    api_blocks = [
        {
            "title": "Study",
            "category": "study",
            "start_at": "2026-09-02T11:20:00+05:30",
            "end_at": "2026-09-02T12:30:00+05:30",
            "source": "study",
        },
        {
            "title": "Lunch",
            "category": "food",
            "start_at": "2026-09-02T13:22:00+05:30",
            "end_at": "2026-09-02T14:07:00+05:30",
            "source": "routine",
        },
    ]
    merged = merge_propose_result(
        api_blocks=api_blocks,
        calendar_blocks=[],
        routines=[],
        range_start=date(2026, 9, 2),
        horizon_days=1,
    )
    assert len(merged) >= 2
    # No two blocks overlap on the same day after rhythm + cascade.
    day_blocks = sorted(merged, key=lambda b: b["start_at"])
    for i in range(len(day_blocks) - 1):
        assert day_blocks[i]["end_at"] <= day_blocks[i + 1]["start_at"]


def test_voice_notes_dir_is_project_relative() -> None:
    from backend.behavior import voice_notes as vn
    from backend.paths import ROOT

    assert vn.NOTES_DIR.is_absolute()
    assert vn.NOTES_DIR == ROOT / "data" / "voice_notes"


def test_dialogues_use_hours_minutes_labels() -> None:
    from backend.behavior.voice_agent.dialogues import pick

    line = pick("productivity_stats_brief", focus_min=90, distracted_min=15, blocks=3)
    assert "1 hour 30 mins" in line
    assert "15 mins" in line
    assert "{focus" not in line


def test_sync_status_helpers() -> None:
    from backend.behavior.calt_desktop.sync_status import format_sync_label

    assert format_sync_label(None) == "never"
    assert format_sync_label("2026-08-17T17:47:12+00:00") != "never"
    from datetime import date

    from backend.behavior.calt_desktop.planner_propose_merge import blocks_for_apply

    blocks = [
        {"title": "x", "start_at": "2026-09-01T09:00:00+05:30", "end_at": "2026-09-01T10:00:00+05:30", "source": "existing"},
        {"title": "y", "start_at": "2026-09-01T11:00:00+05:30", "end_at": "2026-09-01T12:00:00+05:30", "source": "study"},
    ]
    out = blocks_for_apply(blocks, range_start=date(2026, 9, 1), range_end=date(2026, 9, 1))
    assert len(out) == 1
    assert out[0]["title"] == "y"


def test_gate_lock_hint_morning() -> None:
    from backend.behavior.calt_desktop.gate_summary import gate_lock_hint

    hint = gate_lock_hint(
        {
            "locked": True,
            "enabled": True,
            "morning": {"next": "bible", "bible_done": False, "plan_confirmed": False},
        }
    )
    assert "Bible" in hint or "bible" in hint.lower()
    assert "locked" in hint.lower()


def test_collect_system_status_shape() -> None:
    from backend.behavior.calt_desktop.system_status import checklist_rows, collect_system_status

    st = collect_system_status()
    assert "api_up" in st
    assert "hub_up" in st
    rows = checklist_rows(st)
    assert len(rows) >= 6
    assert rows[0][0] == "CALT Desktop"


def test_link_account_banner_visibility() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from backend.behavior.calt_desktop.widgets.link_account_banner import LinkAccountBanner

    app = QApplication.instance() or QApplication([])
    banner = LinkAccountBanner()
    banner.refresh(linked=False)
    assert banner.isVisible()
    banner.refresh(linked=True)
    assert not banner.isVisible()
    assert app is not None


def test_lecture5_seed_note_on_disk() -> None:
    from backend.paths import ROOT

    path = (
        ROOT
        / "data"
        / "notes"
        / "lecture5_pandas_operations_notes.md"
    )
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert "L5-T05" in text
    assert "Topic Index" in text


def test_rules_tab_builds_offscreen() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from backend.behavior.calt_desktop.tabs.rules import RulesTab

    app = QApplication.instance() or QApplication([])

    class _FakeService:
        user_id = 0

        def latest_gate(self, *, force: bool = False):
            return {}

    tab = RulesTab(_FakeService())  # type: ignore[arg-type]
    tab.reload()
    assert app is not None


def test_blocked_apps_editor_roundtrip() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from backend.behavior.calt_desktop.widgets.rules_panels import BlockedAppsEditor

    app = QApplication.instance() or QApplication([])
    editor = BlockedAppsEditor()
    editor.set_exes(["steam.exe", "discord.exe"])
    editor._new_exe.setText("valorant")
    editor._add_exe()
    assert "valorant.exe" in editor.exes()
    assert app is not None


def test_category_policy_table_export() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from backend.behavior.calt_desktop.widgets.rules_panels import CategoryPolicyTable

    app = QApplication.instance() or QApplication([])
    table = CategoryPolicyTable()
    policy = {
        "productive_categories": ["IDE / Code Editor"],
        "blocked_categories": ["Gaming"],
    }
    scores = {"IDE / Code Editor": 80, "Gaming": 10}
    table.load(policy, scores)
    patch, out_scores = table.export()
    assert "IDE / Code Editor" in patch["productive_categories"]
    assert "Gaming" in patch["blocked_categories"]
    assert out_scores["Gaming"] == 10
    assert app is not None


def test_stack_control_status_labels() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from backend.behavior.calt_desktop.widgets.stack_control import StackControl

    app = QApplication.instance() or QApplication([])
    ctrl = StackControl()
    ctrl._apply_status({"api_up": False, "web_up": False, "hub_up": True, "stack_up": False})
    assert "Run CALT stack" in ctrl._btn.text()
    assert "Hub up" in ctrl._btn.text()
    ctrl._apply_status({"api_up": True, "web_up": True, "hub_up": True, "stack_up": True})
    assert "running" in ctrl._btn.text().lower()
    assert app is not None
