"""Today's planner timetable — lightweight tkinter popup from system tray."""

from __future__ import annotations

import logging
import threading
import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING

from backend.behavior.tracker_plan import DayBlockRow, fetch_today_schedule

log = logging.getLogger("desktop_tracker")

if TYPE_CHECKING:
    from backend.behavior.tracker_service import TrackerService

_window_lock = threading.Lock()
_window: tk.Tk | None = None


def _fmt_time(dt) -> str:
    return dt.astimezone().strftime("%H:%M")


def _status_label(row: DayBlockRow) -> str:
    if row.is_current:
        return f"now · {row.minutes_left}m left"
    if row.status == "in_progress":
        return "in progress"
    if row.status == "done":
        return "done"
    return row.status


def _build_rows(parent: tk.Frame, rows: list[DayBlockRow]) -> None:
    for child in parent.winfo_children():
        child.destroy()

    if not rows:
        tk.Label(
            parent,
            text="No blocks scheduled today.\nImport a plan or enable daily routines.",
            bg="#1e293b",
            fg="#94a3b8",
            font=("Segoe UI", 10),
            justify=tk.LEFT,
            padx=12,
            pady=16,
        ).pack(anchor=tk.W)
        return

    for row in rows:
        bg = "#064e3b" if row.is_current else "#1e293b"
        fg = "#ecfdf5" if row.is_current else "#e2e8f0"
        sub_fg = "#6ee7b7" if row.is_current else "#94a3b8"

        frame = tk.Frame(parent, bg=bg, padx=10, pady=8)
        frame.pack(fill=tk.X, pady=2)

        tk.Label(
            frame,
            text=f"{_fmt_time(row.start_at)} – {_fmt_time(row.end_at)}",
            bg=bg,
            fg=sub_fg,
            font=("Segoe UI", 9),
            anchor=tk.W,
        ).pack(fill=tk.X)

        tk.Label(
            frame,
            text=row.title,
            bg=bg,
            fg=fg,
            font=("Segoe UI", 10, "bold"),
            anchor=tk.W,
            wraplength=360,
            justify=tk.LEFT,
        ).pack(fill=tk.X)

        meta = f"{row.category} · {_status_label(row)}"
        tk.Label(
            frame,
            text=meta,
            bg=bg,
            fg=sub_fg,
            font=("Segoe UI", 8),
            anchor=tk.W,
        ).pack(fill=tk.X)


def _open_window(user_id: int) -> None:
    global _window

    root = tk.Tk()
    root.title("CALT — Today's plan")
    root.configure(bg="#0f172a")
    root.geometry("420x520")
    root.minsize(360, 320)

    header = tk.Frame(root, bg="#0f172a", padx=12, pady=10)
    header.pack(fill=tk.X)
    tk.Label(
        header,
        text="Today's timetable",
        bg="#0f172a",
        fg="#f8fafc",
        font=("Segoe UI", 13, "bold"),
    ).pack(anchor=tk.W)
    tk.Label(
        header,
        text="Planner blocks for today (read-only)",
        bg="#0f172a",
        fg="#64748b",
        font=("Segoe UI", 9),
    ).pack(anchor=tk.W)

    canvas = tk.Canvas(root, bg="#1e293b", highlightthickness=0, borderwidth=0)
    scrollbar = ttk.Scrollbar(root, orient=tk.VERTICAL, command=canvas.yview)
    body = tk.Frame(canvas, bg="#1e293b")
    body.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.create_window((0, 0), window=body, anchor=tk.NW)
    canvas.configure(yscrollcommand=scrollbar.set)
    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(8, 0), pady=(0, 8))
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=(0, 8), padx=(0, 8))

    btn_row = tk.Frame(root, bg="#0f172a", padx=12, pady=8)
    btn_row.pack(fill=tk.X)

    def refresh() -> None:
        try:
            rows = fetch_today_schedule(user_id)
            _build_rows(body, rows)
        except Exception as exc:  # noqa: BLE001
            log.warning("Timetable refresh failed: %s", exc)

    tk.Button(
        btn_row,
        text="Refresh",
        command=refresh,
        bg="#334155",
        fg="#f1f5f9",
        activebackground="#475569",
        activeforeground="#fff",
        relief=tk.FLAT,
        padx=12,
        pady=4,
        cursor="hand2",
    ).pack(side=tk.LEFT)

    tk.Button(
        btn_row,
        text="Hide",
        command=root.withdraw,
        bg="#334155",
        fg="#f1f5f9",
        activebackground="#475569",
        activeforeground="#fff",
        relief=tk.FLAT,
        padx=12,
        pady=4,
        cursor="hand2",
    ).pack(side=tk.RIGHT)

    root.protocol("WM_DELETE_WINDOW", root.withdraw)

    refresh()
    _window = root
    root.mainloop()
    _window = None


def show_today_schedule(user_id: int) -> None:
    """Open or raise the timetable window (runs tk on a background thread)."""
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
        args=(user_id,),
        daemon=True,
        name="tracker-timetable-gui",
    ).start()


def show_today_schedule_for_service(service: TrackerService) -> None:
    uid = service.user_id
    if not uid:
        log.warning("Cannot show timetable — tracker user_id not set")
        return
    show_today_schedule(uid)
