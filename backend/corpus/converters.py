"""Convert PDF/EPUB sources to markdown (CPU-first)."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from backend.corpus.chunker import filter_chapter_markdown


def load_metadata(folder: Path) -> dict:
    for name in ("metadata.json", "metadata.json.example"):
        p = folder / name
        if p.is_file():
            return json.loads(p.read_text(encoding="utf-8"))
    return {}


def find_source_file(folder: Path, meta: dict) -> Path | None:
    if meta.get("filename"):
        candidate = folder / meta["filename"]
        if candidate.is_file():
            return candidate
    for ext in ("*.pdf", "*.epub", "*.md", "*.txt"):
        matches = sorted(folder.glob(ext))
        if matches:
            return matches[0]
    return None


def describe_missing_source(folder: Path, meta: dict) -> str:
    expected = meta.get("filename") or "any .pdf / .epub / .md / .txt"
    return (
        f"No source file in {folder}. "
        f"Expected: {expected}. "
        "Copy your book into this folder, then run ingest again. "
        "PowerShell example:\n"
        f'  Copy-Item "$env:USERPROFILE\\Downloads\\YOUR_BOOK.pdf" '
        f'"{folder / (meta.get("filename") or "Mathematics_for_ML.pdf")}"'
    )


def pdf_to_markdown(path: Path, *, chapter: int | None = None) -> str:
    try:
        import fitz  # PyMuPDF
    except ImportError as exc:
        raise RuntimeError("PyMuPDF required: pip install pymupdf") from exc

    doc = fitz.open(str(path))
    lines: list[str] = []
    try:
        for page_num, page in enumerate(doc, start=1):
            blocks = page.get_text("dict").get("blocks", [])
            page_lines: list[str] = []
            for block in blocks:
                if block.get("type") != 0:
                    continue
                for line in block.get("lines", []):
                    spans = line.get("spans", [])
                    if not spans:
                        continue
                    text = "".join(s.get("text", "") for s in spans).strip()
                    if not text:
                        continue
                    max_size = max(float(s.get("size", 12)) for s in spans)
                    if max_size >= 16:
                        page_lines.append(f"# {text}")
                    elif max_size >= 13:
                        page_lines.append(f"## {text}")
                    else:
                        page_lines.append(text)
            if page_lines:
                lines.append(f"\n<!-- page {page_num} -->\n")
                lines.extend(page_lines)
    finally:
        doc.close()

    md = strip_noise("\n".join(lines))
    if chapter is not None:
        md = filter_chapter_markdown(md, chapter)
    return md


def epub_to_markdown(path: Path) -> str:
    """Convert EPUB via pandoc if available."""
    try:
        result = subprocess.run(
            ["pandoc", str(path), "-t", "markdown", "--wrap=none"],
            capture_output=True,
            text=True,
            check=True,
            timeout=300,
        )
        return strip_noise(result.stdout)
    except FileNotFoundError as exc:
        raise RuntimeError(
            "EPUB ingest requires pandoc on PATH. Install pandoc or defer EPUB books."
        ) from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"pandoc failed: {exc.stderr}") from exc


def strip_noise(text: str) -> str:
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"^\s*\d+\s*$", "", text, flags=re.MULTILINE)
    return text.strip()


def file_to_markdown(path: Path, *, chapter: int | None = None) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return pdf_to_markdown(path, chapter=chapter)
    if suffix == ".epub":
        md = epub_to_markdown(path)
        if chapter is not None:
            md = filter_chapter_markdown(md, chapter)
        return md
    if suffix in (".md", ".markdown"):
        text = path.read_text(encoding="utf-8")
        if chapter is not None:
            text = filter_chapter_markdown(text, chapter)
        return text
    if suffix == ".txt":
        text = path.read_text(encoding="utf-8")
        if chapter is not None:
            text = filter_chapter_markdown(text, chapter)
        return text
    raise ValueError(f"Unsupported format: {suffix}")
