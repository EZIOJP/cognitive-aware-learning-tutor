"""Tests for lecture note PDF/DOCX export."""

import pytest

from backend.transcripts.note_export import build_export_html, export_note


@pytest.fixture()
def sample_note() -> str:
    return """# Intro

A short paragraph with **bold** text.

![Test slide](/api/transcripts/snapshots/live_captions_test/1.png)

```python
print("hello")
```

```mermaid
flowchart TD
    A --> B
```
"""


def test_build_export_html(sample_note):
    html = build_export_html(sample_note, title="Test Note", note_relative="lecture one/test.md")
    assert "<h1>Test Note</h1>" in html
    assert "Intro" in html
    assert "print" in html
    assert "mermaid" in html.lower() or "Mermaid" in html


def test_export_pdf_and_docx(sample_note):
    pytest.importorskip("xhtml2pdf")
    pytest.importorskip("docx")
    pdf, _, _ = export_note(sample_note, title="Test", note_relative="test.md", fmt="pdf")
    docx, _, _ = export_note(sample_note, title="Test", note_relative="test.md", fmt="docx")
    assert pdf[:4] == b"%PDF"
    assert docx[:2] == b"PK"
