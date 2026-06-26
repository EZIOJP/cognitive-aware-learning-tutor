"""Export notes run artifacts for review or handoff to another agent."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from transcript_studio.config import AppConfig, load_config
from transcript_studio.log_setup import log_file_path, tail_log


def export_run_insights(
    out_dir: Path,
    *,
    note_path: Path | None = None,
    transcript_path: Path | None = None,
    cleaned_text: str = "",
    cleanup_audit: str = "",
    notes_audit: str = "",
    cfg: AppConfig | None = None,
) -> Path:
    """Write a folder with note, audits, config, and log tail."""
    cfg = cfg or load_config()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    root = out_dir / f"insights_{stamp}"
    root.mkdir(parents=True, exist_ok=True)

    if note_path and note_path.is_file():
        shutil.copy2(note_path, root / note_path.name)
    if transcript_path and transcript_path.is_file():
        shutil.copy2(transcript_path, root / f"source_{transcript_path.name}")
    if cleaned_text.strip():
        (root / "cleaned_transcript.txt").write_text(cleaned_text, encoding="utf-8")
    if cleanup_audit.strip():
        (root / "cleanup_audit.txt").write_text(cleanup_audit, encoding="utf-8")
    if notes_audit.strip():
        (root / "notes_audit.txt").write_text(notes_audit, encoding="utf-8")

    (root / "config_snapshot.json").write_text(
        json.dumps(
            {
                "llm_provider": cfg.llm_provider,
                "llm_base_url": cfg.llm_base_url,
                "llm_model": cfg.llm_model,
                "llm_max_tokens": cfg.llm_max_tokens,
                "fast_mode": cfg.fast_mode,
                "max_llm_chunks": cfg.max_llm_chunks,
                "legacy_notes_pipeline": cfg.legacy_notes_pipeline,
                "notes_quality": getattr(cfg, "notes_quality", "balanced"),
                "llm_pause_sec": getattr(cfg, "llm_pause_sec", 0.0),
                "parse_speed": cfg.parse_speed,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    log_path = log_file_path()
    if log_path.is_file():
        (root / "studio_log_tail.txt").write_text(tail_log(400), encoding="utf-8")

    readme = """# Run insights export

Contents:
- `*.md` — generated notes (if saved)
- `source_*.txt` — original transcript (if available)
- `cleaned_transcript.txt` — parsed text used for generate
- `cleanup_audit.txt` — raw vs cleaned retention
- `notes_audit.txt` — cleaned vs notes retention
- `config_snapshot.json` — Studio toggles for this run
- `studio_log_tail.txt` — last log lines

For full code handoff: `python export_handoff.py` from transcript-notes-studio/.
"""
    (root / "README.md").write_text(readme, encoding="utf-8")
    return root
