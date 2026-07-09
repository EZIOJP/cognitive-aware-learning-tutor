"""Detailed error dialog for Transcript Notes Studio — keeps the app open on failure."""

from __future__ import annotations

import traceback
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk


def format_exception(exc: BaseException) -> str:
    return "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))


def show_detailed_error(
    parent: tk.Misc | None,
    *,
    title: str,
    summary: str,
    details: str,
    log_path: str = "",
) -> None:
    """Modal error window with scrollable traceback; falls back to messagebox."""
    body = summary.strip()
    if log_path:
        body = f"{body}\n\nLog file:\n{log_path}"

    try:
        if parent is None or not parent.winfo_exists():
            raise tk.TclError("no parent")

        win = tk.Toplevel(parent)
        win.title(title)
        win.geometry("720x420")
        win.minsize(480, 280)
        win.transient(parent)
        win.grab_set()

        ttk.Label(win, text=summary, wraplength=680, justify=tk.LEFT).pack(
            anchor=tk.W, padx=12, pady=(12, 6)
        )
        if log_path:
            ttk.Label(win, text=f"Log: {log_path}", foreground="#6b7280").pack(
                anchor=tk.W, padx=12, pady=(0, 6)
            )

        text = scrolledtext.ScrolledText(win, wrap=tk.WORD, height=16, font=("Consolas", 9))
        text.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 8))
        text.insert(tk.END, details.strip() or summary)
        text.configure(state=tk.DISABLED)

        btn_row = ttk.Frame(win)
        btn_row.pack(fill=tk.X, padx=12, pady=(0, 12))

        def copy_details() -> None:
            win.clipboard_clear()
            win.clipboard_append(details.strip() or summary)
            win.update_idletasks()

        ttk.Button(btn_row, text="Copy details", command=copy_details).pack(side=tk.LEFT)
        ttk.Button(btn_row, text="Close", command=win.destroy).pack(side=tk.RIGHT)
        win.protocol("WM_DELETE_WINDOW", win.destroy)
        win.focus_set()
    except tk.TclError:
        messagebox.showerror(title, body, parent=parent)
