# Transcript Notes Studio — Architecture & Goals

## Product goals

1. **One local desktop app** for lecture day: capture messy live captions → clean transcript → grounded study notes on disk.
2. **RAG-grounded notes** use **textbooks only** during generation (not prior lectures), so NumPy lecture notes cite MML / stats books, not random transcript chunks.
3. **Handoff to web app**: saved `.md` in `data/notes/` → Study Library → quiz / SRS / coach (separate FastAPI app).
4. **Unattended mode**: Lecture Auto — capture until silence, parse, generate, save, quit.
5. **Local-first**: LM Studio / Ollama on `127.0.0.1`; no cloud required for core loop.

**Not goals:** replacing the web dashboard, cloud sync, or multi-user auth inside Studio.

---

## System map

```
┌─────────────────────────────────────────────────────────────────┐
│  Transcript Notes Studio (Tkinter)                               │
│  gui.py — workflow steps 1–4                                     │
├──────────────┬──────────────┬──────────────┬────────────────────┤
│ 1 Capture    │ 2 Tune       │ 3 Generate   │ 4 Done             │
│ live_captions│ chunked_parse│ notes_gen    │ open folder / web  │
│ whisper      │ parse_audit  │ corpus_setup │ export insights    │
│ lecture_auto │ cleanup      │ rag_status   │                    │
└──────┬───────┴──────┬───────┴──────┬───────┴────────────────────┘
       │              │              │
       v              v              v
  data/transcripts/   cleaned text   data/notes/*.md
                              │
                              v
              ┌───────────────────────────────┐
              │ Shared backend engine          │
              │ note_generation (RAG router)    │
              │ hybrid_notes / grounded_notes  │
              │ cleanup, chunk_polish, enrich  │
              │ corpus retrieve + registry     │
              │ llm_gateway + ollama_client    │
              └───────────────────────────────┘
                              │
                              v
              ┌───────────────────────────────┐
              │ data/corpus/ (Qdrant + BM25)   │
              │ textbooks + optional handoff   │
              └───────────────────────────────┘
```

---

## GUI (`gui.py`) — mandatory surface

Four workflow steps (left rail):

| Step | Tab / area | Key actions |
|------|------------|-------------|
| **1 Capture** | Live Captions, Whisper, Lecture Auto | `_run_captions`, `_run_lecture_auto`, `_finish_captions` |
| **2 Tune** | Parse & preview | `_run_parse_preview`, aggressive dedup, notes audit |
| **3 Generate** | RAG panel + LLM settings | `_run_summarize`, corpus quick init, auto batch |
| **4 Done** | Paths + Study Library link | `_open_output`, `_open_study_library` |

**Important GUI modules wired from `gui.py`:**

- `config.py` — settings persistence
- `notes_generator.py` — generate button entry
- `corpus_setup.py` — “Quick init (textbooks + MML)”
- `rag_status.py` — “RAG: ready” line + Generate button label
- `lecture_auto.py` — unattended pipeline
- `llm_client.py` — reachability check in status bar (legacy path)
- `cli.py` — same operations headless

**Threading model:** long work in `threading.Thread`; UI updates via `self.after(0, ...)`. Cancel via `threading.Event`.

**Config flags that affect UX (see `config.json`):**

- `auto_open_summarize` — skip “Open Summarize?” after capture
- `silent_generate_done` — no popup when notes saved
- `auto_fast_mode_word_threshold` — auto fast mode for large tuned transcripts
- `lecture_auto_*` — idle/max/RAG/fast/handoff

---

## Generate pipeline (decision tree)

```
User clicks Generate (gui._run_summarize)
    │
    ├─ pre_cleaned from Tune step (preferred)
    ├─ auto fast_mode if words ≥ threshold
    │
    v
notes_generator.generate_notes_from_file
    │
    ├─ legacy_pipeline forced? ──YES──► backend notes_generator + studio llm_client
    │
    └─ NO: rag_notes_available?
            │
            ├─ NO ──► legacy path
            │
            └─ YES ──► generate_notes_unified (backend_note_generation.py)
                    │
                    ├─ words > 1500? ──► hybrid_notes (chunked RAG)
                    │                      retrieve textbook chunks per segment
                    │                      LLM per chunk via llm_gateway
                    │
                    └─ short ──► grounded_notes single-shot
                                 finalize_full_note (optional enrich)
                    │
                    └─ corpus handoff (optional): index transcript + note for quiz
```

**RAG retrieval filter:** `NOTES_RAG_SOURCE_TYPES = ("textbook",)` in `backend_retrieve.py`.  
**Corpus UI count:** registry may list transcripts + saved notes (for quiz); notes generation ignores them.

---

## Data layout

| Path | Purpose |
|------|---------|
| `data/transcripts/` | Raw + cleaned `.txt` |
| `data/notes/` | Generated `.md` |
| `data/corpus/` | Qdrant + BM25 + registry |
| `data/logs/transcript_studio.log` | Studio app log |
| `data/logs/notes_generation.log` | Backend pipeline log |

---

## Dual LLM design (summary)

Studio uses **two** LLM stacks — see `AI_HANDLER.md` for detail:

| Stack | Used when | Entry |
|-------|-----------|-------|
| **AI handler** (`backend_llm_gateway.py`) | RAG generate, enrich, web API | `ollama_generate(..., task="corpus_grounded")` |
| **Studio client** (`llm_client.py`) | Legacy fallback, semantic cache | `generate(prompt)` direct httpx |

**Improvement target:** route Studio legacy through gateway too, or document one path only.

---

## Known pain points (for SSAST / improvement)

1. **14 “documents” in RAG UI** — mostly textbooks + handoff transcripts/notes; label now splits textbook vs rest.
2. **LM Studio ping storm** — multiple `GET /api/v1/models`; cached 20s in `llm_reachable`.
3. **Visual enrich** — Gemma sometimes returns chain-of-thought; guards in `backend_note_enrich.py` + `strip_llm_meta_preamble`.
4. **First hybrid run slow** — loads `SentenceTransformer` for retrieval embeddings.
5. **Quality preset “quality” + fast_mode** — fast disables enrich/refine; preset vs auto-fast can confuse.

---

## Related monorepo docs (not in this bundle)

- `docs/TRANSCRIPT_STUDIO_WORKFLOW.md` — full workflow
- `docs/LLM_GATEWAY.md` — gateway config (`data/llm_tiers.json`)
- `docs/CORPUS_RAG.md` — corpus ingest
