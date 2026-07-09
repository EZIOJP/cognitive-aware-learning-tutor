# Current Architecture

**Last updated:** 2026-06-26

**Full design:** [HLD.md](./HLD.md) (system context, study loops, gaps) · [LLD.md](./LLD.md) (algorithms, schemas, file map)

What exists in the project **today**. For math vision targets, see [MATH_TUTOR_VISION_PIPELINE.md](./MATH_TUTOR_VISION_PIPELINE.md). Daily checklist: [WORKING_PRODUCT.md](./WORKING_PRODUCT.md).

---

## App summary

Local-first study platform: **hub + plugins**, GRE vocab, math tutor, lecture second-brain (corpus/RAG), global quiz/SRS, life tracker, optional EEG/NutriNode/focus mirror.

```text
React (Vite)  →  FastAPI backend/main.py  →  SQLite (vocab_app.db)
                     ↳ hub, vocab, quiz, corpus, transcripts, math, insights, behavior
                     ↳ corpus registry + BM25 + vectors (separate indexes)
```

---

## Stack

| Layer | Technology |
|-------|------------|
| Frontend | Vite 6, React 18, TypeScript, React Router 7, Tailwind 4 |
| UI | Radix/shadcn-style components, Recharts |
| Backend | FastAPI modular monolith, SQLAlchemy, Alembic |
| DB | SQLite (`data/vocab_app.db`) |
| Corpus | `data/corpus/registry.db` + BM25 + local vectors |

---

## Entry points

```text
src/main.tsx → src/app/App.tsx → AppShell
run.bat      → migrations + API :8000 + Vite :5173
```

**Production API:** `backend/main.py` (not `vocab_backend.py`).

---

## Key routes

```text
/                         Dashboard (StudyLoopWidget, Life Clock, AI review)
/gre-vocab/cycle          GRE Read → quiz → report (Phase 1 complete)
/lecture-notes            Transcript library + note generation
/knowledge-base           Corpus ingest / auto-setup
/review                   Global quiz + spaced repetition
/math-tutor/practice/:id  Whiteboard + Ask tutor
/settings/plugins         Plugin manager
/login · /admin
```

Plugin-registered routes: see [LLD.md §13](./LLD.md#13-frontend-route-map).

---

## Providers

```text
ThemeProvider → AuthProvider → PluginRegistryProvider → PomodoroProvider
  → StudySessionProvider → plugin providers (GoalTracker, Nutrition, …)
```

`StudySessionContext`: EEG (simulated by default), cognitive load from gamma thresholds, math canvas state.

---

## Data at a glance

| Data | Where |
|------|--------|
| Users, progress, hub, quiz, KG | `data/vocab_app.db` |
| Corpus chunks | `data/corpus/registry.db` |
| Transcripts, notes, books | `data/transcripts/`, `data/notes/`, `data/raw_library/` |
| GRE words bootstrap | `public/data/words.json` |

Detail: [LLD.md §3](./LLD.md#3-data-stores).

---

## Optional upgrades

| Feature | Enable |
|---------|--------|
| Local LLM | `OLLAMA_ENABLED=1` — see [AI_HANDLER.md](./AI_HANDLER.md) |
| Corpus-grounded notes | `CORPUS_GROUNDED_NOTES=1` |
| Real EEG | `EEG_ENABLED=1` + ESP32 firmware |
| Face mirror | `scripts/run_face_tracker.bat` |

See [HARDWARE_AND_AI_LATER.md](./HARDWARE_AND_AI_LATER.md).

---

## Build

```bat
run.bat
npm run build
```
