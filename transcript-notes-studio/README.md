# Transcript Notes Studio

Standalone desktop app for the full lecture pipeline: **Capture → Tune → Generate**.

Uses the shared `backend/transcripts/` engine when run inside the Cognitive-Aware Learning Tutor monorepo. Notes land in repo `data/transcripts/` and `data/notes/` by default.

The web **Study Library** (`/lecture-notes`) is for reading, mermaid repair, quiz, and export — not capture or generation.

## Generate (current stack)

Studio uses the **same** repo AI handler as the web app:

1. `llm_use_gateway=true` + provider `auto` / `openrouter` / cloud → `backend.core.llm_gateway`
2. RAG path → `generate_notes_unified` → hybrid notes with **concept_extract** before retrieve
3. Notes are **topic briefs** grounded in textbook REFERENCE (not Definition/Importance dumps or classroom UI)
4. After save, Studio logs `grounding=grounded|degraded` and progress lines show **provider · model · latency**

### Transcripts to generate (checkboxes)

On the **Generate** step:

- List of `data/transcripts/*.txt` with checkboxes + `has note` / `no note`
- **Generate notes** runs **only checked** files — **one note per file**
- After parse, the parsed file is auto-checked
- **Ingest selected (RAG index only)** indexes for quiz/coach — it does **not** generate notes

Legacy text-only path only when corpus/LLM unavailable or **Legacy pipeline** is checked.

Prefer **Lecture-first (recommended)** on Generate — transcript primary + gated textbook cites (no LLM rewrite). Uncheck only for experimental LLM rewrite.

**Classic LM Studio notes (separate GUI):** `run_legacy_notes.bat` — Gemma via LM Studio only, **no RAG / no mermaid / no code enrich**. Manual generate from a transcript, or **Classic Auto** (Live Captions → parse → classic notes → LLM names the `.md` file). Main `run.bat` Studio still handles Capture/Tune if you prefer manual steps.

**RAG:** **Ensure RAG (skip if OK)** does nothing when textbooks already work. **Force rebuild** wipes only when you ask. Textbooks only — no transcript ingest.

See [docs/LLM_GATEWAY.md](../docs/LLM_GATEWAY.md) and [docs/TRANSCRIPT_STUDIO_WORKFLOW.md](../docs/TRANSCRIPT_STUDIO_WORKFLOW.md).

## Quick start (Windows)

```bat
cd transcript-notes-studio
run.bat
```

1. **Capture** — Live Captions (Win+Ctrl+L) or Whisper
2. **Tune** — select transcript, parse preview, aggressive dedup
3. **Generate** — LLM notes (start LM Studio or Ollama first)
4. **Done** — open notes folder or Study Library in browser (`?file=` deep link)

## Overnight auto batch

On the **Generate** step, **Auto run** queues transcripts without notes:

1. **Tune** (parse/clean) — same as the Tune tab  
2. **Generate** — RAG when corpus is ready; text-only when **Overnight** preset (diagrams OFF)  
3. **Corpus handoff** — indexes transcript + note chunks for the web app  
4. Run log — `data/logs/auto_run_*.json`

Use **Start overnight** for the full sleep preset (fast mode, 3s pauses, max 5 by default).

## Web Study Library

| Studio | Web (`/lecture-notes`) |
|--------|------------------------|
| Capture, Tune, local generate | RAG notes, primer, quiz, folder revision pack |
| Auto/overnight batch | Export PDF/Word (mermaid→PNG when `mmdc` available) |
| `data/notes/` output | SRS + dashboard due count |

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
| Include diagrams | Final mermaid/code enrich pass (OFF for overnight) |
| Overnight preset | Tune + text-only + RAG + thermal pauses |

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
