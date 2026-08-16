"""Tk “Today’s rules” window — tray menu + optional embed helpers for lock card."""

from __future__ import annotations

import logging
import threading
import tkinter as tk
from typing import TYPE_CHECKING, Any, Callable

from backend.behavior.tracker_rules import (
    RulesSnapshot,
    estimate_distracted_min,
    format_rules_lines,
    pick_jarvis_tip,
    rules_snapshot_from_gate,
)

log = logging.getLogger("desktop_tracker")

if TYPE_CHECKING:
    from backend.behavior.tracker_service import TrackerService

_window_lock = threading.Lock()
_window: tk.Tk | None = None

_POLL_MS = 15_000
_BG = "#0f172a"
_PANEL = "#1e293b"
_FG = "#f8fafc"
_MUTED = "#94a3b8"
_ACCENT = "#0d9488"


def build_snapshot_from_service(service: "TrackerService") -> RulesSnapshot:
    """Refresh gate lightly and assemble display snapshot + cheap extras."""
    gate: dict[str, Any] = {}
    armed: bool | None = None
    try:
        gate = service.latest_gate() or {}
        armed = service.hard_block_armed()
    except Exception as exc:  # noqa: BLE001
        log.debug("rules gate fetch: %s", exc)

    focus = None
    try:
        if gate.get("productive_minutes") is not None:
            focus = int(gate.get("productive_minutes") or 0)
    except (TypeError, ValueError):
        focus = None

    distracted = None
    try:
        total_s = int(service.today_seconds() or 0)
        distracted = estimate_distracted_min(total_s, focus)
    except Exception:  # noqa: BLE001
        distracted = None

    next_key = str((gate.get("morning") or {}).get("next") or "open")
    mode = str((gate.get("browser") or {}).get("mode") or gate.get("browser_mode") or "")
    tip = pick_jarvis_tip(
        next_key, focus_min=focus or 0, distracted_min=distracted or 0, mode=mode or None
    )
    try:
        from backend.behavior.voice_agent.announce import last_jarvis_line

        spoken = last_jarvis_line()
        if spoken:
            tip = spoken
    except Exception:  # noqa: BLE001
        pass

    api_up = web_up = None
    try:
        from backend.behavior.stack_health import get_stack_health, maybe_jarvis_stack_down_line

        health = get_stack_health()
        api_up = health.api_up
        web_up = health.web_up
        down_line = maybe_jarvis_stack_down_line()
        if down_line:
            tip = down_line
            try:
                from backend.behavior.voice_agent.announce import surface_dialogue

                surface_dialogue(down_line, source="stack_health")
            except Exception:  # noqa: BLE001
                pass
            try:
                from backend.behavior.gate_alerts import speak_alert

                speak_alert(down_line, force=False)
            except Exception:  # noqa: BLE001
                pass
    except Exception as exc:  # noqa: BLE001
        log.debug("stack health probe: %s", exc)

    nsfw_line = None
    try:
        nsfw_line = service.nsfw_status_line()
    except Exception:  # noqa: BLE001
        try:
            from backend.behavior.nsfw_screen_scan import scan_status

            nsfw_line = str(scan_status().get("message") or "") or None
        except Exception:  # noqa: BLE001
            nsfw_line = None

    return rules_snapshot_from_gate(
        gate,
        focus_min=focus,
        distracted_min=distracted,
        tracker_alive=True,
        jarvis_tip=tip or None,
        hard_block_armed=armed,
        api_up=api_up,
        web_up=web_up,
        nsfw_scan_line=nsfw_line,
    )


def build_snapshot_from_gate(
    gate: dict[str, Any] | None,
    *,
    user_id: int | None = None,
    tracker_alive: bool = True,
) -> RulesSnapshot:
    """Snapshot for lock-card embed (optional recompute via user_id elsewhere)."""
    g = gate or {}
    focus = None
    try:
        if g.get("productive_minutes") is not None:
            focus = int(g.get("productive_minutes") or 0)
    except (TypeError, ValueError):
        focus = None

    distracted = None
    if user_id:
        try:
            from backend.behavior.tracker_storage import today_total_seconds

            distracted = estimate_distracted_min(today_total_seconds(user_id), focus)
        except Exception:  # noqa: BLE001
            distracted = None

    next_key = str((g.get("morning") or {}).get("next") or "open")
    mode = str((g.get("browser") or {}).get("mode") or g.get("browser_mode") or "")
    tip = pick_jarvis_tip(
        next_key, focus_min=focus or 0, distracted_min=distracted or 0, mode=mode or None
    )
    try:
        from backend.behavior.voice_agent.announce import last_jarvis_line

        spoken = last_jarvis_line()
        if spoken:
            tip = spoken
    except Exception:  # noqa: BLE001
        pass

    api_up = web_up = None
    try:
        from backend.behavior.stack_health import get_stack_health

        health = get_stack_health()
        api_up = health.api_up
        web_up = health.web_up
    except Exception:  # noqa: BLE001
        pass

    return rules_snapshot_from_gate(
        g,
        focus_min=focus,
        distracted_min=distracted,
        tracker_alive=tracker_alive,
        jarvis_tip=tip or None,
        api_up=api_up,
        web_up=web_up,
    )


