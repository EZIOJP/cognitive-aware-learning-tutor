# Bible chapter-a-day + offline verse reader — Implementation Plan

> Spec: `docs/superpowers/specs/2026-07-23-bible-structured-reader-design.md`

**Goal:** Offline JSON Bible (WEB), 1 chapter/day goal, study+chapter → unlimited until midnight, watch verse rotation from today’s chapters.

**Status:** Implemented 2026-07-23

## Delivered

1. **Data + API** — `data/bible/structured/web.json`, `backend/bible/structured.py`, `GET /api/bible/v2/meta`, `GET /api/bible/v2/read/...`, rebuild via `scripts/import_web_bible.py`
2. **Chapter goal + gate** — tick + chapter heartbeat; `day_unlimited` = study goal + ≥1 chapter (or day pass); minute-bank no longer unlocks
3. **UI** — `/bible` verse reader (`BibleReaderPage.tsx`)
4. **Watch** — `GET /api/hub/bible-verse` on tracker hub + main hub
5. **Tests** — `tests/test_bible_structured.py` (8 bible tests green)
