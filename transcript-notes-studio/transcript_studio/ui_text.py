"""Tk text-widget helpers — keep large transcript previews responsive."""

from __future__ import annotations

import re
import tkinter as tk
from typing import Callable

# Above this size, word-wrap layout makes scrolling unusably slow in Tk.
_WRAP_LIMIT = 12_000
# Hard cap on characters inserted into preview panes.
_PREVIEW_CHAR_LIMIT = 40_000

_CHUNK_PROGRESS_RE = re.compile(r"chunk\s+(\d+)\s*/\s*(\d+)", re.I)


def format_preview_text(full: str, *, char_limit: int = _PREVIEW_CHAR_LIMIT) -> tuple[str, bool]:
    """Return display text and whether the source was truncated."""
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
    return tk.NONE if len(display_text) > _WRAP_LIMIT else tk.WORD


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
