"""Generate markdown lecture notes — thin Studio wrapper around backend chunk pipeline."""
from __future__ import annotations
import logging
from pathlib import Path
from typing import Callable
from transcript_studio.chunked_parse import parse_transcript_auto
from transcript_studio.config import load_config
from transcript_studio.gateway_llm import (
    llm_generate_available,
    make_gateway_generate_fn,
    resolve_for_generate,
    to_backend_llm,
)
from transcript_studio.llm_client import LlmOptions, options_from_config
from transcript_studio.snapshots import SNAPSHOT_MARKER_RE, inject_snapshot_images
from transcript_studio.source_loader import (
    combine_source_files,
    list_source_files,
    load_source_file,
    prepare_sources,
)

log = logging.getLogger(__name__)

# Last generate grounding / mode meta (Studio UI + tests).
_LAST_GENERATE_META: dict[str, object] = {}


def last_generate_meta() -> dict[str, object]:
    """Return grounding_status / grounding_reason / mode from the last generate call."""
    return dict(_LAST_GENERATE_META)


def _set_generate_meta(*, mode: str, rag: dict | None = None) -> None:
    status = None
    reason = None
    if isinstance(rag, dict):
        status = rag.get("grounding_status")
        reason = rag.get("grounding_reason")
    if status is None:
        status = "degraded" if str(mode).startswith("legacy") else "grounded"
        reason = "no_textbook_chunks_retrieved" if status == "degraded" else None
    _LAST_GENERATE_META.clear()
    _LAST_GENERATE_META.update(
        {
            "mode": mode,
            "grounding_status": status,
            "grounding_reason": reason,
        }
    )


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
) -> tuple[Path, str, str]:
    """Clean transcript → backend text-only chunk summarize → final visual enrich pass. Returns (path, body, mode)."""
    from backend.transcripts.cleanup import clean_transcript as backend_clean
    from backend.transcripts.notes_generator import generate_notes_from_text as backend_generate
    cfg = load_config()
    use_legacy = cfg.legacy_notes_pipeline if legacy_pipeline is None else legacy_pipeline
    classic = bool(kwargs.pop("classic_lmstudio", False)) or use_legacy
    if classic:
        # Direct LM Studio only — do not require cloud gateway
        cfg.llm_use_gateway = False
        if opts is not None:
            cfg.llm_provider = "lmstudio"
            cfg.llm_base_url = opts.base_url
            cfg.llm_model = opts.model
        from transcript_studio.llm_client import llm_reachable

        if not llm_reachable(cfg):
            raise RuntimeError(
                "LM Studio is offline. Start the local server and load your Gemma model "
                f"({getattr(opts, 'base_url', cfg.llm_base_url)})."
            )
    elif not llm_generate_available(cfg):
        raise RuntimeError(
            "LLM is not available. Configure the repo AI handler (root .env: OLLAMA_ENABLED=1, "
            "LLM_CLOUD_API_KEY, data/llm_tiers.json) or set a manual provider override in Studio."
        )
    fast_mode = bool(kwargs.get("fast_mode", cfg.fast_mode if not use_legacy else True))
    if use_legacy or classic:
        kwargs.setdefault("fast_mode", True)
        kwargs.setdefault("refine_second_pass", False)
        kwargs.setdefault("use_semantic_grouping", False)
        kwargs.setdefault("inject_wikilinks", False)
        kwargs.setdefault("use_tag_extraction", False)
        kwargs.setdefault("note_style", "bullets")
        kwargs.setdefault("coherence_mode", "compact")
        kwargs.setdefault("enrich_with_references", False)
        fast_mode = True
        kwargs["enrich_visuals"] = False
    else:
        kwargs.setdefault("refine_second_pass", cfg.refine_second_pass and not fast_mode)
        kwargs.setdefault("enrich_with_references", cfg.enrich_with_references and not fast_mode)
        kwargs.setdefault("use_tag_extraction", cfg.use_tag_extraction and not fast_mode)
        enrich_visuals = kwargs.pop("enrich_visuals", getattr(cfg, "enrich_visuals", not fast_mode))
        kwargs["enrich_visuals"] = bool(enrich_visuals) and not fast_mode
    kwargs.setdefault("max_chunks", cfg.max_llm_chunks)
    kwargs.setdefault("llm_pause_sec", cfg.llm_pause_sec)
    inject_wikilinks = bool(kwargs.pop("inject_wikilinks", False))
    def progress(msg: str) -> None:
        log.info(msg)
        if on_progress:
            on_progress(msg)
    if cancel_event and cancel_event():
        raise RuntimeError("Summarization cancelled.")
    if pre_cleaned and pre_cleaned.strip():
        cleaned = pre_cleaned.strip()
        progress("Using cleaned transcript from Tune step")
    elif use_legacy or classic:
        cleaned = backend_clean(raw, aggressive=aggressive)
        progress("Classic/legacy pipeline: single-pass cleanup (no RAG)")
    else:
        cleaned = parse_transcript(raw, aggressive=aggressive, preserve_snapshots=True)
    if not cleaned:
        raise ValueError("Transcript is empty after cleanup.")
    progress(f"Ready for LLM: {len(cleaned.split()):,} words ({len(cleaned):,} chars)")
    use_semantic = cfg.use_semantic_chunking and not fast_mode and not use_legacy and not classic
    kwargs.setdefault("use_semantic_grouping", use_semantic)
    kwargs.setdefault("restore_punctuation", False if (use_legacy or classic) else getattr(cfg, "restore_punctuation", False))
    kwargs.setdefault("asr_backend", getattr(cfg, "asr_backend", "recasepunc"))
    kwargs.setdefault("note_style", "bullets" if (use_legacy or classic) else getattr(cfg, "note_style", "bullets"))
    kwargs.setdefault("coherence_mode", "compact")
    kwargs.setdefault("semantic_threshold", getattr(cfg, "semantic_chunk_threshold", 0.45))
    kwargs.setdefault("semantic_threshold_mode", getattr(cfg, "semantic_threshold_mode", "fixed"))
    kwargs.setdefault("semantic_chunk_percentile", getattr(cfg, "semantic_chunk_percentile", 95.0))
    kwargs.setdefault("narrative_judge", False)
    llm_override, llm_tier = resolve_for_generate(cfg, opts)
    # Classic LM Studio: call local server directly — never OpenRouter/gateway
    if classic or (use_legacy and opts is not None):
        from transcript_studio.llm_client import generate as studio_generate

        studio_opts = opts or options_from_config(cfg)
        progress(f"Classic LM Studio · {studio_opts.provider} · {studio_opts.model} (no gateway)")

        def generate_fn(prompt: str) -> str | None:
            return studio_generate(prompt, opts=studio_opts)

    else:
        generate_fn = make_gateway_generate_fn(llm=llm_override, llm_tier=llm_tier, task="notes_chunk")
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
        generate_fn=generate_fn,
        llm=llm_override,
        llm_tier=llm_tier,
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
    _set_generate_meta(mode="legacy", rag={"grounding_status": "degraded", "grounding_reason": "no_textbook_chunks_retrieved"})
    return path, body, "legacy"

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
) -> tuple[Path, str, str]:
    if not transcript_path.is_file():
        raise FileNotFoundError(f"Transcript not found: {transcript_path}")
    raw = load_source_file(transcript_path)
    note_title = title or transcript_path.stem.replace("_", " ")
    snaps = resolve_session_snapshots_dir(transcript_path, session_dir)
    if not aggressive and "live_captions" in transcript_path.name.lower():
        aggressive = True
    cfg = load_config()
    use_legacy = cfg.legacy_notes_pipeline if kwargs.get("legacy_pipeline") is None else bool(
        kwargs.get("legacy_pipeline")
    )
    assemble_mode = bool(kwargs.pop("assemble_mode", True))
    classic = bool(kwargs.get("classic_lmstudio", False)) or use_legacy
    if classic:
        # Force classic path — never lecture-first assemble / RAG
        assemble_mode = False
        kwargs["classic_lmstudio"] = True
        kwargs.setdefault("enrich_visuals", False)
    llm_override, llm_tier = resolve_for_generate(cfg, opts)
    # Lecture-first is default; LLM rewrite only when assemble_mode explicitly False
    if classic or use_legacy:
        kwargs.pop("assemble_mode", None)
        kwargs.pop("classic_lmstudio", None)
        kwargs.pop("legacy_pipeline", None)
        path, body, mode = generate_notes_from_text(
            raw,
            title=note_title,
            aggressive=aggressive,
            output_dir=output_dir,
            opts=opts,
            snapshots_dir=snaps,
            on_progress=on_progress,
            legacy_pipeline=True,
            classic_lmstudio=True,
            **kwargs,
        )
        return path, body, mode
    if assemble_mode or not use_legacy:
        try:
            from backend.paths import TRANSCRIPTS_DIR
            from backend.corpus.retrieve import corpus_available
            from backend.transcripts.note_generation import generate_notes_unified, rag_notes_available

            can_assemble = assemble_mode
            can_rag = (not assemble_mode) and (not use_legacy) and rag_notes_available(llm=llm_override)
            if can_assemble or can_rag:
                try:
                    rel_file = transcript_path.relative_to(TRANSCRIPTS_DIR).as_posix()
                except ValueError:
                    rel_file = transcript_path.name
                if on_progress:
                    if can_assemble:
                        on_progress(
                            "Lecture-first: transcript primary + gated textbook cites (no LLM rewrite)…"
                        )
                    else:
                        on_progress("LLM+RAG rewrite mode…")
                ingest_corpus = bool(kwargs.pop("ingest_corpus", False))
                kwargs.pop("on_progress", None)
                kwargs.pop("assemble_mode", None)
                path, body, mode, rag = generate_notes_unified(
                    transcript_path=transcript_path,
                    transcript_file=rel_file,
                    title=note_title,
                    topic=note_title,
                    folder_path="",
                    llm=llm_override,
                    llm_tier=llm_tier,
                    ingest_corpus=ingest_corpus,
                    assemble_mode=can_assemble,
                    on_progress=on_progress,
                    **kwargs,
                )
                if snaps and snaps.is_dir():
                    if on_progress:
                        on_progress(f"Embedding {len(list(snaps.glob('*.png')))} slide images…")
                    body = inject_snapshot_images(body, snaps, note_path=path)
                    path.write_text(body, encoding="utf-8")
                _set_generate_meta(mode=mode, rag=rag if isinstance(rag, dict) else None)
                g = last_generate_meta()
                if on_progress:
                    gs = g.get("grounding_status")
                    gr = g.get("grounding_reason")
                    ground_hint = f", grounding={gs}" + (f" ({gr})" if gr else "")
                    on_progress(f"Notes saved ({mode}{ground_hint}): {path.name}")
                return path, body, mode
        except Exception as exc:
            log.warning("RAG notes failed, falling back to legacy: %s", exc)
            if on_progress:
                on_progress(f"RAG unavailable ({exc}); using legacy summarization…")
    path, body, mode = generate_notes_from_text(
        raw,
        title=note_title,
        aggressive=aggressive,
        output_dir=output_dir,
        opts=opts,
        snapshots_dir=snaps,
        on_progress=on_progress,
        **kwargs,
    )
    return path, body, mode

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
) -> tuple[Path, str, str]:
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
# Backward-compatible alias for any callers still importing _to_backend_llm.
_to_backend_llm = to_backend_llm
