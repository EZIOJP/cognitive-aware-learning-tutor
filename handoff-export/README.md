# Transcript Notes Studio — Portable handoff bundle

This folder documents the **Capture → Tune → Generate** pipeline so you can move, refactor, or hand work to another agent/repo.

## What to export

From the monorepo root:

```bat
cd transcript-notes-studio
python export_handoff.py
```

Or with a custom destination:

```bat
python export_handoff.py -o D:\exports\transcript-studio-handoff
```

This creates a self-contained folder:

```
handoff-export/
  README.md                    ← this file (copied)
  FLOW_MANIFEST.json           ← machine-readable flow + file list
  TRANSCRIPT_STUDIO_HANDOFF.md ← full agent handoff (from docs/)
  transcript-notes-studio/     ← GUI, CLI, parse audit, throttle
  backend/                     ← notes engine (subset)
  tests/                       ← studio + backend tests
  scripts/                     ← legacy .bat launchers
  data/
    transcripts/.gitkeep
    notes/.gitkeep
```

User lecture files (`*.txt`, `*.md`) are **not** copied — only code and docs.

## Import back into the monorepo

```bat
python export_handoff.py --import D:\exports\transcript-studio-handoff
```

Dry-run first:

```bat
python export_handoff.py --import D:\exports\transcript-studio-handoff --dry-run
```

Import overwrites matching paths under the repo root (never deletes extra files).

## Run exported copy inside monorepo

The export is meant to sit **inside** Cognitive-Aware Learning Tutor (needs `backend/` on `PYTHONPATH`):

```bat
cd handoff-export\transcript-notes-studio
run.bat
```

Standalone extraction (no monorepo) requires keeping `backend/` sibling and setting:

```bat
set PYTHONPATH=<handoff-export>
```

## Pipeline modes

| Mode | Where | Parse | Generate | When to use |
|------|-------|-------|----------|-------------|
| **Studio** | GUI step 2–3 | `chunked_parse` + audit | Chunked LLM + optional refine | Default; large live captions |
| **Legacy** | GUI checkbox or `run_transcript_to_notes.bat` | `backend.cleanup` single pass | Fast chunks, no wikilinks | Closer to original bat script |

Always **Parse on Tune** before Generate so retention audit and `Save cleaned…` use the same text.

## Key files to improve logic

| Area | File |
|------|------|
| GUI workflow | `transcript_studio/gui.py` |
| Studio → backend bridge | `transcript_studio/notes_generator.py` |
| Chunk LLM prompts | `backend/transcripts/notes_generator.py` |
| Parse / dedup | `backend/transcripts/cleanup.py`, `transcript_studio/chunked_parse.py` |
| Retention audit | `transcript_studio/parse_audit.py` |
| Parse speed slider | `transcript_studio/parse_throttle.py` |
| Mermaid in prompts | `backend/transcripts/mermaid/prompts.py` |
| Web read/repair | `src/pages/study/LectureNotesPage.tsx` |

## Tests

```bat
cd transcript-notes-studio
python -m pytest tests/ -q
cd ..
python -m pytest tests/test_notes_generator.py tests/test_transcript_to_notes_cli.py -q
```

## Full handoff doc

See `TRANSCRIPT_STUDIO_HANDOFF.md` in this bundle (or `docs/TRANSCRIPT_STUDIO_HANDOFF.md` in the repo) for architecture, known issues, and improvement backlog.
