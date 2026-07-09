"""Unattended batch note generation — sleep mode / pre-class queue."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from transcript_studio.config import AppConfig, load_config, save_config
from transcript_studio.gateway_llm import llm_generate_reachable, uses_gateway
from transcript_studio.llm_client import options_from_config
from transcript_studio.notes_generator import generate_notes_from_file, parse_transcript
from transcript_studio.paths import repo_root
from transcript_studio.quality_presets import apply_quality_preset
from transcript_studio.source_loader import load_source_file

log = logging.getLogger(__name__)

ProgressFn = Callable[[str], None] | None
CancelFn = Callable[[], bool] | None


@dataclass
class AutoRunItem:
    transcript: Path
    status: str = "pending"  # pending | done | skipped | error
    note_path: Path | None = None
    note_relative: str = ""
    mode: str = ""
    error: str = ""
    tuned: bool = False


@dataclass
class AutoRunResult:
    items: list[AutoRunItem] = field(default_factory=list)
    completed: int = 0
    skipped: int = 0
    failed: int = 0
    log_path: str = ""


def _notes_root(cfg: AppConfig) -> Path:
    return cfg.notes_path().resolve()


def _transcripts_root(cfg: AppConfig) -> Path:
    return cfg.transcripts_path().resolve()


def _logs_dir() -> Path:
    root = repo_root()
    logs = root / "data" / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    return logs


def note_exists_for_transcript(transcript: Path, cfg: AppConfig) -> bool:
    """True if any .md note filename contains the transcript stem."""
    notes_dir = _notes_root(cfg)
    if not notes_dir.is_dir():
        return False
    stem = transcript.stem.lower()
    for md in notes_dir.rglob("*.md"):
        if stem in md.stem.lower():
            return True
    return False


def note_relative_path(note_path: Path, cfg: AppConfig) -> str:
    notes_dir = _notes_root(cfg)
    try:
        return note_path.resolve().relative_to(notes_dir).as_posix()
    except ValueError:
        return note_path.name


def apply_overnight_preset(cfg: AppConfig | None = None) -> AppConfig:
    """Apply overnight quality settings and persist."""
    cfg = cfg or load_config()
    preset = apply_quality_preset("overnight")
    cfg.notes_quality = "overnight"
    cfg.fast_mode = bool(preset.get("fast_mode", True))
    cfg.max_llm_chunks = int(preset.get("max_llm_chunks", 20))
    cfg.legacy_notes_pipeline = bool(preset.get("legacy_notes_pipeline", False))
    cfg.use_semantic_chunking = bool(preset.get("use_semantic_chunking", False))
    cfg.refine_second_pass = bool(preset.get("refine_second_pass", False))
    cfg.llm_pause_sec = float(preset.get("llm_pause_sec", 3.0))
    cfg.parse_speed = int(preset.get("parse_speed", 65))
    cfg.enrich_visuals = bool(preset.get("enrich_visuals", False))
    save_config(cfg)
    return cfg


def tune_transcript(
    path: Path,
    *,
    aggressive: bool = False,
    use_legacy: bool = False,
    on_progress: ProgressFn = None,
) -> str:
    """Tune step — same parse/clean path as the Tune tab."""
    raw = load_source_file(path)
    if not raw.strip():
        raise ValueError(f"Transcript empty: {path.name}")
    if use_legacy:
        from backend.transcripts.cleanup import clean_transcript as backend_clean

        cleaned = backend_clean(raw, aggressive=aggressive)
        if on_progress:
            on_progress(f"Tuned (legacy clean): {path.name}")
    else:
        cleaned = parse_transcript(raw, aggressive=aggressive, preserve_snapshots=True)
        if on_progress:
            on_progress(f"Tuned (parse): {path.name}")
    if not cleaned.strip():
        raise ValueError(f"Transcript empty after tune: {path.name}")
    return cleaned.strip()


def list_auto_queue(
    cfg: AppConfig,
    *,
    limit: int = 20,
    skip_existing: bool = True,
) -> list[Path]:
    """Latest transcripts without matching notes (newest first)."""
    root = _transcripts_root(cfg)
    if not root.is_dir():
        return []
    paths = sorted(root.rglob("*.txt"), key=lambda p: p.stat().st_mtime, reverse=True)
    out: list[Path] = []
    for path in paths:
        if skip_existing and note_exists_for_transcript(path, cfg):
            continue
        out.append(path)
        if len(out) >= limit:
            break
    return out


def _write_run_log(result: AutoRunResult, *, preset: str) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    log_path = _logs_dir() / f"auto_run_{stamp}.json"
    payload: dict[str, Any] = {
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "preset": preset,
        "completed": result.completed,
        "skipped": result.skipped,
        "failed": result.failed,
        "items": [
            {
                "transcript": str(item.transcript),
                "status": item.status,
                "note_path": str(item.note_path) if item.note_path else "",
                "note_relative": item.note_relative,
                "mode": item.mode,
                "error": item.error,
                "tuned": item.tuned,
            }
            for item in result.items
        ],
    }
    log_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    result.log_path = str(log_path)
    return log_path


def run_auto_item(
    path: Path,
    cfg: AppConfig,
    *,
    use_rag: bool = True,
    run_tune: bool = True,
    aggressive: bool = False,
    on_progress: ProgressFn = None,
    cancel_event: CancelFn = None,
) -> AutoRunItem:
    """Tune → generate for one transcript."""
    item = AutoRunItem(transcript=path)
    use_legacy = not use_rag

    if cancel_event and cancel_event():
        item.status = "error"
        item.error = "cancelled"
        return item

    pre_cleaned: str | None = None
    if run_tune:
        pre_cleaned = tune_transcript(
            path,
            aggressive=aggressive,
            use_legacy=use_legacy,
            on_progress=on_progress,
        )
        item.tuned = True

    title = path.stem.replace("_", " ")
    enrich_visuals = getattr(cfg, "enrich_visuals", not cfg.fast_mode)
    note_path, _body, mode = generate_notes_from_file(
        path,
        title=title,
        aggressive=aggressive,
        opts=None if uses_gateway(cfg) else options_from_config(cfg),
        legacy_pipeline=use_legacy,
        pre_cleaned=pre_cleaned,
        fast_mode=cfg.fast_mode,
        enrich_visuals=enrich_visuals,
        max_chunks=cfg.max_llm_chunks,
        llm_pause_sec=cfg.llm_pause_sec,
        refine_second_pass=cfg.refine_second_pass and not cfg.fast_mode,
        on_progress=on_progress,
        cancel_event=cancel_event,
    )
    item.status = "done"
    item.note_path = note_path
    item.note_relative = note_relative_path(note_path, cfg)
    item.mode = mode
    if mode not in ("grounded", "hybrid_grounded"):
        try:
            from backend.corpus.handoff import ingest_lecture_handoff

            ingest_lecture_handoff(transcript_path=path, note_path=note_path)
        except Exception as exc:
            log.warning("Corpus handoff skipped for %s: %s", path.name, exc)
    return item


def run_auto_batch(
    cfg: AppConfig,
    paths: list[Path] | None = None,
    *,
    limit: int = 10,
    skip_existing: bool = True,
    use_rag: bool = True,
    run_tune: bool = True,
    overnight_preset: bool = False,
    on_progress: ProgressFn = None,
    cancel_event: CancelFn = None,
) -> AutoRunResult:
    """
    Generate notes for queued transcripts unattended.
    use_rag=False forces legacy pipeline (faster, no corpus).
    overnight_preset applies text-only fast settings before the run.
    """
    def step(msg: str) -> None:
        log.info(msg)
        if on_progress:
            on_progress(msg)

    preset_name = "overnight" if overnight_preset else getattr(cfg, "notes_quality", "balanced")
    if overnight_preset:
        cfg = apply_overnight_preset(cfg)

    result = AutoRunResult()
    if not llm_generate_reachable(cfg):
        raise RuntimeError("LLM not reachable — configure the repo AI handler or a manual provider override.")

    queue = paths or list_auto_queue(cfg, limit=limit, skip_existing=skip_existing)
    if not queue:
        step("Auto queue empty — no new transcripts to process.")
        _write_run_log(result, preset=preset_name)
        return result

    step(f"Auto run ({preset_name}) — {len(queue)} transcript(s) queued")

    for i, path in enumerate(queue, start=1):
        if cancel_event and cancel_event():
            step("Auto run cancelled.")
            break

        item = AutoRunItem(transcript=path)
        result.items.append(item)

        if skip_existing and note_exists_for_transcript(path, cfg):
            item.status = "skipped"
            result.skipped += 1
            step(f"[{i}/{len(queue)}] Skip (note exists): {path.name}")
            continue

        step(f"[{i}/{len(queue)}] Tune + generate: {path.name}")
        aggressive = "live_captions" in path.name.lower()

        try:
            done = run_auto_item(
                path,
                cfg,
                use_rag=use_rag,
                run_tune=run_tune,
                aggressive=aggressive,
                on_progress=on_progress,
                cancel_event=cancel_event,
            )
            item.status = done.status
            item.note_path = done.note_path
            item.note_relative = done.note_relative
            item.mode = done.mode
            item.tuned = done.tuned
            item.error = done.error
            if done.status == "done":
                result.completed += 1
                step(f"[{i}/{len(queue)}] Saved ({done.mode}): {done.note_relative or path.name}")
            else:
                result.failed += 1
        except Exception as exc:
            item.status = "error"
            item.error = str(exc)
            result.failed += 1
            step(f"[{i}/{len(queue)}] Failed: {path.name} — {exc}")

    step(
        f"Auto run finished — {result.completed} saved, "
        f"{result.skipped} skipped, {result.failed} failed"
    )
    log_path = _write_run_log(result, preset=preset_name)
    step(f"Run log: {log_path}")
    return result
