"""Reward-day panel — stats + typeable activate (tray-safe tk window).

Root cause of broken typing: pystray menus call simpledialog on the tray thread
with a withdrawn Tk root; Windows often never delivers keyboard focus to that
dialog. Fix: dedicated Tk mainloop on a background thread + Entry.focus_force.
"""

from __future__ import annotations

import logging
import threading
import tkinter as tk
from typing import TYPE_CHECKING, Any, Callable

log = logging.getLogger("desktop_tracker")

if TYPE_CHECKING:
    from backend.behavior.tracker_service import TrackerService

_window_lock = threading.Lock()
_window: tk.Tk | None = None

BG = "#0f172a"
PANEL = "#1e293b"
FG = "#e2e8f0"
MUTED = "#94a3b8"
ACCENT = "#34d399"
WARN = "#fbbf24"
BTN = "#334155"
BTN_OK = "#059669"


def _row(parent: tk.Frame, label: str, value: str, *, value_fg: str = FG) -> None:
    row = tk.Frame(parent, bg=PANEL)
    row.pack(fill=tk.X, pady=2)
    tk.Label(row, text=label, bg=PANEL, fg=MUTED, font=("Segoe UI", 9), width=18, anchor=tk.W).pack(
        side=tk.LEFT
    )
    tk.Label(row, text=value, bg=PANEL, fg=value_fg, font=("Segoe UI", 9, "bold"), anchor=tk.W).pack(
        side=tk.LEFT, fill=tk.X, expand=True
    )


def _collect(service: "TrackerService") -> dict[str, Any]:
    from backend.behavior.browser_gate_policy import mode_label
    from backend.behavior.reward_days import CONFIRM_PHRASE, status
    from backend.behavior.stack_health import get_stack_health
    from backend.behavior.tracker_rules import next_step_label

    st = status(int(service.user_id))
    gate = service.latest_gate() or {}
    browser = gate.get("browser") or {}
    morning = gate.get("morning") or {}
    mode = browser.get("mode") or gate.get("browser_mode") or "—"
    try:
        health = get_stack_health().status_line()
    except Exception:  # noqa: BLE001
        health = "API: ? · Web: ?"

    secs = int(service.today_seconds() or 0)
    m = secs // 60
    if m < 60:
        today = f"{m}m"
    else:
        h, rem = divmod(m, 60)
        today = f"{h}h {rem}m" if rem else f"{h}h"

    return {
        "user": getattr(service, "username", None) or str(service.user_id),
        "today": today,
        "mode": mode_label(str(mode)),
        "day_unlimited": bool(gate.get("day_unlimited")),
        "reward_day": bool(gate.get("reward_day") or st.get("active_today")),
        "day_pass": bool(gate.get("day_pass")),
        "rules_next": next_step_label(morning.get("next")),
        "health": health,
        "confirm_phrase": CONFIRM_PHRASE,
        **st,
    }


