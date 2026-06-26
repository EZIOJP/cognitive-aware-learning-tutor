"""Generate markdown lecture notes — thin Studio wrapper around backend chunk pipeline."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from transcript_studio.cleanup import clean_transcript
from transcript_studio.chunked_parse import parse_transcript_auto
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


def parse_transcript(
    raw: str,
    *,
    aggressive: bool = False,
    preserve_snapshots: bool = False,
    thorough: bool | None = None,
    on_progress: Callable[[str, float], None] | None = None,
    cancel_event: Callable[[], bool] | None = None,
) -> str:
    if not preserve_snapshots:
        raw = strip_snapshot_markers(raw)
    cfg = load_config()
    use_thorough = cfg.thorough_parse if thorough is None else thorough
    from transcript_studio.parse_throttle import speed_to_throttle

    throttle = speed_to_throttle(cfg.parse_speed)
    return parse_transcript_auto(
        raw,
        aggressive=aggressive,
        thorough=use_thorough,
        chunk_lines=throttle.chunk_lines,
        pause_sec=max(0.0, throttle.pause_ms / 1000.0),
        on_progress=on_progress,
        cancel_event=cancel_event,
    )


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
    pre_cleaned: str | None = None,
    legacy_pipeline: bool | None = None,
    **kwargs: object,
) -> tuple[Path, str]:
    """Clean transcript → backend chunk summarize (mermaid + code in prompt)."""
    from backend.transcripts.cleanup import clean_transcript as backend_clean
    from backend.transcripts.notes_generator import generate_notes_from_text as backend_generate

    cfg = load_config()
    if not llm_available(cfg):
        raise RuntimeError(
            "Local LLM is not enabled. Turn on LLM in settings and start Ollama or LM Studio."
        )

    use_legacy = cfg.legacy_notes_pipeline if legacy_pipeline is None else legacy_pipeline
    fast_mode = bool(kwargs.get("fast_mode", cfg.fast_mode if not use_legacy else True))
    if use_legacy:
        kwargs.setdefault("fast_mode", True)
        kwargs.setdefault("refine_second_pass", False)
        kwargs.setdefault("use_semantic_grouping", False)
        kwargs.setdefault("inject_wikilinks", False)
        kwargs.setdefault("use_tag_extraction", False)
        fast_mode = bool(kwargs.get("fast_mode", True))
    kwargs.setdefault("refine_second_pass", cfg.refine_second_pass and not fast_mode)
    kwargs.setdefault("enrich_with_references", cfg.enrich_with_references and not fast_mode)
    kwargs.setdefault("use_tag_extraction", cfg.use_tag_extraction and not fast_mode)
    kwargs.setdefault("max_chunks", cfg.max_llm_chunks)
    kwargs.setdefault("llm_pause_sec", cfg.llm_pause_sec)
    inject_wikilinks = bool(kwargs.pop("inject_wikilinks", cfg.inject_wikilinks and not use_legacy))

    def progress(msg: str) -> None:
        log.info(msg)
        if on_progress:
            on_progress(msg)

    if cancel_event and cancel_event():
        raise RuntimeError("Summarization cancelled.")

    if pre_cleaned and pre_cleaned.strip():
        cleaned = pre_cleaned.strip()
        progress("Using cleaned transcript from Tune step")
    elif use_legacy:
        cleaned = backend_clean(raw, aggressive=aggressive)
        progress("Legacy pipeline: single-pass backend cleanup")
    else:
        cleaned = parse_transcript(raw, aggressive=aggressive, preserve_snapshots=True)
    if not cleaned:
        raise ValueError("Transcript is empty after cleanup.")

    progress(f"Ready for LLM: {len(cleaned.split()):,} words ({len(cleaned):,} chars)")

    use_semantic = cfg.use_semantic_chunking and not fast_mode and not use_legacy
    if len(cleaned.split()) > 12_000:
        use_semantic = False
        progress("Large transcript — using word chunks instead of semantic grouping")
    kwargs.setdefault("use_semantic_grouping", use_semantic)

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

    if inject_wikilinks:
        try:
            from transcript_studio.wikilink_injector import inject_wikilinks

            progress("Injecting wikilinks…")
            inject_wikilinks(path, folder=path.parent)
            body = path.read_text(encoding="utf-8")
        except Exception as exc:
            log.warning("Wikilink injection skipped: %s", exc)
            progress(f"Wikilink injection skipped: {exc}")

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
    pre_cleaned: str | None = None,
    legacy_pipeline: bool | None = None,
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
        pre_cleaned=pre_cleaned,
        legacy_pipeline=legacy_pipeline,
        exclude_context_paths={p.resolve() for p in transcript_paths},
        **kwargs,
    )
