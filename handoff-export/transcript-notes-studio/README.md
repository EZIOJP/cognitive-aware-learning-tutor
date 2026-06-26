# Transcript Notes Studio

Standalone desktop app for the full lecture pipeline: **Capture → Tune → Generate**.

Uses the shared `backend/transcripts/` engine when run inside the Cognitive-Aware Learning Tutor monorepo. Notes land in repo `data/transcripts/` and `data/notes/` by default.

The web **Study Library** (`/lecture-notes`) is for reading, mermaid repair, quiz, and export — not capture or generation.

## Quick start (Windows)

```bat
cd transcript-notes-studio
run.bat
```

1. **Capture** — Live Captions (Win+Ctrl+L) or Whisper
2. **Tune** — select transcript, parse preview, aggressive dedup
3. **Generate** — LLM notes (start LM Studio or Ollama first)
4. **Done** — open notes folder or Study Library in browser

## Workflow

See [docs/TRANSCRIPT_STUDIO_WORKFLOW.md](../docs/TRANSCRIPT_STUDIO_WORKFLOW.md) for architecture and QA checklist.  
Full agent handoff: [docs/TRANSCRIPT_STUDIO_HANDOFF.md](../docs/TRANSCRIPT_STUDIO_HANDOFF.md).

## CLI

```bat
python -m transcript_studio.cli capture
python -m transcript_studio.cli parse live_captions.txt --aggressive
python -m transcript_studio.cli generate --latest --title "EDA recap"
python -m transcript_studio.cli generate -i lecture.txt --context ./prereqs
```

Legacy flags still work: `--latest`, `-i`, `--parse-only`.

## Configuration

`config.json` — leave `transcripts_dir` and `notes_dir` **empty** to use repo `data/transcripts` and `data/notes`.

| Toggle | Effect |
|--------|--------|
| Aggressive dedup | Collapse Windows caption prefix growth |
| 2nd-pass refine | Stitch chunk summaries into one document |
| Semantic chunking | Group sentences before LLM passes |
| Tag extraction | Topic tags on sections |
| Inject wikilinks | `[[...]]` links between notes in output folder |
| Fast mode | Chunk pass only (skip refine/enrich/tags) |

## Project layout

```
transcript-notes-studio/
  run.bat / run_gui.py
  config.json
  transcript_studio/
    paths.py           # resolves data/ via backend.paths
    cleanup.py         # re-exports backend.transcripts.cleanup
    live_captions.py   # backend scraper + GUI stop_event
    source_loader.py   # backend.transcripts.sources
    notes_generator.py # thin wrapper → backend pipeline
    snapshots.py       # slide capture during Whisper sessions
    gui.py             # workflow stepper UI
    cli.py             # capture | parse | generate
```

## Tests

```bat
cd transcript-notes-studio
python -m pytest tests/ -q
python verify_pipeline_imports.py
```

## Relationship to main app

| Shared engine (`backend/transcripts/`) | Studio |
|----------------------------------------|--------|
| `cleanup`, `notes_generator`, `mermaid/` | Imported, not duplicated |
| FastAPI `/api/transcripts` | Not used |
| Study Library web UI | Read/repair/quiz only |

Legacy root scripts (`scripts/run_live_captions_scraper.bat`, `scripts/run_transcript_to_notes.bat`) delegate to `transcript_studio.cli` for headless automation.

## Handoff / export

Portable code bundle (no lecture data) for moving or refactoring:

```bat
cd transcript-notes-studio
python export_handoff.py
rem or: scripts\export_transcript_studio_handoff.bat
rem or: python -m transcript_studio.cli export-handoff
```

See [handoff/README.md](handoff/README.md) and [docs/TRANSCRIPT_STUDIO_HANDOFF.md](../docs/TRANSCRIPT_STUDIO_HANDOFF.md).
