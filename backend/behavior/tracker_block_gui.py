"""Popup when hard-block kills a game — work-first nudge + unlock progress."""

from __future__ import annotations

import logging
import threading
import tkinter as tk
from typing import Any

log = logging.getLogger("desktop_tracker")

_window_lock = threading.Lock()
_window: tk.Tk | None = None
_last_show_at = 0.0
_MIN_GAP_S = 45.0  # don't spam while Steam respawns helpers


def _fmt_minutes(m: int) -> str:
    m = max(0, int(m))
    if m < 60:
        return f"{m} min"
    h, rem = divmod(m, 60)
    if rem == 0:
        return f"{h}h"
    return f"{h}h {rem}m"


def _draw_ring(canvas: tk.Canvas, done: int, goal: int) -> None:
    canvas.delete("all")
    w = int(canvas["width"])
    h = int(canvas["height"])
    pad = 8
    x0, y0, x1, y1 = pad, pad, w - pad, h - pad
    canvas.create_oval(x0, y0, x1, y1, outline="#334155", width=10)
    goal = max(1, goal)
    frac = min(1.0, max(0.0, done / goal))
    # tk arc: 0° is 3 o'clock, extent counterclockwise; start at 90° (12 o'clock)
    extent = -frac * 360.0
    color = "#14b8a6" if frac >= 1.0 else "#f59e0b"
    if frac > 0.002:
        canvas.create_arc(
            x0,
            y0,
            x1,
            y1,
            start=90,
            extent=extent,
            style=tk.ARC,
            outline=color,
            width=10,
        )
    pct = int(round(frac * 100))
    canvas.create_text(
        w // 2,
        h // 2 - 6,
        text=f"{pct}%",
        fill="#f8fafc",
        font=("Segoe UI", 16, "bold"),
    )
    canvas.create_text(
        w // 2,
        h // 2 + 16,
        text="focus",
        fill="#94a3b8",
        font=("Segoe UI", 9),
    )


def _open_window(
    *,
    blocked_app: str,
    productive: int,
    goal: int,
    remaining: int,
) -> None:
    global _window

    root = tk.Tk()
    root.title("CALT — Games locked")
    root.configure(bg="#0f172a")
    root.resizable(False, False)
    root.attributes("-topmost", True)
    try:
        root.geometry("420x320+80+80")
    except tk.TclError:
        pass

    header = tk.Frame(root, bg="#0f172a", padx=16, pady=12)
    header.pack(fill=tk.X)
    tk.Label(
        header,
        text="Work first — then play",
        bg="#0f172a",
        fg="#f8fafc",
        font=("Segoe UI", 14, "bold"),
    ).pack(anchor=tk.W)
    tk.Label(
        header,
        text=f"Blocked: {blocked_app or 'game'}",
        bg="#0f172a",
        fg="#f87171",
        font=("Segoe UI", 10),
    ).pack(anchor=tk.W, pady=(4, 0))

    body = tk.Frame(root, bg="#1e293b", padx=16, pady=14)
    body.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 8))

    left = tk.Frame(body, bg="#1e293b")
    left.pack(side=tk.LEFT, padx=(0, 12))
    ring = tk.Canvas(left, width=120, height=120, bg="#1e293b", highlightthickness=0)
    ring.pack()
    _draw_ring(ring, productive, goal)

    right = tk.Frame(body, bg="#1e293b")
    right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    tk.Label(
        right,
        text="Finish today's productive focus goal to unlock games.",
        bg="#1e293b",
        fg="#cbd5e1",
        font=("Segoe UI", 10),
        wraplength=220,
        justify=tk.LEFT,
    ).pack(anchor=tk.W)

    stats = tk.Frame(right, bg="#1e293b")
    stats.pack(anchor=tk.W, pady=(12, 0), fill=tk.X)
    rows = [
        ("Done today", _fmt_minutes(productive)),
        ("Daily goal", _fmt_minutes(goal)),
        ("Still needed", _fmt_minutes(remaining)),
    ]
    for label, val in rows:
        row = tk.Frame(stats, bg="#1e293b")
        row.pack(fill=tk.X, pady=2)
        tk.Label(row, text=label, bg="#1e293b", fg="#94a3b8", font=("Segoe UI", 9)).pack(
            side=tk.LEFT
        )
        tk.Label(
            row,
            text=val,
            bg="#1e293b",
            fg="#f8fafc",
            font=("Segoe UI", 10, "bold"),
        ).pack(side=tk.RIGHT)

    # Progress bar under stats
    bar_wrap = tk.Frame(right, bg="#334155", height=8)
    bar_wrap.pack(fill=tk.X, pady=(14, 0))
    bar_wrap.pack_propagate(False)
    frac = min(1.0, max(0.0, productive / max(1, goal)))
    fill_w = max(2, int(220 * frac))
    fill = tk.Frame(bar_wrap, bg="#14b8a6" if frac >= 1 else "#f59e0b", width=fill_w)
    fill.place(x=0, y=0, relheight=1.0)

    btn_row = tk.Frame(root, bg="#0f172a", padx=16, pady=10)
    btn_row.pack(fill=tk.X)

    def close() -> None:
        global _window
        try:
            root.destroy()
        except tk.TclError:
            pass
        _window = None

    tk.Button(
        btn_row,
        text="Got it — back to work",
        command=close,
        bg="#0d9488",
        fg="#f0fdfa",
        activebackground="#14b8a6",
        activeforeground="#fff",
        relief=tk.FLAT,
        padx=14,
        pady=6,
        cursor="hand2",
        font=("Segoe UI", 10, "bold"),
    ).pack(side=tk.RIGHT)

    root.protocol("WM_DELETE_WINDOW", close)
    _window = root
    root.mainloop()
    _window = None


def show_hard_block_notice(
    *,
    blocked_app: str,
    gate: dict[str, Any] | None,
    force: bool = False,
) -> None:
    """Show (or refresh) the work-first unlock card. Debounced; non-blocking thread."""
    global _last_show_at, _window
    import time

    now = time.time()
    if not force and (now - _last_show_at) < _MIN_GAP_S:
        return
    g = gate or {}
    productive = int(g.get("productive_minutes") or 0)
    goal = int(g.get("daily_goal_minutes") or 240)
    remaining = int(g.get("remaining_minutes") or max(0, goal - productive))

    def runner() -> None:
        global _last_show_at
        with _window_lock:
            if _window is not None:
                try:
                    _window.lift()
                    _window.attributes("-topmost", True)
                    _last_show_at = time.time()
                    return
                except tk.TclError:
                    pass
            _last_show_at = time.time()
            try:
                _open_window(
                    blocked_app=blocked_app,
                    productive=productive,
                    goal=goal,
                    remaining=remaining,
                )
            except Exception as exc:  # noqa: BLE001
                log.warning("hard-block notice failed: %s", exc)

    threading.Thread(target=runner, name="hard-block-gui", daemon=True).start()
