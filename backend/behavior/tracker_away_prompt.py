"""Away-from-desk prompt when user returns from idle (RescueTime borrow)."""

from __future__ import annotations

import json
import logging
import threading
import time
import tkinter as tk
from pathlib import Path
from typing import Any, Callable

log = logging.getLogger("desktop_tracker")

_ROOT = Path(__file__).resolve().parent.parent.parent
_LOG_PATH = _ROOT / "data" / "behavior" / "away_log.json"
_MIN_IDLE_S = 600.0
_MIN_GAP_S = 900.0
_window_lock = threading.Lock()
_last_prompt_at = 0.0


def away_min_idle_s() -> float:
    return _MIN_IDLE_S


def log_away_response(
    *,
    choice: str,
    idle_seconds: float,
    user_id: int | None = None,
) -> dict[str, Any]:
    """Append away prompt response to local log."""
    item = {
        "choice": (choice or "ignore").strip().lower()[:32],
        "idle_seconds": round(float(idle_seconds), 1),
        "user_id": user_id,
        "ts": time.time(),
    }
    try:
        _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        items: list[dict[str, Any]] = []
        if _LOG_PATH.is_file():
            raw = json.loads(_LOG_PATH.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                items = [x for x in raw if isinstance(x, dict)]
        items.append(item)
        items = items[-100:]
        _LOG_PATH.write_text(json.dumps(items, indent=0), encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        log.debug("away log: %s", exc)
    return item


def _format_idle(idle_seconds: float) -> str:
    from backend.behavior.time_fmt import format_hours_mins

    return format_hours_mins(max(1, int(idle_seconds / 60)))


def _run_dialog(idle_seconds: float, on_choice: Callable[[str], None]) -> None:
    root = tk.Tk()
    root.title("CALT — Away from desk?")
    root.configure(bg="#0f172a")
    root.resizable(False, False)
    root.attributes("-topmost", True)

    frame = tk.Frame(root, bg="#0f172a", padx=20, pady=16)
    frame.pack(fill=tk.BOTH, expand=True)

    tk.Label(
        frame,
        text="Were you working away from the computer?",
        fg="#f8fafc",
        bg="#0f172a",
        font=("Segoe UI", 11, "bold"),
        wraplength=320,
        justify=tk.LEFT,
    ).pack(anchor=tk.W)

    tk.Label(
        frame,
        text=f"Away ~{_format_idle(idle_seconds)} — log it or dismiss.",
        fg="#94a3b8",
        bg="#0f172a",
        font=("Segoe UI", 9),
        wraplength=320,
        justify=tk.LEFT,
    ).pack(anchor=tk.W, pady=(6, 14))

    btn_row = tk.Frame(frame, bg="#0f172a")
    btn_row.pack(fill=tk.X)

    def pick(choice: str) -> None:
        try:
            on_choice(choice)
        finally:
            root.destroy()

    for label, choice, color in (
        ("Working", "working", "#059669"),
        ("Break", "break", "#475569"),
        ("Ignore", "ignore", "#334155"),
    ):
        tk.Button(
            btn_row,
            text=label,
            command=lambda c=choice: pick(c),
            bg=color,
            fg="#f8fafc",
            activebackground=color,
            activeforeground="#f8fafc",
            relief=tk.FLAT,
            padx=10,
            pady=6,
            font=("Segoe UI", 9),
        ).pack(side=tk.LEFT, padx=(0, 8))

    root.update_idletasks()
    w, h = root.winfo_width(), root.winfo_height()
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    root.geometry(f"+{max(0, sw - w - 24)}+{max(0, sh - h - 80)}")
    root.mainloop()


def show_away_prompt(
    idle_seconds: float,
    *,
    on_choice: Callable[[str], None],
) -> bool:
    """Show Tk prompt in a daemon thread. Returns False if throttled."""
    global _last_prompt_at
    now = time.time()
    if idle_seconds < _MIN_IDLE_S:
        return False
    if now - _last_prompt_at < _MIN_GAP_S:
        return False
    _last_prompt_at = now

    def worker() -> None:
        with _window_lock:
            try:
                _run_dialog(idle_seconds, on_choice)
            except Exception as exc:  # noqa: BLE001
                log.debug("away prompt ui: %s", exc)
                on_choice("ignore")

    threading.Thread(target=worker, name="away-prompt", daemon=True).start()
    return True