def paint_rules_section(
    parent: tk.Misc,
    snap: RulesSnapshot,
    *,
    title: str = "Today’s rules",
) -> tk.Frame:
    """Draw a compact rules block into an existing Tk parent. Returns the frame."""
    frame = tk.Frame(parent, bg=_PANEL, padx=12, pady=10)
    frame.pack(fill=tk.X, pady=(8, 0))

    if title:
        tk.Label(
            frame,
            text=title,
            bg=_PANEL,
            fg=_FG,
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor=tk.W)

    body = tk.Frame(frame, bg=_PANEL)
    body.pack(fill=tk.X, pady=(6, 0) if title else (0, 0))

    for i, line in enumerate(format_rules_lines(snap)):
        is_mode = i == 0 and line.startswith("Mode:")
        fg = "#fbbf24" if is_mode else (_FG if i <= 1 else _MUTED)
        weight = "bold" if i <= 1 or is_mode else "normal"
        tk.Label(
            body,
            text=line,
            bg=_PANEL,
            fg=fg,
            font=("Segoe UI", 9, weight),
            justify=tk.LEFT,
            wraplength=400,
            anchor=tk.W,
        ).pack(anchor=tk.W, pady=(0, 2))

    return frame


def _clear_children(widget: tk.Misc) -> None:
    for child in widget.winfo_children():
        child.destroy()


