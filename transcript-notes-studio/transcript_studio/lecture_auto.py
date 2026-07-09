"""End-to-end Lecture Auto: capture → parse → RAG notes → save → quit Studio."""

from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from transcript_studio.auto_pipeline import apply_overnight_preset, tune_transcript
from transcript_studio.config import AppConfig, load_config, save_config
from transcript_studio.live_captions import LiveCaptionsScraper, check_captions_deps, ensure_windows
from transcript_studio.gateway_llm import llm_generate_reachable, uses_gateway
from transcript_studio.llm_client import options_from_config
from transcript_studio.notes_generator import generate_notes_from_file
from transcript_studio.paths import repo_root

log = logging.getLogger(__name__)

PhaseFn = Callable[[str, str], None] | None
ProgressFn = Callable[[str], None] | None
CancelFn = Callable[[], bool] | None


@dataclass
class LectureAutoResult:
    success: bool = False
    transcript_path: Path | None = None
    note_path: Path | None = None
    mode: str = ""
    error: str = ""
    log_path: str = ""
    phases: list[dict[str, object]] = field(default_factory=list)


def _logs_dir() -> Path:
    root = repo_root()
    logs = root / "data" / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    return logs


def _phase(
    phases: list[dict[str, object]],
    name: str,
    *,
    on_phase: PhaseFn = None,
    message: str = "",
) -> None:
    entry = {
        "phase": name,
        "message": message,
        "at": datetime.now(timezone.utc).isoformat(),
    }
    phases.append(entry)
    if on_phase:
        on_phase(name, message)
    if message:
        log.info("[lecture_auto] %s — %s", name, message)


def _write_run_log(result: LectureAutoResult) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    log_path = _logs_dir() / f"lecture_auto_{stamp}.json"
    payload = {
        "finished_at": datetime.now(timezone.utc).isoformat(),
        **asdict(result),
        "transcript_path": str(result.transcript_path) if result.transcript_path else "",
        "note_path": str(result.note_path) if result.note_path else "",
    }
    log_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    result.log_path = str(log_path)
    return log_path


def run_lecture_auto(
    cfg: AppConfig | None = None,
    *,
    on_phase: PhaseFn = None,
    on_progress: ProgressFn = None,
    cancel_event: threading.Event | None = None,
) -> LectureAutoResult:
    """
    Capture live captions, parse, generate textbook-grounded notes, save, optionally quit caller.
    """
    cfg = cfg or load_config()
    result = LectureAutoResult()
    phases = result.phases
    cancel = cancel_event or threading.Event()

    def cancelled() -> bool:
        return cancel.is_set()

    def progress(msg: str) -> None:
        log.info(msg)
        if on_progress:
            on_progress(msg)

    try:
        if not llm_generate_reachable(cfg):
            raise RuntimeError(
                "LLM not reachable. Configure the repo AI handler (root .env) or a manual provider override."
            )
        ok, dep_msg = check_captions_deps()
        if not ok:
            raise RuntimeError(dep_msg)
        ensure_windows()

        if cfg.lecture_auto_fast_mode:
            cfg = apply_overnight_preset(cfg)

        _phase(phases, "capturing", on_phase=on_phase, message="Starting Live Captions capture")
        scraper = LiveCaptionsScraper(
            poll_interval=cfg.captions_poll_interval,
            method=cfg.captions_method,  # type: ignore[arg-type]
        )
        max_sec = cfg.lecture_auto_max_sec if cfg.lecture_auto_max_sec > 0 else None
        idle_sec = cfg.lecture_auto_idle_sec if cfg.lecture_auto_idle_sec > 0 else None
        capture_started = time.monotonic()
        scraper.run(
            max_seconds=max_sec,
            idle_seconds=idle_sec,
            stop_event=cancel,
        )
        if cancelled():
            raise RuntimeError("Lecture Auto cancelled during capture.")

        transcript_path = scraper.save(output_dir=cfg.transcripts_path())
        result.transcript_path = transcript_path
        cfg.last_transcript = str(transcript_path)
        save_config(cfg)
        elapsed = int(time.monotonic() - capture_started)
        _phase(
            phases,
            "captured",
            on_phase=on_phase,
            message=f"Saved {transcript_path.name} ({len(scraper.segments)} segments, {elapsed}s)",
        )

        _phase(phases, "parsing", on_phase=on_phase, message="Cleaning transcript")
        aggressive = "live_captions" in transcript_path.name.lower()
        pre_cleaned = tune_transcript(
            transcript_path,
            aggressive=aggressive,
            use_legacy=not cfg.lecture_auto_use_rag,
            on_progress=progress,
        )
        word_count = len(pre_cleaned.split())
        _phase(phases, "parsed", on_phase=on_phase, message=f"{word_count:,} words ready for notes")

        if cancelled():
            raise RuntimeError("Lecture Auto cancelled before notes generation.")

        _phase(phases, "generating", on_phase=on_phase, message="Generating textbook-grounded notes")
        title = transcript_path.stem.replace("_", " ")
        note_path, _body, mode = generate_notes_from_file(
            transcript_path,
            title=title,
            aggressive=aggressive,
            opts=None if uses_gateway(cfg) else options_from_config(cfg),
            legacy_pipeline=not cfg.lecture_auto_use_rag,
            pre_cleaned=pre_cleaned,
            ingest_corpus=cfg.lecture_auto_handoff_corpus,
            fast_mode=cfg.fast_mode,
            enrich_visuals=cfg.enrich_visuals,
            max_chunks=cfg.max_llm_chunks,
            llm_pause_sec=cfg.llm_pause_sec,
            refine_second_pass=cfg.refine_second_pass and not cfg.fast_mode,
            on_progress=progress,
            cancel_event=cancelled,
        )
        result.note_path = note_path
        result.mode = mode
        _phase(phases, "saved", on_phase=on_phase, message=f"Notes saved: {note_path.name} ({mode})")

        result.success = True
        _phase(phases, "done", on_phase=on_phase, message="Lecture Auto complete")
        return result
    except Exception as exc:
        result.error = f"{type(exc).__name__}: {exc}"
        _phase(phases, "error", on_phase=on_phase, message=result.error)
        log.exception("Lecture Auto failed")
        return result
    finally:
        _write_run_log(result)
