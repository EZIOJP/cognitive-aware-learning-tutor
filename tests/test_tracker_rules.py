"""Pure formatting for desktop tracker “Today’s rules / What’s next” panel."""

from __future__ import annotations

from backend.behavior.tracker_rules import (
    format_rules_lines,
    format_tray_tooltip,
    next_step_label,
    rules_snapshot_from_gate,
)


def _gate(
    *,
    next_step: str = "bible",
    bible_done: bool = False,
    plan_confirmed: bool = False,
    enabled: bool = True,
    hint: str | None = None,
    rewards_pts: int = 0,
    productive: int = 40,
    wake_clock: str | None = "06:42",
    browser_enforce: bool = True,
    browser_mode: str | None = None,
) -> dict:
    morning = {
        "enabled": True,
        "bible_done": bible_done,
        "plan_done": plan_confirmed,
        "plan_confirmed": plan_confirmed,
        "next": next_step,
        "hint": hint
        or (
            "Finish today’s Bible chapter (+10), then confirm plan/goals (+10)."
            if next_step == "bible"
            else (
                "Review goals & plan on Productivity, then Confirm (+10)."
                if next_step == "plan"
                else "Morning complete — 20 pts today."
            )
        ),
        "rewards": {"total_points": rewards_pts},
        "bible_url": "http://localhost:5173/bible",
        "plan_url": "http://localhost:5173/productivity?tab=plan",
        "suggested_wake": (
            {
                "wake_clock": wake_clock,
                "note": f"Last sleep ended ~{wake_clock} local.",
            }
            if wake_clock
            else None
        ),
    }
    mode = browser_mode or (
        "bible" if next_step == "bible" else "planning" if next_step == "plan" else "free"
    )
    return {
        "enabled": enabled,
        "locked": enabled and next_step != "open",
        "productive_minutes": productive,
        "daily_goal_minutes": 240,
        "browser_mode": mode,
        "morning": morning,
        "browser": {
            "enforce": browser_enforce,
            "mode": mode,
            "mode_label": mode.upper(),
            "allowed_browsers": ["msedge.exe"],
        },
    }


def test_rules_surface_nsfw_scan_inactive():
    snap = rules_snapshot_from_gate(
        _gate(next_step="open", bible_done=True, plan_confirmed=True, browser_mode="study"),
        nsfw_scan_line="NSFW scan inactive: install nudenet / set model",
    )
    lines = format_rules_lines(snap)
    assert any("NSFW scan inactive" in ln for ln in lines)


def test_next_step_label_maps_known_keys():
    assert next_step_label("bible") == "Bible"
    assert next_step_label("plan") == "Confirm plan"
    assert next_step_label("open") == "Day open"
    assert next_step_label("OPEN") == "Day open"
    assert next_step_label("") == "Day open"
    assert next_step_label("weird") == "Day open"


def test_snapshot_bible_pending():
    snap = rules_snapshot_from_gate(_gate(next_step="bible", rewards_pts=0))
    assert snap.next_key == "bible"
    assert snap.next_label == "Bible"
    assert snap.browser_mode == "bible"
    assert snap.browser_mode_label == "BIBLE"
    assert snap.bible_mark == "○"
    assert snap.plan_mark == "○"
    assert snap.hard_block == "Armed"
    assert snap.rewards_pts == 0
    assert "Bible" in snap.hint or "chapter" in snap.hint.lower()
    assert snap.wake_line is not None
    assert "06:42" in snap.wake_line
    assert snap.zen_edge_hint is not None
    assert "Zen" in snap.zen_edge_hint or "Edge" in snap.zen_edge_hint


def test_snapshot_plan_step_after_bible():
    snap = rules_snapshot_from_gate(
        _gate(next_step="plan", bible_done=True, plan_confirmed=False, rewards_pts=10)
    )
    assert snap.next_label == "Confirm plan"
    assert snap.browser_mode_label == "PLANNING"
    assert snap.bible_mark == "✓"
    assert snap.plan_mark == "○"
    assert snap.rewards_pts == 10


def test_snapshot_day_open_disarmed():
    snap = rules_snapshot_from_gate(
        _gate(
            next_step="open",
            bible_done=True,
            plan_confirmed=True,
            enabled=False,
            rewards_pts=20,
            browser_enforce=False,
            wake_clock=None,
        )
    )
    assert snap.next_label == "Day open"
    assert snap.browser_mode == "free"
    assert snap.bible_mark == "✓"
    assert snap.plan_mark == "✓"
    assert snap.hard_block == "Disarmed"
    assert snap.zen_edge_hint is None
    assert snap.wake_line is None


def test_focus_distracted_and_alive_extras():
    snap = rules_snapshot_from_gate(
        _gate(productive=55),
        focus_min=55,
        distracted_min=12,
        tracker_alive=True,
        jarvis_tip="Chapter first. I'll wait.",
    )
    assert snap.focus_min == 55
    assert snap.distracted_min == 12
    assert snap.tracker_alive is True
    assert snap.jarvis_tip == "Chapter first. I'll wait."


def test_format_rules_lines_readable():
    snap = rules_snapshot_from_gate(
        _gate(next_step="bible", productive=30),
        focus_min=30,
        distracted_min=5,
        tracker_alive=True,
        jarvis_tip="Bible first — then we open the day.",
    )
    lines = format_rules_lines(snap)
    text = "\n".join(lines)
    assert "Mode: BIBLE" in text
    assert "YouTube blocked until daily goal" in text
    assert "What’s next: Bible" in text or "What's next: Bible" in text
    assert "Bible" in text and "○" in text
    assert "Armed" in text
    assert "Focus" in text or "focus" in text.lower()
    assert "Recording" in text or "alive" in text.lower()
    assert "Jarvis" in text or "Tip" in text


def test_format_rules_includes_stack_health():
    snap = rules_snapshot_from_gate(
        _gate(next_step="bible"),
        api_up=False,
        web_up=False,
    )
    text = "\n".join(format_rules_lines(snap))
    assert "API: down" in text
    assert "Web: down" in text
    assert "run.bat" in text.lower() or "CALT stack" in text


def test_tray_tooltip_includes_stack_bits():
    snap = rules_snapshot_from_gate(
        _gate(next_step="plan", bible_done=True),
        api_up=True,
        web_up=False,
    )
    tip = format_tray_tooltip(snap)
    assert "API:up" in tip or "API: up" in tip
    assert "Web:dn" in tip or "Web:down" in tip
    assert len(tip) <= 128


def test_tray_tooltip_short():
    snap = rules_snapshot_from_gate(_gate(next_step="plan", bible_done=True))
    tip = format_tray_tooltip(snap)
    assert "PLANNING" in tip
    assert "Confirm plan" in tip
    assert len(tip) < 130
