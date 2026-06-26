# Corpus / RAG status

Last updated: second-brain loop (grounded notes, studio handoff, golden benchmark).

## Quick checks

```bat
python -m backend.corpus.cli health
python -m backend.corpus.cli status
python -m backend.corpus.cli benchmark
python -m backend.corpus.cli build-golden
python -m backend.corpus.cli purge-test
```

Or use **Knowledge Base** (`/knowledge-base`) → **Build Knowledge Base**.

## Expected chunk counts (after full ingest)

| Document | document_id | ~chunks |
|----------|-------------|--------:|
| Mathematics for Machine Learning (ch 1–2) | `mml_2021_deisenroth` | 70 |
| Data Science from Scratch (full PDF) | `ds_from_scratch_2019` | 1,480 |
| Practical Statistics (full PDF) | `practical_stats_3e` | 600 |
| Designing ML Systems (full PDF) | `designing_ml_systems_2022` | 525 |
| AI: Guide for Thinking Humans (full PDF) | `ai_thinking_humans_2019` | 380 |
| Lecture transcript (per file) | `transcript_<stem>` | varies |

Run `python -m backend.corpus.cli status` to compare live counts.

## Study loop (second brain)

| Step | Where | Status |
|------|-------|--------|
| Capture + generate | Transcript Notes Studio | Done |
| Auto-ingest transcript + note | Studio Done + web Generate | Done (`backend/corpus/handoff.py`) |
| Grounded notes (RAG writer) | Lecture Notes → Create → **Generate grounded (RAG)** | Done — set `CORPUS_GROUNDED_NOTES=1` |
| Quiz / drills / gap | Lecture Notes tabs | Done |
| Spaced review | Review Hub | Done |

## Architecture delivered

| Sprint | Feature |
|--------|---------|
| 1b | MML Ch 1–2 ingest, KG concept seeds, lecture `aligns_with`, golden benchmark, quiz citations |
| 2 | `code_lint`, mermaid/python note lint on save, citation checker, grounded notes API |
| 3 | KG graph retrieval in `hybrid_retrieve`, gap-driven lazy book ingest, pandoc preflight in GUI |
| 4 | Quiz failures log to KG via `source_chunk_id`, SRS due queue biased by weak topics, retrieval boost |
| 5 | Full PDF ingest in auto-setup, `ingest-all-books` CLI/API, per-book Index in Knowledge Base UI |
| 6 | Grounded notes UI, studio/web corpus handoff, `build-golden` CLI, expected chunk table |

## Resolved (latest)

| Issue | Fix |
|-------|-----|
| Grounded notes UI button | Lecture Notes create sheet + `CORPUS_GROUNDED_NOTES=1` |
| Studio → corpus handoff | Auto `ingest_lecture_handoff` after Generate in Studio GUI |
| Web generate → corpus | `POST /notes/generate` calls handoff after save |
| Stale golden benchmark | `python -m backend.corpus.cli build-golden` refreshes fixture from live retrieval |

## Deferred (not blockers)

| Item | Notes |
|------|-------|
| LightRAG package | Install later if KPIs justify; v1 uses `graph_retrieve.py` KG bridge |
| Pandoc on PATH | Required for EPUB ingest; all current books are PDF |
| HF_TOKEN warnings | Cosmetic during first embedding model download |

## Environment

| Tool | Purpose |
|------|---------|
| `pandoc` | EPUB textbook ingest (optional) |
| LM Studio / Ollama | Grounded notes + equation node extraction |
| `HF_TOKEN` (optional) | Faster embedding model download |

## Key paths

- Raw books: `data/raw_library/`
- Index: `data/corpus/registry.db`, `bm25.pkl`, `qdrant/`
- Golden set: `tests/fixtures/mml_golden_qa.json`
- Setup log: `data/logs/corpus_setup_latest.log`

## Feature flags

```env
CORPUS_GROUNDED_NOTES=1
```

Enables corpus-grounded notes API and the **Generate grounded (RAG)** button in Lecture Notes.
