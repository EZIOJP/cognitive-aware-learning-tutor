# GRE lane — architecture design pack

Self-contained design copy for **GRE vocabulary**, **math practice**, and **math OCR / intervention**.

Aimed at **low-level designers** who need the order of systems, APIs, and files — not a full product dump.

## Read in this order

1. [GIST.md](GIST.md) — mental model + happy paths (2 minutes)
2. [HLD.md](HLD.md) — contexts, loops, boundaries
3. [LLD.md](LLD.md) — endpoints, call graphs, modules, schemas
4. [FILE_MAP.md](FILE_MAP.md) — URL → page → backend file

## Scope (in)

| Subsystem | API prefix | Status |
|-----------|------------|--------|
| GRE vocab (auth, progress, cycle quiz) | `/api/vocab` | Phase 1 complete |
| Math question bank + practice | `/api/math` | Shipped |
| Math OCR + stuckness intervention | `/api/math/ocr`, `/api/math/intervention` | Shipped (quality still improving) |

## Scope (out)

Lecture notes / corpus RAG / global quiz SRS — see `export-bundle/notes-gen-render/` and `docs/COMPLETION_SPRINT.md`.  
Pomodoro, Life Tracker, EEG hardware — touch only when asked.

## Live docs (source of truth if this pack drifts)

| Topic | Live doc |
|-------|----------|
| Full product HLD/LLD | `docs/HLD.md`, `docs/LLD.md` |
| GRE Phase 1 checklist | `docs/GRE_VOCAB_PHASE1.md` |
| Math OCR / vision | `docs/MATH_TUTOR_VISION_PIPELINE.md` |
| Canvas OCR roadmap | `docs/CANVAS_OCR_ROADMAP.md` |
| Vocab file map | `docs/FILE_MAP.md` |
