"""Tk text-widget helpers — keep large transcript previews responsive."""

from __future__ import annotations

import re
import tkinter as tk
from typing import Callable

# Hard cap on characters inserted into preview panes.
_PREVIEW_CHAR_LIMIT = 40_000
# Soft-wrap width when source text is one long line (legacy parse output).
_DISPLAY_WRAP_WIDTH = 100

_CHUNK_PROGRESS_RE = re.compile(r"chunk\s+(\d+)\s*/\s*(\d+)", re.I)


def _wrap_long_line(text: str, *, width: int = _DISPLAY_WRAP_WIDTH) -> str:
    """Break a single-line blob into rows — Notepad-style when parse omitted newlines."""
    if "\n" in text:
        return text
    words = text.split()
    if len(words) < 40:
        return text
    lines: list[str] = []
    current: list[str] = []
    length = 0
    for word in words:
        extra = len(word) + (1 if current else 0)
        if current and length + extra > width:
            lines.append(" ".join(current))
            current = [word]
            length = len(word)
        else:
            current.append(word)
            length += extra
    if current:
        lines.append(" ".join(current))
    return "\n".join(lines)


def format_preview_text(full: str, *, char_limit: int = _PREVIEW_CHAR_LIMIT) -> tuple[str, bool]:
    """Return display text and whether the source was truncated."""
    full = _wrap_long_line(full)
    if len(full) <= char_limit:
        return full, False
    cut = full[:char_limit]
    if "\n" in cut:
        cut = cut.rsplit("\n", 1)[0]
    notice = (
        f"\n\n--- Preview truncated ({len(full):,} chars total). "
        "Full text is kept in memory and written to disk on save. ---\n"
    )
    return cut + notice, True


def preview_wrap_mode(display_text: str) -> str:
    """Always word-wrap preview panes like Notepad."""
    return tk.WORD


def parse_chunk_progress(message: str) -> tuple[int, int] | None:
    match = _CHUNK_PROGRESS_RE.search(message)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def insert_text_chunked(
    widget: tk.Text,
    text: str,
    *,
    after_ms: int = 1,
    chunk_size: int = 16_384,
    on_complete: Callable[[], None] | None = None,
    schedule,
) -> None:
    """Insert large strings without freezing the event loop."""

    def step(offset: int = 0) -> None:
        try:
            if not widget.winfo_exists():
                return
            widget.configure(state=tk.NORMAL)
            if offset == 0:
                widget.delete("1.0", tk.END)
            end = min(offset + chunk_size, len(text))
            widget.insert(tk.END, text[offset:end])
            if end < len(text):
                schedule(after_ms, lambda: step(end))
                return
            widget.configure(state=tk.DISABLED)
            if on_complete:
                on_complete()
        except tk.TclError:
            return

    step(0)