def _open_window(service: "TrackerService", on_claimed: Callable[[], None] | None) -> None:
    global _window

    from backend.behavior.reward_days import CONFIRM_PHRASE, claim_reward_day

    root = tk.Tk()
    root.title("CALT — Reward day")
    root.configure(bg=BG)
    root.geometry("440x560")
    root.minsize(400, 480)
    try:
        root.attributes("-topmost", True)
    except tk.TclError:
        pass

    header = tk.Frame(root, bg=BG, padx=14, pady=12)
    header.pack(fill=tk.X)
    tk.Label(
        header,
        text="Reward day",
        bg=BG,
        fg="#f8fafc",
        font=("Segoe UI", 14, "bold"),
    ).pack(anchor=tk.W)
    tk.Label(
        header,
        text="Banked credits unlock free browsing until midnight.\nAdult filters stay on · tracking continues.",
        bg=BG,
        fg=MUTED,
        font=("Segoe UI", 9),
        justify=tk.LEFT,
    ).pack(anchor=tk.W, pady=(4, 0))

    stats = tk.Frame(root, bg=PANEL, padx=14, pady=12)
    stats.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 8))

    status_lbl = tk.Label(
        root,
        text="",
        bg=BG,
        fg=MUTED,
        font=("Segoe UI", 9),
        wraplength=400,
        justify=tk.LEFT,
    )
    status_lbl.pack(fill=tk.X, padx=14, pady=(0, 4))

    entry_frame = tk.Frame(root, bg=BG, padx=14, pady=4)
    entry_frame.pack(fill=tk.X)
    tk.Label(
        entry_frame,
        text=f"Type {CONFIRM_PHRASE} to activate one credit:",
        bg=BG,
        fg=FG,
        font=("Segoe UI", 9),
    ).pack(anchor=tk.W)
    entry = tk.Entry(
        entry_frame,
        font=("Segoe UI", 12),
        bg="#0b1220",
        fg=FG,
        insertbackground=FG,
        relief=tk.FLAT,
        highlightthickness=1,
        highlightbackground="#475569",
        highlightcolor=ACCENT,
    )
    entry.pack(fill=tk.X, pady=(6, 0), ipady=6)

    btn_row = tk.Frame(root, bg=BG, padx=14, pady=12)
    btn_row.pack(fill=tk.X)

    def render() -> None:
        for child in stats.winfo_children():
            child.destroy()
        try:
            data = _collect(service)
        except Exception as exc:  # noqa: BLE001
            tk.Label(stats, text=f"Could not load stats: {exc}", bg=PANEL, fg="#f87171").pack(
                anchor=tk.W
            )
            return

        active = bool(data.get("reward_day") or data.get("active_today"))
        avail = int(data.get("available") or 0)
        if active:
            title_fg, title = ACCENT, "ACTIVE until midnight"
        elif avail > 0:
            title_fg, title = WARN, f"{avail} credit(s) ready"
        else:
            title_fg, title = MUTED, "No credits banked yet"

        tk.Label(
            stats,
            text=title,
            bg=PANEL,
            fg=title_fg,
            font=("Segoe UI", 12, "bold"),
        ).pack(anchor=tk.W, pady=(0, 8))

        _row(stats, "User", str(data.get("user") or "—"))
        _row(stats, "Tracked today", str(data.get("today") or "—"))
        _row(stats, "Browser mode", str(data.get("mode") or "—"))
        _row(stats, "Day unlimited", "yes" if data.get("day_unlimited") else "no")
        _row(stats, "Day pass", "yes" if data.get("day_pass") else "no")
        _row(stats, "Rules next", str(data.get("rules_next") or "—"))
        _row(stats, "Stack", str(data.get("health") or "—"))
        _row(stats, "Banked credits", str(avail), value_fg=ACCENT if avail else MUTED)
        _row(stats, "Earned / granted", f"{data.get('earned', 0)} / {data.get('granted', 0)}")
        _row(stats, "Spent", str(data.get("spent") or 0))
        _row(stats, "Qualifying days", str(data.get("qualifying_days") or 0))
        _row(stats, "To next earn", f"{data.get('days_to_next_reward', 4)} day(s)")

        if active:
            status_lbl.configure(
                text="Reward day is already on. Extensions stay in free mode.",
                fg=ACCENT,
            )
            entry.configure(state=tk.DISABLED)
        elif data.get("day_unlimited") and not active:
            status_lbl.configure(
                text="Today is already unlocked (goal + Bible or day pass). Save credits for later.",
                fg=WARN,
            )
            entry.configure(state=tk.DISABLED)
        elif avail <= 0:
            status_lbl.configure(
                text="Earn credits: study goal + one Bible chapter on 4 days.",
                fg=MUTED,
            )
            entry.configure(state=tk.DISABLED)
        else:
            status_lbl.configure(
                text="Activate below — desktop tracker + browser extensions update in a few seconds.",
                fg=MUTED,
            )
            entry.configure(state=tk.NORMAL)

    def activate() -> None:
        typed = (entry.get() or "").strip().upper()
        if typed != CONFIRM_PHRASE:
            status_lbl.configure(
                text=f'Type {CONFIRM_PHRASE} exactly (caps optional), then Activate.',
                fg="#f87171",
            )
            entry.focus_force()
            return
        gate = service.latest_gate() or {}
        already = bool(gate.get("day_unlimited")) and not bool(gate.get("reward_day"))
        try:
            out = claim_reward_day(
                int(service.user_id),
                confirm=CONFIRM_PHRASE,
                already_unlocked=already,
            )
        except ValueError as exc:
            status_lbl.configure(text=str(exc), fg="#f87171")
            return
        try:
            from backend.behavior.voice_agent import sync_voice_with_browser_gate

            sync_voice_with_browser_gate(
                {
                    "reward_day": True,
                    "day_unlimited": True,
                    "browser": {"mode": "free"},
                },
                user_id=int(service.user_id),
            )
        except Exception:  # noqa: BLE001
            pass
        status_lbl.configure(
            text=(out.get("message") or "Reward day active")
            + f" · {out.get('available', 0)} left · voice paused for gaming",
            fg=ACCENT,
        )
        entry.delete(0, tk.END)
        if on_claimed:
            try:
                on_claimed()
            except Exception:  # noqa: BLE001
                pass
        render()

    def focus_entry() -> None:
        try:
            root.lift()
            root.focus_force()
            if str(entry.cget("state")) == "normal":
                entry.focus_force()
                entry.icursor(tk.END)
        except tk.TclError:
            pass

    tk.Button(
        btn_row,
        text="Refresh",
        command=render,
        bg=BTN,
        fg="#f1f5f9",
        activebackground="#475569",
        activeforeground="#fff",
        relief=tk.FLAT,
        padx=12,
        pady=6,
        cursor="hand2",
    ).pack(side=tk.LEFT)

    tk.Button(
        btn_row,
        text="Activate",
        command=activate,
        bg=BTN_OK,
        fg="#ecfdf5",
        activebackground="#047857",
        activeforeground="#fff",
        relief=tk.FLAT,
        padx=14,
        pady=6,
        cursor="hand2",
    ).pack(side=tk.LEFT, padx=(8, 0))

    tk.Button(
        btn_row,
        text="Close",
        command=root.destroy,
        bg=BTN,
        fg="#f1f5f9",
        activebackground="#475569",
        activeforeground="#fff",
        relief=tk.FLAT,
        padx=12,
        pady=6,
        cursor="hand2",
    ).pack(side=tk.RIGHT)

    entry.bind("<Return>", lambda _e: activate())
    root.bind("<Escape>", lambda _e: root.destroy())

    def close() -> None:
        global _window
        try:
            root.destroy()
        except tk.TclError:
            pass
        _window = None

    root.protocol("WM_DELETE_WINDOW", close)
    render()
    _window = root
    root.after(80, focus_entry)
    root.after(250, focus_entry)
    root.mainloop()
    _window = None


def show_reward_day_panel(
    service: "TrackerService",
    *,
    on_claimed: Callable[[], None] | None = None,
) -> None:
    """Open or raise the reward-day window (tk on a background thread)."""
    global _window

    if not service.user_id:
        log.warning("Cannot open reward day panel — tracker user_id not set")
        return

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
        kwargs={"service": service, "on_claimed": on_claimed},
        daemon=True,
        name="tracker-reward-gui",
    ).start()