def _open_window(
    *,
    fetch_snap: Callable[[], RulesSnapshot],
) -> None:
    global _window

    root = tk.Tk()
    root.title("CALT — Today’s rules")
    root.configure(bg=_BG)
    root.minsize(420, 300)
    try:
        root.geometry("480x400+100+100")
    except tk.TclError:
        pass

    header = tk.Frame(root, bg=_BG, padx=16, pady=12)
    header.pack(fill=tk.X)
    tk.Label(
        header,
        text="Today’s rules",
        bg=_BG,
        fg=_FG,
        font=("Segoe UI", 14, "bold"),
    ).pack(anchor=tk.W)
    tk.Label(
        header,
        text="Morning gate · hard-block · light tracker extras",
        bg=_BG,
        fg="#64748b",
        font=("Segoe UI", 9),
    ).pack(anchor=tk.W)

    panel = tk.Frame(root, bg=_PANEL, padx=4, pady=4)
    panel.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 8))

    content = tk.Frame(panel, bg=_PANEL)
    content.pack(fill=tk.BOTH, expand=True)

    btn_row = tk.Frame(root, bg=_BG, padx=16, pady=10)
    btn_row.pack(fill=tk.X)

    snap_holder: dict[str, RulesSnapshot | None] = {"snap": None}

    def _tk_message(title: str, body: str) -> None:
        from tkinter import messagebox

        messagebox.showinfo(title, body, parent=root)

    def _health_from_snap():
        from backend.behavior.stack_health import StackHealth

        snap = snap_holder["snap"]
        if snap is not None and snap.api_up is not None and snap.web_up is not None:
            return StackHealth(api_up=bool(snap.api_up), web_up=bool(snap.web_up))
        return None

    def _set_status(msg: str) -> None:
        try:
            root.title(msg if msg else "CALT — Today’s rules")
        except tk.TclError:
            pass

    def _open_target(url: str) -> None:
        from backend.behavior.stack_health import open_calt_page

        open_calt_page(
            url,
            health=_health_from_snap(),
            on_message=_tk_message,
            on_status=_set_status,
            parent=root,
            speak=True,
            auto_start=True,
        )

    def render() -> None:
        try:
            snap = fetch_snap()
        except Exception as exc:  # noqa: BLE001
            log.warning("rules refresh failed: %s", exc)
            return
        snap_holder["snap"] = snap
        _clear_children(content)
        paint_rules_section(content, snap, title="")
        # Enable/hint Start stack when either side is down
        try:
            down = snap.api_up is False or snap.web_up is False
            start_btn.configure(state=tk.NORMAL if down else tk.DISABLED)
            next_key = str(snap.next_key or "").lower()
            mode = str(snap.browser_mode or "").lower()
            prefer_bible = next_key == "bible" or mode == "bible"
            web_dn = snap.web_up is False
            if prefer_bible and web_dn:
                start_bible_btn.configure(state=tk.NORMAL, text="Start stack & open Bible")
            elif down:
                start_bible_btn.configure(
                    state=tk.NORMAL,
                    text="Start stack & open Bible" if prefer_bible else "Start stack & open",
                )
            else:
                start_bible_btn.configure(state=tk.DISABLED, text="Start stack & open Bible")
        except tk.TclError:
            pass

    def open_bible() -> None:
        snap = snap_holder["snap"]
        url = snap.bible_url if snap else "/bible"
        _open_target(url)

    def open_plan() -> None:
        snap = snap_holder["snap"]
        url = snap.plan_url if snap else "/productivity?tab=plan"
        _open_target(url)

    def start_stack() -> None:
        from backend.behavior.stack_health import local_jarvis_speak, start_calt_stack

        local_jarvis_speak("stack_starting", force=True)
        start_calt_stack()
        _tk_message(
            "Starting CALT stack",
            "Launched run.bat in a new console (API + frontend).\n"
            "Wait a few seconds, then Refresh or use Open Bible / Productivity.",
        )

    def start_stack_and_open() -> None:
        """One-click: start stack (if needed) then open Bible (or plan)."""
        snap = snap_holder["snap"]
        next_key = str(getattr(snap, "next_key", "") or "").lower() if snap else "bible"
        mode = str(getattr(snap, "browser_mode", "") or "").lower() if snap else ""
        prefer_bible = next_key == "bible" or mode == "bible"
        url = (
            (snap.bible_url if prefer_bible else snap.plan_url)
            if snap
            else ("/bible" if prefer_bible else "/productivity?tab=plan")
        )
        _open_target(url)
        try:
            render()
        except Exception:  # noqa: BLE001
            pass

    def close() -> None:
        global _window
        try:
            root.destroy()
        except tk.TclError:
            pass
        _window = None

    tk.Button(
        btn_row,
        text="Open Bible",
        command=open_bible,
        bg=_ACCENT,
        fg="#f0fdfa",
        activebackground="#14b8a6",
        relief=tk.FLAT,
        padx=12,
        pady=6,
        cursor="hand2",
        font=("Segoe UI", 9, "bold"),
    ).pack(side=tk.LEFT)

    tk.Button(
        btn_row,
        text="Open Productivity",
        command=open_plan,
        bg="#334155",
        fg="#e2e8f0",
        activebackground="#475569",
        relief=tk.FLAT,
        padx=12,
        pady=6,
        cursor="hand2",
        font=("Segoe UI", 9),
    ).pack(side=tk.LEFT, padx=(8, 0))

    start_btn = tk.Button(
        btn_row,
        text="Start CALT stack",
        command=start_stack,
        bg="#334155",
        fg="#e2e8f0",
        activebackground="#475569",
        relief=tk.FLAT,
        padx=10,
        pady=6,
        cursor="hand2",
        font=("Segoe UI", 9),
        state=tk.DISABLED,
    )
    start_btn.pack(side=tk.LEFT, padx=(8, 0))

    start_bible_btn = tk.Button(
        btn_row,
        text="Start stack & open Bible",
        command=start_stack_and_open,
        bg="#0f766e",
        fg="#f0fdfa",
        activebackground="#14b8a6",
        relief=tk.FLAT,
        padx=10,
        pady=6,
        cursor="hand2",
        font=("Segoe UI", 9, "bold"),
        state=tk.DISABLED,
    )
    start_bible_btn.pack(side=tk.LEFT, padx=(8, 0))

    tk.Button(
        btn_row,
        text="Refresh",
        command=render,
        bg="#334155",
        fg="#e2e8f0",
        activebackground="#475569",
        relief=tk.FLAT,
        padx=10,
        pady=6,
        cursor="hand2",
        font=("Segoe UI", 9),
    ).pack(side=tk.LEFT, padx=(8, 0))

    tk.Button(
        btn_row,
        text="Close",
        command=close,
        bg="#334155",
        fg="#e2e8f0",
        activebackground="#475569",
        relief=tk.FLAT,
        padx=10,
        pady=6,
        cursor="hand2",
        font=("Segoe UI", 9),
    ).pack(side=tk.RIGHT)

    def poll() -> None:
        if _window is None:
            return
        try:
            if not root.winfo_exists():
                return
            # Only poll when visible (not withdrawn)
            try:
                if root.state() == "withdrawn":
                    root.after(_POLL_MS, poll)
                    return
            except tk.TclError:
                return
            render()
            root.after(_POLL_MS, poll)
        except tk.TclError:
            return

    root.protocol("WM_DELETE_WINDOW", close)
    render()
    _window = root
    root.after(_POLL_MS, poll)
    root.mainloop()
    _window = None


def show_todays_rules(fetch_snap: Callable[[], RulesSnapshot]) -> None:
    """Open or raise the rules window (tk on a background thread)."""
    global _window

    with _window_lock:
        if _window is not None:
            try:
                if _window.winfo_exists():
                    _window.after(0, _window.deiconify)
                    _window.after(0, _window.lift)
                    _window.after(0, _window.focus_force)
                    return
            except tk.TclError:
                _window = None

    threading.Thread(
        target=_open_window,
        kwargs={"fetch_snap": fetch_snap},
        daemon=True,
        name="tracker-rules-gui",
    ).start()


def show_todays_rules_for_service(service: "TrackerService") -> None:
    if not service.user_id:
        log.warning("Cannot show today’s rules — tracker user_id not set")
        return
    show_todays_rules(lambda: build_snapshot_from_service(service))
