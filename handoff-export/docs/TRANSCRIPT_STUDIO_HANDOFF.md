# Transcript Notes Studio — Agent Handoff

**Project:** Cognitive-Aware Learning Tutor  
**Area:** Desktop capture → parse → LLM notes → web Study Library  
**Date:** 2026-06-25  
**Status:** Working end-to-end; quality tuning in progress  

---

## 1. What works today

| Step | Entry | Output |
|------|-------|--------|
| Capture | Studio **1 Capture** or `cli capture` | `data/transcripts/live_captions_*.txt` |
| Tune | **Parse & preview**, **Save cleaned…**, cleanup audit | In-memory cleaned text + optional `*_cleaned_*.txt` |
| Generate | **Generate notes** (Studio or legacy bat) | `data/notes/*_YYYYMMDD_HHMMSS.md` |
| Study | Web `/lecture-notes` | Read, mermaid repair, quiz (no generation) |

**Tests:** `transcript-notes-studio/tests/` (99+), plus `tests/test_notes_generator.py`, `tests/test_transcript_to_notes_cli.py`.

**Portable bundle:** `python transcript-notes-studio/export_handoff.py` → `handoff-export/` at repo root.

---

## 2. Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│ Transcript Notes Studio (Tkinter)                                  │
│  gui.py — workflow rail: Capture | Tune | Generate | Done       │
│  cli.py — capture | parse | generate | export-handoff           │
└───────────────┬─────────────────────────────────────────────────┘
                │
    ┌───────────┼───────────┐
    ▼           ▼           ▼
chunked_parse  parse_audit  notes_generator.py (thin wrapper)
parse_throttle              │
    │                       ▼
    │           backend/transcripts/notes_generator.py
    │             ├─ cleanup / chunk_by_words / semantic_grouper
    │             ├─ summarize_chunk (CHUNK_PROMPT + mermaid rules)
    │             └─ refine_second_pass (optional)
    ▼
backend/transcripts/cleanup.py
```

**Data:** `backend/paths.py` → `data/transcripts/`, `data/notes/`, `data/logs/transcript_studio.log`.

**LLM:** `backend/core/ollama_client.py` — LM Studio default `http://127.0.0.1:1234`, model `google/gemma-4-e4b`.

---

## 3. Two pipelines (important)

### Studio (default)

1. **Parse:** `transcript_studio/chunked_parse.py` — multi-pass, throttle slider (`parse_throttle.py`)
2. **Audit:** `parse_audit.audit_parse` — raw vs cleaned retention
3. **Generate:** Re-parses unless Tune preview exists (`pre_cleaned`); merges many chunks → max 12 LLM calls
4. **Post:** optional wikilinks, slide gallery, notes audit (`audit_notes`)

### Legacy (`run_transcript_to_notes.bat` or GUI **Legacy pipeline**)

1. **Parse:** `backend.transcripts.cleanup.clean_transcript` — single pass
2. **Generate:** `fast_mode` default, no semantic grouping, no wikilinks
3. Same backend `generate_notes_from_file`

**GUI toggles** (`config.json`): `legacy_notes_pipeline`, `parse_speed`, `max_llm_chunks`, `thorough_parse`, `refine_second_pass`, `inject_wikilinks`.

---

## 4. Known issues / improvement backlog

| Issue | Cause | Suggested fix |
|-------|-------|----------------|
| Notes too thin vs lecture | 50 chunks merged → 12 LLM passes; heavy summarization | Raise `max_llm_chunks` (16–24); smaller `target_words`; more passes |
| Pre-class Q&A in notes | First ~75 lines of transcript are chat before lecture | Trim marker or “skip until keyword” pre-pass |
| Broken mermaid/code fences | LLM output + aggressive mermaid rules in prompt | Relax CHUNK_PROMPT; post-process fences; Study Library repair |
| Wikilinks invisible | Only when other `.md` in folder share `##` headings | Off by default; document or remove |
| `KeyError` on generate | Mermaid rules `{...}` in `.format()` | Fixed via `_embed_rules()` — keep when editing prompts |
| Double parse | Generate ignored Tune preview | Fixed: `pre_cleaned` from `_cleaned_text` |
| Low notes retention | Expected for summaries | **Notes audit** tab after generate; compare with cleanup audit |

---

## 5. File map

### Studio (`transcript-notes-studio/transcript_studio/`)

