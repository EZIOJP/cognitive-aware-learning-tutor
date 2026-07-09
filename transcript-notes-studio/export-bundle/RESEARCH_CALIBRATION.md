# Research Calibration — Gemini Note + PDF vs This Repo

This document maps your research ([`Let me calibrate Gemini's take agai.txt`](file:///c:/Users/Lenovo/Desktop/Let%20me%20calibrate%20Gemini's%20take%20agai.txt) and [`Local Lecture Notes Pipeline Best Practices.pdf`](file:///c:/Users/Lenovo/Downloads/Local%20Lecture%20Notes%20Pipeline%20Best%20Practices.pdf)) to **verified repo state** and implementation phases.

---

## Gemini calibration (your note)

| Claim | Verdict | Repo evidence |
|-------|---------|---------------|
| `gui.py` 2.7k lines mixes UI + pipeline | **Correct** | Refactor to service layer is Phase 3 (Option A) |
| Legacy is default path | **Wrong** | RAG first in `notes_generator.py` → `generate_notes_unified` |
| Preprocessing missing | **Wrong** | `cleanup.py`, `chunked_parse.py`, aggressive dedup on `live_captions_*` |
| `CHUNK_PROMPT` brace crash | **Was open — fixed** | `_escape_format_braces` on chunk + reference in `summarize_chunk` |
| Empty chunk kills run | **Was open — fixed** | `placeholder_for_failed_chunk` + continue |
| Qdrant lock freeze | **Correct** | Singleton client + GUI SQLite warning; use `run_backend_no_reload.bat` |
| `semantic_grouper` dead >180 segments | **Fixed** | `backend/transcripts/semantic_chunker.py` wired in `_select_chunks` |
| sqlalchemy startup crash | **Fixed** | Optional import in `graph_retrieve.py` |

---

## PDF best practices → phase map

| PDF topic | Phase 1 (reliability) | Phase 2 (quality) | Phase 3 (architecture) |
|-----------|----------------------|---------------------|-------------------------|
| Spectral / M3Seg / ToC-LLM segmentation | — | Wire `semantic_chunker.py` | Full spectral if needed |
| Narrative / proof-chain prompts | — | New prompt templates | — |
| RAPTOR tree | — | — | Optional large effort |
| Sequential refine + state | Partial (`refine_second_pass`) | **Done** — compact / sequential / cloud_heavy modes | — |
| G-Eval / NLI eval | — | **Done** — heuristics + optional `narrative_judge` | Local G-Eval judge |
| Disfluency tagger / recasepunc | — | **Done** — `asr_restore.py` | — |
| Qdrant server mode | Documented | Docker Qdrant if singleton insufficient | — |

---

## Phase 2 quality checklist

- [x] ASR punctuation restore (`backend/transcripts/asr_restore.py`)
- [x] Semantic chunker backend + percentile mode
- [x] Narrative prompt + factual-lock (`note_style=narrative`)
- [x] Coherence modes: `compact` (default), `sequential`, `cloud_heavy`
- [x] Narrative heuristics + optional LLM judge (`NARRATIVE_LOW` marker)
- [x] Quality preset: semantic + refine + narrative + ASR restore

---

## Phase 1 reliability checklist (this sprint)

- [x] Escape braces in `CHUNK_PROMPT.format()`
- [x] Chunk placeholder instead of abort
- [x] Qdrant singleton per process + `retrieval_backend()`
- [x] GUI warning when SQLite vector fallback
- [x] LINT_FAILED visible in status bar after save
- [x] `scripts/run_backend_no_reload.bat`
- [x] Acceptance: generate cleaned 10k-word lecture (`test_!.txt`) end-to-end — `reliability_acceptance_*.md`, mode `hybrid_grounded`

---

## Dual LLM paths (AI handler)

| Path | Entry | When |
|------|-------|------|
| **Gateway** | `backend/core/llm_gateway.py` | RAG hybrid/grounded, enrich |
| **Studio client** | `transcript_studio/llm_client.py` | Legacy fallback only |

Unifying legacy through gateway is Phase 3.

---

## Operator quick fixes

1. Before Generate: one LM Studio model loaded; kill extra Python processes.
2. Don't use `run_backend.bat` (`--reload`) while Studio generates notes.
3. If RAG line shows **SQLite vectors**, restart Studio after closing backend.
4. `grep LINT_FAILED data/notes/*.md` for broken block markers.

See also: [`WORKFLOW_QUICKREF.md`](WORKFLOW_QUICKREF.md), [`AI_HANDLER.md`](AI_HANDLER.md).
