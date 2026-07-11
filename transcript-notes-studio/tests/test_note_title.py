"""Unit tests for classic auto note title / slug."""

from __future__ import annotations

from transcript_studio.note_title import _slugify, suggest_note_title


def test_slugify_basic() -> None:
    assert _slugify("NumPy arrays and DAV intro") == "numpy_arrays_and_dav_intro"


def test_slugify_strips_markdown() -> None:
    assert _slugify('## "Hello World!"') == "hello_world"


def test_suggest_note_title_uses_llm() -> None:
    def gen(_prompt: str) -> str:
        return "NumPy broadcasting basics"

    display, slug = suggest_note_title("lots of numpy talk…", generate_fn=gen)
    assert display == "NumPy broadcasting basics"
    assert slug == "numpy_broadcasting_basics"


def test_suggest_note_title_fallback() -> None:
    display, slug = suggest_note_title("", generate_fn=lambda _p: None, fallback="live_captions_x")
    assert "live captions" in display.lower() or "live_captions" in display
    assert slug.startswith("live")
