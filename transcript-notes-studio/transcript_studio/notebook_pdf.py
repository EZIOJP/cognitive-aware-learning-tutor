"""Parse flattened Colab/Jupyter PDF exports back into code and prose cells."""

from __future__ import annotations

import re

# Match: In [1]:, In [12]:, Out[1]:, Out [1]:
CELL_MARKER_RE = re.compile(r"(?:In\s*\[\d*\]:|Out\s*\[\d*\]:)", re.IGNORECASE)
EXECUTION_MARKER_LINE_RE = re.compile(r"^\s*(?:In\s*\[\d*\]:|Out\s*\[\d*\]:)\s*$", re.MULTILINE | re.IGNORECASE)
NOTEBOOK_FILENAME_HINTS = ("colab", "ipynb", "notebook", "jupyter")


def count_cell_markers(text: str) -> int:
    return len(CELL_MARKER_RE.findall(text))


def looks_like_notebook_pdf(text: str, filename: str = "") -> bool:
    name = filename.lower()
    if any(hint in name for hint in NOTEBOOK_FILENAME_HINTS):
        return True
    return count_cell_markers(text) >= 2


def parse_flattened_notebook_pdf(pdf_text: str) -> list[dict[str, str]]:
    """
    Reconstruct notebook cells from a flattened PDF text export.
    Matches standard Jupyter/Colab execution markers.
    """
    parts = CELL_MARKER_RE.split(pdf_text)
    markers = CELL_MARKER_RE.findall(pdf_text)

    if not markers:
        if pdf_text.strip():
            return [{"type": "prose", "content": pdf_text.strip()}]
        return []

    parsed_cells: list[dict[str, str]] = []
    leading = parts[0].strip() if parts else ""
    if leading:
        parsed_cells.append({"type": "prose", "content": leading})

    for i, marker in enumerate(markers):
        cell_body = parts[i + 1].strip() if i + 1 < len(parts) else ""
        full_cell = f"{marker}\n{cell_body}".strip() if cell_body else marker
        parsed_cells.append({"type": "code_or_output", "content": full_cell})

    trailing_idx = len(markers) + 1
    if trailing_idx < len(parts) and parts[trailing_idx].strip():
        parsed_cells.append({"type": "prose", "content": parts[trailing_idx].strip()})

    return parsed_cells


def strip_execution_markers(text: str) -> str:
    """Remove In [n]: / Out [n]: lines from notebook text."""
    lines = []
    for line in text.splitlines():
        if EXECUTION_MARKER_LINE_RE.match(line):
            continue
        cleaned = re.sub(r"^(?:In\s*\[\d*\]:|Out\s*\[\d*\]:)\s*", "", line, flags=re.IGNORECASE)
        lines.append(cleaned)
    return "\n".join(lines).strip()


def _cell_to_markdown(cell: dict[str, str]) -> str:
    content = cell["content"]
    if cell["type"] == "prose":
        return content

    body = strip_execution_markers(content)
    if not body:
        return ""

    lower = body.lower()
    if lower.startswith("error") or lower.startswith("traceback"):
        return f"```text\n{body}\n```"

    looks_like_code = any(kw in body for kw in ("import ", "def ", "class ", "=", "print(", "for ", "if "))
    fence = "python" if looks_like_code else "text"
    return f"```{fence}\n{body}\n```"


def format_notebook_cells_for_reference(cells: list[dict[str, str]]) -> str:
    """Convert parsed cells into markdown suitable for reference bundles."""
    blocks: list[str] = []
    for cell in cells:
        block = _cell_to_markdown(cell)
        if block:
            blocks.append(block)
    return "\n\n".join(blocks)


def format_notebook_pdf_text(pdf_text: str, *, filename: str = "") -> str:
    """Parse and format notebook PDF text if markers detected, else return stripped text."""
    if not looks_like_notebook_pdf(pdf_text, filename):
        return pdf_text.strip()
    cells = parse_flattened_notebook_pdf(pdf_text)
    formatted = format_notebook_cells_for_reference(cells)
    return formatted or pdf_text.strip()
