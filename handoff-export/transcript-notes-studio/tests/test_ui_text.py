from transcript_studio.ui_text import format_preview_text, parse_chunk_progress, preview_wrap_mode

import tkinter as tk


def test_format_preview_text_truncates():
    full = "a" * 50_000
    display, truncated = format_preview_text(full, char_limit=1000)
    assert truncated
    assert len(display) < 1200
    assert "truncated" in display.lower()


def test_preview_wrap_mode_large_uses_none():
    assert preview_wrap_mode("x" * 20_000) == tk.NONE
    assert preview_wrap_mode("short") == tk.WORD


def test_parse_chunk_progress():
    assert parse_chunk_progress("Summarizing chunk 3/12 (420 words)…") == (3, 12)
    assert parse_chunk_progress("Loading model") is None
