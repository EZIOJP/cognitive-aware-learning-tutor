"""Tests for ASR punctuation restoration."""

from unittest.mock import patch

from backend.transcripts.asr_restore import (
    _heuristic_restore,
    is_available,
    maybe_restore_asr,
    restore_punctuation,
)


def test_heuristic_restore_adds_period_and_caps():
    raw = "hello world\nthis is a test"
    out = _heuristic_restore(raw)
    assert out.startswith("Hello")
    assert "world." in out


def test_maybe_restore_skips_when_disabled():
    raw = "line one\nline two " * 30
    cleaned = "same text"
    assert maybe_restore_asr(cleaned, raw, enabled=False) == cleaned


@patch("backend.transcripts.asr_restore.is_available", return_value=False)
def test_restore_punctuation_heuristic_fallback(_mock):
    out = restore_punctuation("hello there")
    assert out[0].isupper()
