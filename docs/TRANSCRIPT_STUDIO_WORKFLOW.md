# Transcript Notes Studio workflow

One desktop app owns **Capture → Parse → Generate**. The web app at `/lecture-notes` is for **reading, mermaid repair, quiz, and export** only.

## Architecture

```mermaid
flowchart LR
  subgraph studio [Transcript Notes Studio]
    Cap[1 Capture]
    Tune[2 Tune]
    Gen[3 Generate]
    Done[4 Done]
  end
  subgraph engine [Shared backend engine]
    LC[live_captions]
    CL[cleanup]
    NG[notes_generator]
    MD[note_document + mermaid]
  end
  subgraph disk [Repo data/]
    T[data/transcripts]
    N[data/notes]
  end
  subgraph web [Web Study Library]
    LN[/lecture-notes]
  end
  Cap --> LC --> T
  Tune --> CL
  Gen --> NG --> MD --> N
  LN --> N
```

## Primary entry point

```bat
transcript-notes-studio\run.bat
```

Workflow steps in the GUI:

1. **Capture** — Windows Live Captions (Win+Ctrl+L) or Whisper file/live
2. **Tune** — pick transcript, aggressive dedup, parse preview
3. **Generate** — LLM notes with mermaid rules, optional refine/tags/wikilinks
4. **Done** — open `data/notes/`, launch Study Library in browser

## Data paths

Empty `transcripts_dir` / `notes_dir` in `config.json` resolve to repo canonical dirs via `backend.paths`:

- `data/transcripts/`
- `data/notes/`

## CLI (headless / automation)

From `transcript-notes-studio/`:

```bat
python -m transcript_studio.cli capture
python -m transcript_studio.cli parse live_captions_20260623_204143.txt --aggressive
python -m transcript_studio.cli generate --latest --title "Lecture 1"
```

Legacy root scripts delegate to the same CLI:

- `scripts\run_live_captions_scraper.bat` → `cli capture`
- `scripts\run_transcript_to_notes.bat` → `cli generate`

## Web app scope

| In scope | Out of scope |
|----------|----------------|
| Open notes from `data/notes/` | Live caption capture |
| Mermaid fix / regen / save | Transcript tuning UI |
| Quiz, gap analysis, export | Batch note generation wizard |

## Manual QA checklist

1. Studio **Capture** → `.txt` appears in `data/transcripts/`
2. Studio **Generate** → `.md` in `data/notes/` with valid ` ```mermaid ` fences
3. `run.bat` + `http://localhost:5173/lecture-notes` → note in library tree, diagrams render
4. After Generate **Done**, dialog should report corpus chunk counts (transcript + note indexed)
5. Set `CORPUS_GROUNDED_NOTES=1` → Lecture Notes → **Generate grounded (RAG)** on same transcript
6. No need to run legacy two-step `.bat` scripts for normal use

## Handoff / export bundle

Portable copy of Studio + backend notes engine (no lecture `.txt`/`.md`):

```bat
scripts\export_transcript_studio_handoff.bat
rem or: cd transcript-notes-studio && python export_handoff.py
```

See [TRANSCRIPT_STUDIO_HANDOFF.md](./TRANSCRIPT_STUDIO_HANDOFF.md).
