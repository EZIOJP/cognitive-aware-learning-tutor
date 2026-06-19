"""Load text from transcripts, markdown, PDF, and notebooks for summarization."""

from __future__ import annotations

from pathlib import Path

from transcript_studio.context_loader import extract_ipynb, read_text_file
from transcript_studio.notebook_pdf import format_notebook_pdf_text, looks_like_notebook_pdf

SOURCE_EXTENSIONS = {".txt", ".md", ".pdf", ".ipynb"}
TRANSCRIPT_EXTENSIONS = {".txt"}
REFERENCE_EXTENSIONS = {".pdf", ".md", ".ipynb"}

MAX_PDF_PAGES = 300
MAX_REFERENCE_FILE_CHARS = 80_000


def check_pdf_deps() -> tuple[bool, str]:
    try:
        import pypdf  # noqa: F401

        return True, "pypdf installed — PDF sources supported"
    except ImportError:
        return False, "PDF support needs pypdf: pip install pypdf"


def _extract_pdf(path: Path, *, max_chars: int | None = None) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("PDF support needs pypdf: pip install pypdf") from exc

    try:
        reader = PdfReader(str(path))
    except Exception as exc:
        raise RuntimeError(f"Could not read PDF: {path.name}") from exc

    if getattr(reader, "is_encrypted", False):
        try:
            reader.decrypt("")
        except Exception as exc:
            raise RuntimeError(f"PDF is password-protected: {path.name}") from exc

    parts: list[str] = []
    total = 0
    for i, page in enumerate(reader.pages):
        if i >= MAX_PDF_PAGES:
            parts.append(f"\n… [truncated after {MAX_PDF_PAGES} pages]")
            break
        text = (page.extract_text() or "").strip()
        if not text:
            continue
        if max_chars and total + len(text) > max_chars:
            parts.append(text[: max_chars - total] + "\n\n… [truncated]")
            break
        parts.append(text)
        total += len(text)

    if not parts:
        raise ValueError(
            f"No extractable text in {path.name} — scanned/image PDFs need OCR (not supported yet)."
        )
    raw = "\n\n".join(parts)
    if looks_like_notebook_pdf(raw, path.name):
        return format_notebook_pdf_text(raw, filename=path.name)
    return raw


def load_source_file(path: Path, *, max_chars: int | None = None) -> str:
    if not path.is_file():
        raise FileNotFoundError(f"Source not found: {path}")

    ext = path.suffix.lower()
    if ext not in SOURCE_EXTENSIONS:
        raise ValueError(
            f"Unsupported file type {ext!r} — use {', '.join(sorted(SOURCE_EXTENSIONS))}"
        )

    limit = max_chars or (MAX_REFERENCE_FILE_CHARS if ext in REFERENCE_EXTENSIONS else None)

    if ext == ".pdf":
        return _extract_pdf(path, max_chars=limit)
    if ext == ".ipynb":
        text = extract_ipynb(path, max_chars=limit or MAX_REFERENCE_FILE_CHARS)
        return text

    text = read_text_file(path, max_chars=limit)
    return text


def split_source_paths(paths: list[Path]) -> tuple[list[Path], list[Path]]:
    """Split selected files into lecture transcript(s) vs reference (PDF/Colab/slides)."""
    transcripts: list[Path] = []
    references: list[Path] = []
    for path in paths:
        ext = path.suffix.lower()
        if ext in TRANSCRIPT_EXTENSIONS:
            transcripts.append(path)
        elif ext in REFERENCE_EXTENSIONS:
            references.append(path)
    return transcripts, references


def load_reference_bundle(paths: list[Path]) -> str:
    parts: list[str] = []
    for path in paths:
        try:
            text = load_source_file(path).strip()
        except (OSError, ValueError, RuntimeError):
            continue
        if not text:
            continue
        label = path.stem.replace("_", " ")
        parts.append(f"### Reference: {label} ({path.name})\n\n{text}")
    if not parts:
        return ""
    return "\n\n---\n\n".join(parts)


def combine_transcript_sources(paths: list[Path]) -> str:
    parts: list[str] = []
    for path in paths:
        text = load_source_file(path).strip()
        if not text:
            continue
        label = path.stem.replace("_", " ")
        parts.append(f"--- Transcript: {label} ({path.name}) ---\n\n{text}")
    if not parts:
        raise ValueError("No transcript content in selected .txt files.")
    return "\n\n".join(parts) + "\n"


def combine_source_files(paths: list[Path]) -> str:
    """Legacy combine — prefer split + transcript-only for summarization."""
    transcripts, references = split_source_paths(paths)
    if transcripts:
        return combine_transcript_sources(transcripts)
    if references:
        return load_reference_bundle(references)
    raise ValueError("No content in selected files.")


def prepare_sources(paths: list[Path]) -> tuple[str, str, bool]:
    """
    Prepare lecture transcript text, reference bundle, and whether aggressive dedup is recommended.
    """
    transcripts, references = split_source_paths(paths)
    auto_aggressive = any("live_captions" in p.name.lower() for p in transcripts)

    if transcripts:
        transcript_text = combine_transcript_sources(transcripts)
    elif references:
        transcript_text = load_reference_bundle(references)
        references = []
    else:
        raise ValueError("No supported source files selected.")

    reference_text = load_reference_bundle(references)
    return transcript_text, reference_text, auto_aggressive


def reference_slice(reference: str, chunk_index: int, total_chunks: int, *, window: int = 6000) -> str:
    if not reference or total_chunks < 1:
        return ""
    if len(reference) <= window:
        return reference
    step = max(window, len(reference) // total_chunks)
    start = min((chunk_index - 1) * step, max(0, len(reference) - window))
    return reference[start : start + window]


def list_source_files(folder: Path | None = None) -> list[Path]:
    from transcript_studio.config import load_config

    root = folder or load_config().transcripts_path()
    root.mkdir(parents=True, exist_ok=True)
    files: list[Path] = []
    for ext in SOURCE_EXTENSIONS:
        files.extend(root.glob(f"*{ext}"))
    return sorted(set(files), key=lambda p: p.stat().st_mtime, reverse=True)
