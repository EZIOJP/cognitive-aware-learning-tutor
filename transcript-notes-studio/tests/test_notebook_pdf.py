"""Tests for Colab/Jupyter PDF notebook parsing."""

from __future__ import annotations

from transcript_studio.notebook_pdf import (
    count_cell_markers,
    format_notebook_cells_for_reference,
    format_notebook_pdf_text,
    looks_like_notebook_pdf,
    parse_flattened_notebook_pdf,
    strip_execution_markers,
)

SAMPLE_FLATTENED = """
Introduction to NumPy

This notebook covers array basics.

In [1]:
import numpy as np
x = np.array([1, 2, 3])

Out[1]:
array([1, 2, 3])

In [2]:
print(x.mean())

Out [2]:
2.0

Summary of key points.
"""


def test_count_cell_markers() -> None:
    assert count_cell_markers(SAMPLE_FLATTENED) == 4


def test_looks_like_notebook_pdf_by_markers() -> None:
    assert looks_like_notebook_pdf(SAMPLE_FLATTENED) is True
    assert looks_like_notebook_pdf("plain slide text") is False


def test_looks_like_notebook_pdf_by_filename() -> None:
    assert looks_like_notebook_pdf("one marker In [1]: only", "lecture1_numpy.ipynb___Colab.pdf") is True


def test_parse_flattened_notebook_pdf() -> None:
    cells = parse_flattened_notebook_pdf(SAMPLE_FLATTENED)
    types = [c["type"] for c in cells]
    assert "prose" in types
    assert "code_or_output" in types
    code_cells = [c for c in cells if c["type"] == "code_or_output"]
    assert any("import numpy" in c["content"] for c in code_cells)


def test_strip_execution_markers() -> None:
    raw = "In [1]:\nimport numpy as np\nOut [2]:\n42"
    cleaned = strip_execution_markers(raw)
    assert "In [1]:" not in cleaned
    assert "Out [2]:" not in cleaned
    assert "import numpy as np" in cleaned


def test_format_notebook_cells_for_reference() -> None:
    cells = parse_flattened_notebook_pdf(SAMPLE_FLATTENED)
    formatted = format_notebook_cells_for_reference(cells)
    assert "```python" in formatted or "```text" in formatted
    assert "In [1]:" not in formatted


def test_format_notebook_pdf_text_plain_passthrough() -> None:
    plain = "Slide deck without notebook markers."
    assert format_notebook_pdf_text(plain) == plain


def test_truncated_import_at_page_break() -> None:
    text = "In [1]:\nimport num\n\nIn [2]:\nnp.array([1])"
    formatted = format_notebook_pdf_text(text)
    assert "import num" in formatted
    assert "In [1]:" not in formatted
