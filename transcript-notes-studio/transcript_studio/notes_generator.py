"""Generate markdown lecture notes — thin Studio wrapper around backend chunk pipeline."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from transcript_studio.cleanup import clean_transcript
from transcript_studio.config import load_config
from transcript_studio.llm_client import LlmOptions, generate, llm_available, options_from_config
from transcript_studio.snapshots import SNAPSHOT_MARKER_RE, inject_snapshot_images
from transcript_studio.source_loader import (
    combine_source_files,
    list_source_files,
    load_source_file,
    prepare_sources,
)

log = logging.getLogger(__name__)


def strip_snapshot_markers(raw: str) -> str:
    return SNAPSHOT_MARKER_RE.sub(lambda m: f"\n*[Slide {m.group(1)}]*\n", raw)


def parse_transcript(raw: str, *, aggressive: bool = False, preserve_snapshots: bool = False) -> str:
    if not preserve_snapshots:
        raw = strip_snapshot_markers(raw)
    return clean_transcript(raw, aggressive=aggressive)


def resolve_session_snapshots_dir(transcript_path: Path, session_dir: Path | None) -> Path | None:
    if session_dir and (session_dir / "snapshots").is_dir():
        snaps = session_dir / "snapshots"
        if any(snaps.glob("*.png")):
            return snaps
    parent = transcript_path.parent
    if (parent / "snapshots").is_dir() and any((parent / "snapshots").glob("*.png")):
        return parent / "snapshots"
    return None


def _to_backend_llm(opts: LlmOptions | None):
    from backend.core.ollama_client import LlmOptions as BackendLlmOptions

    if opts is None:
        return None
    return BackendLlmOptions(
        provider=opts.provider,
        base_url=opts.base_url,
        model=opts.model,
        max_tokens=opts.max_tokens,
        api_key=opts.api_key or None,
    )


def generate_notes_from_text(
    raw: str,
    *,
    title: str = "lecture",
    aggressive: bool = False,
    output_dir: Path | None = None,
    opts: LlmOptions | None = None,
    snapshots_dir: Path | None = None,
    note_output_path: Path | None = None,
    on_progress: Callable[[str], None] | None = None,
    cancel_event: Callable[[], bool] | None = None,
    reference_materials: str = "",
    transcript_stem: str | None = None,
    **kwargs: object,
) -> tuple[Path, str]:
    """Clean transcript → backend chunk summarize (mermaid + code in prompt)."""
    from backend.transcripts.notes_generator import generate_notes_from_text as backend_generate

    cfg = load_config()
    if not llm_available(cfg):
        raise RuntimeError(
            "Local LLM is not enabled. Turn on LLM in settings and start Ollama or LM Studio."
        )

    def progress(msg: str) -> None:
        log.info(msg)
        if on_progress:
            on_progress(msg)

    if cancel_event and cancel_event():
        raise RuntimeError("Summarization cancelled.")

    cleaned = parse_transcript(raw, aggressive=aggressive, preserve_snapshots=True)
    if not cleaned:
        raise ValueError("Transcript is empty after cleanup.")

    llm_opts = opts or options_from_config(cfg)

    def studio_generate(prompt: str) -> str | None:
        return generate(prompt, opts=llm_opts, timeout=240.0, use_cache=False)

    path, body = backend_generate(
        cleaned,
        title=title,
        aggressive=aggressive,
        output_dir=output_dir or cfg.notes_path(),
        note_output_path=note_output_path,
        on_progress=progress,
        already_cleaned=True,
        reference_materials=reference_materials,
        transcript_stem=transcript_stem,
        generate_fn=studio_generate,
        llm=_to_backend_llm(llm_opts),
        **kwargs,
    )

    if snapshots_dir and snapshots_dir.is_dir():
        if cancel_event and cancel_event():
            raise RuntimeError("Summarization cancelled.")
        progress(f"Embedding {len(list(snapshots_dir.glob('*.png')))} slide images…")
        body = inject_snapshot_images(body, snapshots_dir, note_path=path)
        path.write_text(body, encoding="utf-8")

    return path, body


def generate_notes_from_file(
    transcript_path: Path,
    *,
    title: str | None = None,
    aggressive: bool = False,
    output_dir: Path | None = None,
    opts: LlmOptions | None = None,
    session_dir: Path | None = None,
    on_progress: Callable[[str], None] | None = None,
    **kwargs: object,
) -> tuple[Path, str]:
    if not transcript_path.is_file():
        raise FileNotFoundError(f"Transcript not found: {transcript_path}")
    raw = load_source_file(transcript_path)
    note_title = title or transcript_path.stem.replace("_", " ")
    snaps = resolve_session_snapshots_dir(transcript_path, session_dir)
    if not aggressive and "live_captions" in transcript_path.name.lower():
        aggressive = True
    return generate_notes_from_text(
        raw,
        title=note_title,
        aggressive=aggressive,
        output_dir=output_dir,
        opts=opts,
        snapshots_dir=snaps,
        on_progress=on_progress,
        **kwargs,
    )


def list_transcripts(folder: Path | None = None) -> list[Path]:
    return list_source_files(folder)


def combine_transcript_files(paths: list[Path]) -> str:
    return combine_source_files(paths)


def generate_notes_from_files(
    transcript_paths: list[Path],
    *,
    title: str = "lecture",
    aggressive: bool = False,
    output_dir: Path | None = None,
    opts: LlmOptions | None = None,
    session_dir: Path | None = None,
    on_progress: Callable[[str], None] | None = None,
    on_step: Callable[[int, int, str], None] | None = None,
    cancel_event: Callable[[], bool] | None = None,
    **kwargs: object,
) -> tuple[Path, str]:
    if not transcript_paths:
        raise ValueError("Select at least one source file.")

    transcript_text, reference_text, auto_aggressive, _manifest = prepare_sources(transcript_paths)
    if auto_aggressive and not aggressive:
        aggressive = True

    primary = transcript_paths[0]
    snaps = resolve_session_snapshots_dir(primary, session_dir)
    if not snaps:
        for p in transcript_paths:
            snaps = resolve_session_snapshots_dir(p, session_dir)
            if snaps:
                break

    def progress(msg: str) -> None:
        log.info(msg)
        if on_progress:
            on_progress(msg)

    if reference_text:
        progress(f"Reference material: {len(reference_text.split())} words")

    return generate_notes_from_text(
        transcript_text,
        title=title,
        aggressive=aggressive,
        output_dir=output_dir,
        opts=opts,
        snapshots_dir=snaps,
        reference_materials=reference_text,
        transcript_stem=primary.stem,
        on_progress=progress,
        cancel_event=cancel_event,
        **kwargs,
    )
