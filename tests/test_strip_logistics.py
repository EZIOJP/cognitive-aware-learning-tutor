"""Tests for logistics section stripping."""

from backend.transcripts.cleanup import strip_logistics_sections


def test_strip_logistics_removes_ui_session_sections():
    md = """# Lecture

## User Interface (UI) Familiarization

- **Definition**: UI refers to the means by which a user interacts.

## Session Structure

- Format: lectures and Q&A.

## NumPy Arrays

NumPy provides ndarray for numerical computing.
<!-- cite: abc-123 -->

The array stores homogeneous data.
"""
    out = strip_logistics_sections(md)
    assert "User Interface" not in out
    assert "Session Structure" not in out
    assert "NumPy Arrays" in out
    assert "cite: abc-123" in out


def test_strip_logistics_keeps_cited_section():
    md = """## Note-Taking Strategy

Some tips.
<!-- cite: x1 -->
"""
    out = strip_logistics_sections(md)
    assert "Note-Taking Strategy" in out
