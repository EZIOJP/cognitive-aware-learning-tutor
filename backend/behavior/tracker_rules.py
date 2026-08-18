"""Format “Today’s rules / What’s next” from distraction-gate JSON (pure helpers)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.behavior.time_fmt import format_hours_mins


_NEXT_LABELS = {
    "bible": "Bible",
    "plan": "Confirm plan",
    "open": "Day open",
}

_BIBLE_URL = "http://localhost:5173/bible"
_PLAN_URL = "http://localhost:5173/productivity?tab=plan"


@dataclass(frozen=True)
class RulesSnapshot:
    next_key: str
    next_label: str
    bible_done: bool
    plan_confirmed: bool
    bible_mark: str
    plan_mark: str
    rewards_pts: int
    hard_block: str
    hint: str
    wake_line: str | None
    focus_min: int | None
    distracted_min: int | None
    tracker_alive: bool
    zen_edge_hint: str | None
    jarvis_tip: str | None
    bible_url: str
    plan_url: str
    browser_mode: str = "free"
    browser_mode_label: str = "FREE"
    api_up: bool | None = None
    web_up: bool | None = None
    nsfw_scan_line: str | None = None


def next_step_label(next_key: str | None, *, plan_window: dict[str, Any] | None = None) -> str:
    key = (next_key or "open").strip().lower()
    if key == "plan" and isinstance(plan_window, dict):
        phase = str(plan_window.get("phase") or "")
        if phase == "before_start":
            clock = str(plan_window.get("start_clock") or plan_window.get("start_hhmm") or "").strip()
            return f"Plan opens {clock}" if clock else "Plan opens soon"
        end_label = str(plan_window.get("end_label") or "").strip()
        if phase == "open" and end_label:
            return f"Confirm plan · until {end_label}"
    return _NEXT_LABELS.get(key, _NEXT_LABELS["open"])


def _mark(done: bool) -> str:
    return "✓" if done else "○"


def _wake_line(suggested: Any) -> str | None:
    if not isinstance(suggested, dict) or not suggested:
        return None
    clock = str(suggested.get("wake_clock") or "").strip()
    note = str(suggested.get("note") or "").strip()
    if clock and note:
        return f"Suggested wake ~{clock}"
    if clock:
        return f"Suggested wake ~{clock}"
    if note:
        # Keep short — full note can be long
        return note if len(note) <= 72 else note[:69] + "…"
    return None


def rules_snapshot_from_gate(
    gate: dict[str, Any] | None,
    *,
    focus_min: int | None = None,
    distracted_min: int | None = None,
    tracker_alive: bool = True,
    jarvis_tip: str | None = None,
    hard_block_armed: bool | None = None,
    api_up: bool | None = None,
    web_up: bool | None = None,
    nsfw_scan_line: str | None = None,
) -> RulesSnapshot:
    """Build a display snapshot from compute_distraction_gate (or hub) JSON."""
    g = gate or {}
    morning = g.get("morning") if isinstance(g.get("morning"), dict) else {}
    browser = g.get("browser") if isinstance(g.get("browser"), dict) else {}
    rewards = morning.get("rewards") if isinstance(morning.get("rewards"), dict) else {}

    next_key = str(morning.get("next") or "open").strip().lower()
    if next_key not in _NEXT_LABELS:
        next_key = "open"

    bible_done = bool(morning.get("bible_done"))
    plan_confirmed = bool(morning.get("plan_confirmed") or morning.get("plan_done"))
    rewards_pts = int(rewards.get("total_points") or 0)
    plan_window = morning.get("plan_window") if isinstance(morning.get("plan_window"), dict) else None

    if hard_block_armed is None:
        armed = bool(g.get("enabled"))
    else:
        armed = bool(hard_block_armed)

    hint = str(morning.get("hint") or "").strip()
    if not hint:
        hint = {
            "bible": "Finish today’s Bible chapter, then confirm plan.",
            "plan": "Confirm today’s plan on the Plan tab to open the day.",
            "open": "Morning complete — day is open.",
        }.get(next_key, "Morning complete — day is open.")
        if next_key == "plan" and plan_window:
            if plan_window.get("phase") == "before_start":
                hint = str(plan_window.get("reason") or hint)
            elif plan_window.get("end_label"):
                hint = f"Confirm plan · available until {plan_window.get('end_label')}."

    auto_plan = morning.get("auto_plan") if isinstance(morning.get("auto_plan"), dict) else None
    if next_key == "plan" and auto_plan:
        titles = [str(t) for t in (auto_plan.get("titles") or []) if str(t).strip()][:3]
        if titles and auto_plan.get("drafted"):
            hint = f"Auto-draft: {', '.join(titles)}. Confirm on the Plan tab."
        elif titles and auto_plan.get("reason") == "plan_exists":
            hint = (
                f"Blocks already on today ({len(titles)}). "
                "Add more, or confirm as-is on the Plan tab."
            )

    focus = focus_min
    if focus is None and g.get("productive_minutes") is not None:
        try:
            focus = int(g.get("productive_minutes") or 0)
        except (TypeError, ValueError):
            focus = None

    enforce = bool(browser.get("enforce"))
    zen_hint = "Gate: Edge only while enforcing" if enforce else None

    bible_url = str(morning.get("bible_url") or _BIBLE_URL).rstrip("/")
    plan_url = str(morning.get("plan_url") or _PLAN_URL).rstrip("/")

    from backend.behavior.browser_gate_policy import mode_label

    mode_raw = str(browser.get("mode") or g.get("browser_mode") or "free").strip().lower()
    if mode_raw not in ("bible", "planning", "study", "free"):
        mode_raw = "free"
    mode_lbl = str(browser.get("mode_label") or mode_label(mode_raw))

    return RulesSnapshot(
        next_key=next_key,
        next_label=next_step_label(next_key, plan_window=plan_window),
        bible_done=bible_done,
        plan_confirmed=plan_confirmed,
        bible_mark=_mark(bible_done),
        plan_mark=_mark(plan_confirmed),
        rewards_pts=rewards_pts,
        hard_block="Armed" if armed else "Disarmed",
        hint=hint,
        wake_line=_wake_line(morning.get("suggested_wake")),
        focus_min=focus,
        distracted_min=distracted_min,
        tracker_alive=bool(tracker_alive),
        zen_edge_hint=zen_hint,
        jarvis_tip=(jarvis_tip.strip() if jarvis_tip else None) or None,
        bible_url=bible_url,
        plan_url=plan_url,
        browser_mode=mode_raw,
        browser_mode_label=mode_lbl,
        api_up=api_up,
        web_up=web_up,
        nsfw_scan_line=(nsfw_scan_line.strip() if nsfw_scan_line else None) or None,
    )


def format_rules_lines(snap: RulesSnapshot) -> list[str]:
    """Multi-line body for the Tk rules panel (no buttons)."""
    mode_extra = ""
    if snap.browser_mode in ("bible", "planning", "study"):
        mode_extra = " · YouTube blocked until daily goal"
    elif snap.browser_mode == "free":
        mode_extra = " · YouTube OK (distraction filter on)"
    lines = [
        f"Mode: {snap.browser_mode_label}{mode_extra}",
        f"What’s next: {snap.next_label}",
        f"Bible {snap.bible_mark}  ·  Plan confirmed {snap.plan_mark}"
        + (f"  ·  Rewards {snap.rewards_pts} pts" if snap.rewards_pts else ""),
        f"Hard-block: {snap.hard_block}",
    ]
    if snap.hint:
        lines.append(snap.hint)
    if snap.wake_line:
        lines.append(snap.wake_line)

    extras: list[str] = []
    if snap.focus_min is not None:
        extras.append(f"Focus {format_hours_mins(snap.focus_min)}")
    if snap.distracted_min is not None:
        extras.append(f"Distracted {format_hours_mins(snap.distracted_min)}")
    extras.append("Recording: alive" if snap.tracker_alive else "Recording: ?")
    lines.append(" · ".join(extras))

    if snap.api_up is not None or snap.web_up is not None:
        api_s = "up" if snap.api_up else "down" if snap.api_up is False else "?"
        web_s = "up" if snap.web_up else "down" if snap.web_up is False else "?"
        stack = f"API: {api_s} · Web: {web_s}"
        if snap.web_up is False:
            stack += " — Start CALT stack (tray / run.bat)"
        elif snap.api_up is False:
            stack += " — gate/data may be stale"
        lines.append(stack)

    if snap.zen_edge_hint:
        lines.append(snap.zen_edge_hint)
    if snap.nsfw_scan_line:
        lines.append(snap.nsfw_scan_line)
    if snap.jarvis_tip:
        lines.append(f"Jarvis: {snap.jarvis_tip}")
    return lines


def format_tray_tooltip(snap: RulesSnapshot) -> str:
    """Short hover text for the system tray icon."""
    bit = f"{snap.browser_mode_label} · Next: {snap.next_label} · {snap.hard_block}"
    if snap.rewards_pts:
        bit += f" · {snap.rewards_pts}pts"
    if snap.api_up is not None or snap.web_up is not None:
        api_s = "up" if snap.api_up else "dn" if snap.api_up is False else "?"
        web_s = "up" if snap.web_up else "dn" if snap.web_up is False else "?"
        bit += f" · API:{api_s} Web:{web_s}"
    return bit if len(bit) <= 128 else bit[:125] + "…"


def pick_jarvis_tip(next_key: str, *, focus_min: int = 0, distracted_min: int = 0, mode: str | None = None) -> str:
    """One canned dialogue line (text only — no TTS). Soft-fails to empty."""
    try:
        from backend.behavior.voice_agent import dialogues as dlg

        m = (mode or "").strip().lower()
        if m in ("bible", "planning", "study", "free"):
            return dlg.pick(
                f"mode_{m}",
                mode="rotate",
                focus_min=int(focus_min or 0),
                distracted_min=int(distracted_min or 0),
                blocks=0,
            )
        key = (next_key or "open").strip().lower()
        cat = {
            "bible": "morning_bible_nudge",
            "plan": "morning_plan_brief",
            "open": "idle_checkin",
        }.get(key, "idle_checkin")
        return dlg.pick(
            cat,
            mode="rotate",
            focus_min=int(focus_min or 0),
            distracted_min=int(distracted_min or 0),
            blocks=0,
        )
    except Exception:  # noqa: BLE001
        return ""


def estimate_distracted_min(total_tracked_sec: int, focus_min: int | None) -> int | None:
    """Cheap distracted estimate: tracked minutes minus focus (floor at 0)."""
    if focus_min is None:
        return None
    tracked_m = max(0, int(total_tracked_sec) // 60)
    return max(0, tracked_m - max(0, int(focus_min)))
