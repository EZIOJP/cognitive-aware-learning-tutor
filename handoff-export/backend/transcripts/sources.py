"""Load transcripts and reference files for lecture-note generation."""

from __future__ import annotations

import json
from pathlib import Path

from backend.paths import NOTES_DIR, TRANSCRIPTS_DIR

SOURCE_EXTENSIONS = {".txt", ".md", ".pdf", ".ipynb"}
TRANSCRIPT_EXTENSIONS = {".txt"}
REFERENCE_EXTENSIONS = {".pdf", ".md", ".ipynb"}
MAX_PDF_PAGES = 300
MAX_REFERENCE_FILE_CHARS = 80_000


def _read_text(path: Path, *, max_chars: int | None = None) -> str:
    text = path.read_text(encoding="utf-8", errors="replace")
    if max_chars and len(text) > max_chars:
        return text[:max_chars] + "\n\n… [truncated]"
    return text


def _extract_ipynb(path: Path, *, max_chars: int | None = None) -> str:
    data = json.loads(path.read_text(encoding="utf-8"))
    parts: list[str] = []
    for cell in data.get("cells", []):
        src = cell.get("source", [])
        if isinstance(src, list):
            src = "".join(src)
        src = str(src).strip()
        if src:
            parts.append(src)
    text = "\n\n".join(parts)
    if max_chars and len(text) > max_chars:
        return text[:max_chars] + "\n\n… [truncated]"
    return text


def _extract_pdf(path: Path, *, max_chars: int | None = None) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("PDF support needs pypdf: pip install pypdf") from exc

    reader = PdfReader(str(path))
    parts: list[str] = []
    total = 0
    for i, page in enumerate(reader.pages):
        if i >= MAX_PDF_PAGES:
            break
        text = (page.extract_text() or "").strip()
        if not text:
            continue
        if max_chars and total + len(text) > max_chars:
            parts.append(text[: max_chars - total])
            break
        parts.append(text)
        total += len(text)
    if not parts:
        raise ValueError(f"No extractable text in {path.name}")
    return "\n\n".join(parts)


def load_source_file(path: Path, *, max_chars: int | None = None) -> str:
    if not path.is_file():
        raise FileNotFoundError(f"Source not found: {path}")

    ext = path.suffix.lower()
    if ext not in SOURCE_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {ext}")

    limit = max_chars or (MAX_REFERENCE_FILE_CHARS if ext in REFERENCE_EXTENSIONS else None)
    if ext == ".pdf":
        return _extract_pdf(path, max_chars=limit)
    if ext == ".ipynb":
        return _extract_ipynb(path, max_chars=limit)
    return _read_text(path, max_chars=limit)


def split_source_paths(paths: list[Path]) -> tuple[list[Path], list[Path]]:
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
    return "\n\n---\n\n".join(parts) if parts else ""


def combine_transcript_sources(paths: list[Path]) -> str:
    parts: list[str] = []
    for path in paths:
        text = load_source_file(path).strip()
        if text:
            label = path.stem.replace("_", " ")
            parts.append(f"--- Transcript: {label} ({path.name}) ---\n\n{text}")
    if not parts:
        raise ValueError("No transcript content in selected .txt files.")
    return "\n\n".join(parts) + "\n"


def build_source_manifest(paths: list[Path]) -> str:
    transcripts, references = split_source_paths(paths)
    lines = [
        "Source manifest — use these names for ## headings and narrative flow:",
        "Order sources follow the class session (transcript first, then references).",
    ]
    for index, path in enumerate(transcripts, start=1):
        label = path.stem.replace("_", " ")
        lines.append(
            f"{index}. TRANSCRIPT `{path.name}` ({label}) — live lecture voice; "
            "preserve how the instructor explained concepts in class."
        )
    for index, path in enumerate(references, start=len(transcripts) + 1):
        label = path.stem.replace("_", " ")
        if path.suffix.lower() == ".ipynb":
            role = "Colab notebook"
        elif path.suffix.lower() == ".pdf":
            role = "PDF slides/handout"
        else:
            role = "reference notes"
        lines.append(
            f"{index}. REFERENCE `{path.name}` ({label}) — {role}; "
            "weave runnable examples under the matching lecture topic."
        )
    return "\n".join(lines)


def prepare_sources(paths: list[Path]) -> tuple[str, str, bool, str]:
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
    manifest = build_source_manifest(paths)
    return transcript_text, reference_text, auto_aggressive, manifest


def reference_slice(reference: str, chunk_index: int, total_chunks: int, *, window: int = 6000) -> str:
    if not reference or total_chunks < 1:
        return ""
    if len(reference) <= window:
        return reference
    step = max(window, len(reference) // total_chunks)
    start = min((chunk_index - 1) * step, max(0, len(reference) - window))
    return reference[start : start + window]


def load_context_folder(folder: Path, *, exclude_paths: set[Path] | None = None) -> str:
    """Load reference files from a folder — PDF/md/ipynb/py only (not raw .txt transcripts)."""
    if not folder.is_dir():
        return ""
    exclude = {p.resolve() for p in (exclude_paths or set())}
    ref_extensions = {".md", ".pdf", ".ipynb", ".py"}
    parts: list[str] = []
    total_chars = 0
    max_total = 240_000
    for path in sorted(folder.rglob("*")):
        if not path.is_file() or path.resolve() in exclude:
            continue
        if path.suffix.lower() not in ref_extensions:
            continue
        try:
            text = load_source_file(path, max_chars=12_000).strip()
        except (OSError, ValueError, RuntimeError):
            continue
        if not text:
            continue
        block = f"### Context: {path.name}\n\n{text}"
        if total_chars + len(block) > max_total:
            break
        parts.append(block)
        total_chars += len(block)
    return "\n\n---\n\n".join(parts) if parts else ""


def resolve_source_path(relative_or_name: str) -> Path:
    from backend.paths import NOTES_DIR, TRANSCRIPTS_DIR

    rel = relative_or_name.replace("\\", "/").lstrip("/")
    if ".." in rel.split("/"):
        raise ValueError("Invalid source path.")

    transcript = (TRANSCRIPTS_DIR / rel).resolve()
    if transcript.is_file() and transcript.is_relative_to(TRANSCRIPTS_DIR.resolve()):
        return transcript

    note = (NOTES_DIR / rel).resolve()
    if note.is_file() and note.is_relative_to(NOTES_DIR.resolve()):
        return note

    raise FileNotFoundError(f"Source not found: {relative_or_name}")
