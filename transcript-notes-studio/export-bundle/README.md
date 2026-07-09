# Transcript Notes Studio — Export Bundle (20 files)

Portable snapshot of the **most important** Studio + backend engine files for review, SSAST, and improvement planning.

**Hard limit:** 20 files in this folder (no subfolders).

## How to use this bundle

1. Read **`ARCHITECTURE_AND_GOALS.md`** first — product goals, data flow, GUI map.
2. Read **`AI_HANDLER.md`** — how `llm_gateway` works vs Studio `llm_client`.
3. Read **`WORKFLOW_QUICKREF.md`** — Capture → Tune → Generate → Done.
4. Open **`gui.py`** — mandatory UI orchestrator (~2.7k lines).
5. Trace generate: `notes_generator.py` → `backend_note_generation.py` → `backend_hybrid_notes.py` / `backend_grounded_notes.py`.

## File index (20)

| # | File | Role |
|---|------|------|
| 1 | `README.md` | This index |
| 2 | `ARCHITECTURE_AND_GOALS.md` | Architecture, goals, system map |
| 3 | `AI_HANDLER.md` | LLM gateway / dual-handler design |
| 4 | `WORKFLOW_QUICKREF.md` | Operator workflow + CLI |
| 5 | `gui.py` | **Main Tkinter GUI** — Capture, Tune, Generate, RAG panel |
| 6 | `config.py` | `AppConfig` dataclass + JSON load/save |
| 7 | `config.json` | Live settings example (paths, LLM, lecture auto) |
| 8 | `notes_generator.py` | Studio wrapper → backend or legacy LLM |
| 9 | `llm_client.py` | Direct LM Studio/Ollama client (legacy path) |
| 10 | `corpus_setup.py` | RAG quick init + corpus summary for UI |
| 11 | `rag_status.py` | RAG ready / legacy mode banner logic |
| 12 | `lecture_auto.py` | Unattended capture → parse → RAG → save |
| 13 | `cli.py` | Headless: parse, generate, lecture-auto |
| 14 | `backend_note_generation.py` | Unified entry: RAG-first, legacy fallback |
| 15 | `backend_hybrid_notes.py` | Long transcript: per-chunk RAG + merge |
| 16 | `backend_grounded_notes.py` | Short transcript: single-shot RAG |
| 17 | `backend_llm_gateway.py` | **AI handler** — tiers, tasks, fallback chains |
| 18 | `backend_ollama_client.py` | Transport to LM Studio / Ollama / OpenAI |
| 19 | `backend_retrieve.py` | Hybrid BM25 + vector retrieval (`textbook` filter) |
| 20 | `backend_note_enrich.py` | Post-merge mermaid/code enrich pass |

## Canonical paths in monorepo

| Export copy | Live path |
|-------------|-----------|
| `gui.py` | `transcript-notes-studio/transcript_studio/gui.py` |
| `backend_*.py` | `backend/...` (strip `backend_` prefix) |

## Run Studio (from monorepo)

```bat
transcript-notes-studio\run.bat
```

Logs: `data/logs/transcript_studio.log`, `data/logs/notes_generation.log`