| File | Role |
|------|------|
| `gui.py` | Workflow UI, parse/generate threads, audits, save cleaned |
| `cli.py` | Headless capture/parse/generate |
| `config.py` / `config.json` | Paths, LLM, pipeline toggles |
| `notes_generator.py` | Wrapper: parse → `backend_generate`, legacy mode |
| `chunked_parse.py` | Multi-pass parse with pauses |
| `parse_throttle.py` | Speed slider → chunk size / pause |
| `parse_audit.py` | Cleanup + **notes retention** audit |
| `ui_text.py` | Large preview without UI freeze |
| `log_setup.py` | `data/logs/transcript_studio.log` |
| `source_loader.py` | Thin wrapper → `backend.transcripts.sources` |
| `cleanup.py` | Thin wrapper → `backend.transcripts.cleanup` |
| `live_captions.py` | Windows caption scraper |
| `llm_client.py` | Studio LLM calls |
| `wikilink_injector.py` | Optional `[[links]]` between notes |
| `export_handoff.py` | Export/import portable bundle |

### Backend engine (`backend/transcripts/`)

| File | Role |
|------|------|
| `notes_generator.py` | **Core** chunk summarize + refine |
| `cleanup.py` | Dedup, filler strip, `chunk_by_words` |
| `sources.py` | Context folder, PDF/md reference load |
| `semantic_grouper.py` | Embedding-based chunk groups (capped for large files) |
| `mermaid/prompts.py` | `MERMAID_GENERATION_RULES` in prompts |
| `note_document.py` | Finalize markdown |
| `snapshots.py` | Slide PNG gallery in notes |

### Web (read-only for this pipeline)

| File | Role |
|------|------|
| `src/pages/study/LectureNotesPage.tsx` | Study Library shell |
| `src/components/study/StudyLibraryViewer.tsx` | Note viewer |
| `backend/transcripts/router.py` | `/api/transcripts/*` |

### Scripts

| File | Role |
|------|------|
| `scripts/run_transcript_to_notes.bat` | Legacy CLI wrapper |
| `scripts/run_live_captions_scraper.bat` | Legacy capture |
| `transcript-notes-studio/run.bat` | Studio GUI |

---

## 6. Config reference (`transcript-notes-studio/config.json`)

```json
{
  "transcripts_dir": "",
  "notes_dir": "",
  "aggressive_dedup_default": true,
  "thorough_parse": true,
  "parse_speed": 65,
  "legacy_notes_pipeline": false,
  "max_llm_chunks": 12,
  "refine_second_pass": true,
  "fast_mode": false,
  "use_semantic_chunking": true,
  "inject_wikilinks": false
}
```

Empty `transcripts_dir` / `notes_dir` → repo `data/transcripts` and `data/notes`.

---

## 7. Commands

```bat
rem Studio GUI
transcript-notes-studio\run.bat

rem Export portable handoff (code + docs, no lecture data)
cd transcript-notes-studio
python export_handoff.py -o ..\handoff-export

rem Import back
python export_handoff.py --import ..\handoff-export

rem Legacy headless
scripts\run_transcript_to_notes.bat --latest --aggressive-dedup

rem Studio CLI
python -m transcript_studio.cli parse live_captions_20260623_204143.txt --aggressive --audit
python -m transcript_studio.cli generate --latest --fast --no-refine
```

---

## 8. QA checklist

1. Capture → new `.txt` in `data/transcripts/`
2. Tune → Parse → char/word counts; Cleanup audit >70% retention for live captions
3. Save cleaned → `.txt` on disk with expected size
4. Generate → `.md` in `data/notes/`; Notes audit tab shows retention %
5. `/lecture-notes` → note appears; mermaid renders or is fixable
6. Legacy pipeline → completes without wikilinks/refine

---

## 9. Related docs

- [TRANSCRIPT_STUDIO_WORKFLOW.md](./TRANSCRIPT_STUDIO_WORKFLOW.md) — short workflow
- [MERMAID_RENDER_AND_REGEN_HANDOFF.md](./MERMAID_RENDER_AND_REGEN_HANDOFF.md) — Study Library repair
- `transcript-notes-studio/handoff/README.md` — portable bundle readme
- `transcript-notes-studio/handoff/FLOW_MANIFEST.json` — machine-readable flow

---

## 10. Suggested next engineering tasks

1. **Chunk strategy** — configurable `target_words`, avoid blind merge to 12
2. **Pre-lecture trim** — detect “class start” or manual line range
3. **Single outline pass** — LLM table of contents before chunk summarize
4. **Export flow presets** — JSON profile: `{ "name": "legacy-fast", "toggles": {...} }`
5. **Always show wikilink help** — or remove feature until multi-note library exists
