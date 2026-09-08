"""Dashboard bridge — plain-English gate snapshot for v2a WebView."""

from __future__ import annotations

from backend.behavior.calt_desktop.dashboard_bridge import snapshot_from_gate


def _stub_gate(
    *,
    next_step: str = "bible",
    bible_done: bool = False,
    plan_confirmed: bool = False,
    enabled: bool = True,
    locked: bool | None = None,
    productive: int = 40,
    remaining: int = 200,
    day_unlimited: bool = False,
    hard_block_gaming: bool = True,
    hard_block_exes: list[str] | None = None,
    free_override: bool = False,
    browser_mode: str | None = None,
    block_porn: bool = True,
) -> dict:
    morning = {
        "enabled": True,
        "bible_done": bible_done,
        "plan_done": plan_confirmed,
        "plan_confirmed": plan_confirmed,
        "next": next_step,
        "hint": (
            "Finish today's Bible chapter to unlock the plan."
            if next_step == "bible"
            else (
                "Confirm today's plan on the Plan tab to open the day."
                if next_step == "plan"
                else "Morning complete — day is open."
            )
        ),
        "rewards": {"total_points": 0},
    }
    mode = browser_mode or (
        "bible" if next_step == "bible" else "planning" if next_step == "plan" else "study"
    )
    if locked is None:
        locked = bool(enabled and not day_unlimited and next_step != "open")
    return {
        "enabled": enabled,
        "locked": locked,
        "unlocked": not locked,
        "productive_minutes": productive,
        "daily_goal_minutes": 240,
        "remaining_minutes": remaining,
        "hard_block_gaming": hard_block_gaming,
        "hard_block_exes": list(hard_block_exes or ["steam.exe"]),
        "day_unlimited": day_unlimited,
        "browser_mode": mode,
        "morning": morning,
        "browser": {
            "enforce": locked,
            "mode": mode,
            "mode_label": mode.upper(),
            "block_porn": block_porn,
            "free_override_active": free_override,
            "free_override_until": "2099-01-01T12:00:00+00:00" if free_override else None,
        },
    }


def test_snapshot_from_gate_why_and_blocked_summary():
    snap = snapshot_from_gate(_stub_gate(next_step="bible"))
    active = snap["active"]
    assert isinstance(active["why"], str) and active["why"].strip()
    assert isinstance(active["blocked_summary"], list)
    assert active["blocked_summary"]
    assert active["hard_block_armed"] is True
    assert active["morning_next"] == "bible"
    assert isinstance(active["until"], dict)
    assert active["until"].get("label")
    assert snap["incubation"]["active"] is False
    assert isinstance(snap["earned"]["daily_cap"], int)


def test_snapshot_bible_until_kind_morning():
    snap = snapshot_from_gate(_stub_gate(next_step="bible"))
    until = snap["active"]["until"]
    assert until["kind"] == "morning"
    assert "bible" in until["label"].lower() or "Bible" in until["label"]


def test_snapshot_day_open_empty_or_soft_blocks():
    snap = snapshot_from_gate(
        _stub_gate(
            next_step="open",
            bible_done=True,
            plan_confirmed=True,
            locked=False,
            day_unlimited=True,
            remaining=0,
            browser_mode="free",
        )
    )
    assert snap["active"]["why"].strip()
    assert isinstance(snap["active"]["blocked_summary"], list)
