"""Classic auto: Live Captions capture → parse → LM Studio notes → LLM filename."""

from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from transcript_studio.auto_pipeline import tune_transcript
from transcript_studio.config import AppConfig, load_config, save_config
from transcript_studio.live_captions import LiveCaptionsScraper, check_captions_deps, ensure_windows
from transcript_studio.llm_client import (
    DEFAULT_LMSTUDIO_MODEL,
    LlmOptions,
    generate,
    llm_reachable,
    lmstudio_loaded_model,
)
from transcript_studio.note_title import suggest_note_title
from transcript_studio.notes_generator import generate_notes_from_file
from transcript_studio.paths import notes_dir, repo_root

log = logging.getLogger(__name__)

PhaseFn = Callable[[str, str], None] | None
ProgressFn = Callable[[str], None] | None


@dataclass
class ClassicAutoResult:
    success: bool = False
    transcript_path: Path | None = None
    note_path: Path | None = None
    title: str = ""
    mode: str = "classic"
    error: str = ""
    log_path: str = ""
    phases: list[dict[str, object]] = field(default_factory=list)


def _logs_dir() -> Path:
    logs = repo_root() / "data" / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    return logs


def _phase(
    phases: list[dict[str, object]],
    name: str,
    *,
    on_phase: PhaseFn = None,
    message: str = "",
) -> None:
    entry = {"phase": name, "message": message, "at": datetime.now(timezone.utc).isoformat()}
    phases.append(entry)
    if on_phase:
        on_phase(name, message)
    if message:
        log.info("[classic_auto] %s — %s", name, message)


def run_classic_auto(
    cfg: AppConfig | None = None,
    *,
    opts: LlmOptions | None = None,
    on_phase: PhaseFn = None,
    on_progress: ProgressFn = None,
    cancel_event: threading.Event | None = None,
    idle_sec: float | None = None,
    max_sec: float | None = None,
) -> ClassicAutoResult:
    """
    Full classic pipeline:
    Live Captions → parse/clean → LM Studio Gemma notes (no RAG/mermaid) → LLM names the file.
    """
    cfg = cfg or load_config()
    result = ClassicAutoResult()
    phases = result.phases
    cancel = cancel_event or threading.Event()

    def cancelled() -> bool:
        return cancel.is_set()

    def progress(msg: str) -> None:
        log.info(msg)
        if on_progress:
            on_progress(msg)

    try:
        cfg.llm_use_gateway = False
        cfg.llm_provider = "lmstudio"
        if opts is not None:
            cfg.llm_base_url = opts.base_url
            cfg.llm_model = opts.model
        if not llm_reachable(cfg):
            raise RuntimeError(
                "LM Studio offline. Start local server and load Gemma before Classic Auto."
            )
        ok, dep_msg = check_captions_deps()
        if not ok:
            raise RuntimeError(dep_msg)
        ensure_windows()

        base_url = (opts.base_url if opts else None) or cfg.llm_base_url or "http://127.0.0.1:1234"
        api_key = (opts.api_key if opts else None) or cfg.llm_api_key or "lm-studio"
        requested = (opts.model if opts else None) or cfg.llm_model or ""
        cloudish = any(
            x in requested.lower() for x in ("gemini", "gpt", "claude", "openrouter", "gemma-3")
        )
        model = requested
        if not model or cloudish:
            model = lmstudio_loaded_model(base_url, api_key=api_key) or DEFAULT_LMSTUDIO_MODEL
        elif opts is None:
            model = lmstudio_loaded_model(base_url, api_key=api_key) or model
        studio_opts = LlmOptions(
            provider="lmstudio",
            base_url=base_url,
            model=model,
            max_tokens=int(
                (opts.max_tokens if opts else None) or cfg.llm_max_tokens or 8192
            ),
            temperature=float(
                (opts.temperature if opts else None) or cfg.llm_temperature or 0.3
            ),
            api_key=api_key,
        )
        cfg.llm_model = studio_opts.model
        cfg.llm_base_url = studio_opts.base_url

        _phase(phases, "capturing", on_phase=on_phase, message="Starting Live Captions capture")
        scraper = LiveCaptionsScraper(
            poll_interval=cfg.captions_poll_interval,
            method=cfg.captions_method,  # type: ignore[arg-type]
        )
        max_s = max_sec if max_sec is not None else (cfg.lecture_auto_max_sec or None)
        idle_s = idle_sec if idle_sec is not None else (cfg.lecture_auto_idle_sec or None)
        if max_s is not None and max_s <= 0:
            max_s = None
        if idle_s is not None and idle_s <= 0:
            idle_s = None
        started = time.monotonic()
        scraper.run(max_seconds=max_s, idle_seconds=idle_s, stop_event=cancel)
        if cancelled():
            raise RuntimeError("Classic Auto cancelled during capture.")

        transcript_path = scraper.save(output_dir=cfg.transcripts_path())
        result.transcript_path = transcript_path
        cfg.last_transcript = str(transcript_path)
        save_config(cfg)
        elapsed = int(time.monotonic() - started)
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
            use_legacy=True,
            on_progress=progress,
        )
        word_count = len(pre_cleaned.split())
        _phase(phases, "parsed", on_phase=on_phase, message=f"{word_count:,} words ready")

        if cancelled():
            raise RuntimeError("Classic Auto cancelled before title/notes.")

        _phase(phases, "naming", on_phase=on_phase, message="Asking LM Studio for note title…")

        def gen_fn(prompt: str) -> str | None:
            return generate(prompt, opts=studio_opts)

        display_title, slug = suggest_note_title(
            pre_cleaned,
            generate_fn=gen_fn,
            fallback=transcript_path.stem,
        )
        result.title = display_title
        _phase(phases, "named", on_phase=on_phase, message=f"Title: {display_title} → {slug}")

        if cancelled():
            raise RuntimeError("Classic Auto cancelled before notes generation.")

        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        out_path = notes_dir() / f"{slug}_{stamp}.md"
        _phase(
            phases,
            "generating",
            on_phase=on_phase,
            message=f"Classic LM Studio notes → {out_path.name}",
        )
        note_path, _body, mode = generate_notes_from_file(
            transcript_path,
            title=display_title,
            aggressive=aggressive,
            opts=studio_opts,
            legacy_pipeline=True,
            classic_lmstudio=True,
            assemble_mode=False,
            enrich_visuals=False,
            fast_mode=True,
            refine_second_pass=False,
            use_semantic_grouping=False,
            use_tag_extraction=False,
            inject_wikilinks=False,
            pre_cleaned=pre_cleaned,
            note_output_path=out_path,
            on_progress=progress,
            cancel_event=cancelled,
        )
        result.note_path = note_path
        result.mode = mode
        _phase(phases, "saved", on_phase=on_phase, message=f"Notes saved: {note_path.name}")
        result.success = True
        _phase(phases, "done", on_phase=on_phase, message="Classic Auto complete")
        return result
    except Exception as exc:
        result.error = f"{type(exc).__name__}: {exc}"
        _phase(phases, "error", on_phase=on_phase, message=result.error)
        log.exception("Classic Auto failed")
        return result
    finally:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        log_path = _logs_dir() / f"classic_auto_{stamp}.json"
        payload = {
            "finished_at": datetime.now(timezone.utc).isoformat(),
            **asdict(result),
            "transcript_path": str(result.transcript_path) if result.transcript_path else "",
            "note_path": str(result.note_path) if result.note_path else "",
        }
        log_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        result.log_path = str(log_path)
