"""Load transcripts and references — backend engine + Studio helpers."""

from __future__ import annotations

from pathlib import Path

from backend.transcripts import sources as _sources
from backend.transcripts.sources import (
    MAX_PDF_PAGES,
    MAX_REFERENCE_FILE_CHARS,
    REFERENCE_EXTENSIONS,
    SOURCE_EXTENSIONS,
    TRANSCRIPT_EXTENSIONS,
    build_source_manifest,
    combine_transcript_sources,
    load_context_folder,
    load_reference_bundle,
    prepare_sources,
    reference_slice,
    resolve_source_path,
    split_source_paths,
)

_extract_pdf = _sources._extract_pdf


def load_source_file(path: Path, *, max_chars: int | None = None) -> str:
    """Load source text — uses studio _extract_pdf so tests can monkeypatch."""
    if not path.is_file():
        raise FileNotFoundError(f"Source not found: {path}")

    ext = path.suffix.lower()
    if ext not in SOURCE_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {ext}")

    limit = max_chars or (MAX_REFERENCE_FILE_CHARS if ext in REFERENCE_EXTENSIONS else None)
    if ext == ".pdf":
        return _extract_pdf(path, max_chars=limit)
    if ext == ".ipynb":
        return _sources._extract_ipynb(path, max_chars=limit)
    return _sources._read_text(path, max_chars=limit)


def check_pdf_deps() -> tuple[bool, str]:
    try:
        import pypdf  # noqa: F401

        return True, "pypdf installed — PDF sources supported"
    except ImportError:
        return False, "PDF support needs pypdf: pip install pypdf"


def combine_source_files(paths: list[Path]) -> str:
    """Legacy combine — prefer split + transcript-only for summarization."""
    transcripts, references = split_source_paths(paths)
    if transcripts:
        return combine_transcript_sources(transcripts)
    if references:
        return load_reference_bundle(references)
    raise ValueError("No content in selected files.")


def list_source_files(folder: Path | None = None) -> list[Path]:
    from transcript_studio.config import load_config

    root = folder or load_config().transcripts_path()
    root.mkdir(parents=True, exist_ok=True)
    files: list[Path] = []
    for ext in SOURCE_EXTENSIONS:
        files.extend(root.glob(f"*{ext}"))
    return sorted(set(files), key=lambda p: p.stat().st_mtime, reverse=True)


__all__ = [
    "MAX_PDF_PAGES",
    "MAX_REFERENCE_FILE_CHARS",
    "REFERENCE_EXTENSIONS",
    "SOURCE_EXTENSIONS",
    "TRANSCRIPT_EXTENSIONS",
    "_extract_pdf",
    "build_source_manifest",
    "check_pdf_deps",
    "combine_source_files",
    "combine_transcript_sources",
    "list_source_files",
    "load_context_folder",
    "load_reference_bundle",
    "load_source_file",
    "prepare_sources",
    "reference_slice",
    "resolve_source_path",
    "split_source_paths",
]
