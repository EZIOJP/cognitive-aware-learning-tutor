# Current Architecture

What exists in the project **today** (2026-06). For the target math vision pipeline, see [MATH_TUTOR_VISION_PIPELINE.md](./MATH_TUTOR_VISION_PIPELINE.md).

## App summary

Local-first study platform: **hub + plugins**, GRE vocab, math tutor, life tracker, optional EEG/NutriNode/focus mirror.

```text
React (Vite)  →  FastAPI backend/main.py  →  SQLite (vocab_app.db)
                     ↳ hub, vocab, math, behavior, insights, EEG WS, plugins
```

Daily checklist: [WORKING_PRODUCT.md](./WORKING_PRODUCT.md).

## Frontend stack

- Vite 6, React 18, TypeScript, React Router
- Tailwind 4, Radix/shadcn-style UI, Recharts
- **Math whiteboard:** `react-sketch-canvas` (`MathSplitWhiteboard.tsx`)
- Plugins: `src/plugins/*` + `PluginRegistryProvider` (server sync)

## Entry points

```text
src/main.tsx → src/app/App.tsx → AppShell
```

Key routes:

```text
/                         Hub dashboard (widgets, life clock, AI review)
/math-tutor               Math hub
/math-tutor/practice/:id  Practice + whiteboard + Ask tutor
/gre-vocab                GRE hub (Phase 1 complete)
/gre-vocab/read/:mode     Read modes (API when signed in)
/gre-vocab/cycle          Read → quiz → report
/settings/plugins         Plugin manager
/settings/features        Feature Studio
/focus/calibrate          Face calibration UI
/admin                    Admin (words, users, export)
/login
```

## Global providers

```text
AuthProvider → PluginRegistryProvider → StudySessionProvider → …
ThemeContext, GoalTrackerContext, NutritionProvider (NutriNode)
```

`StudySessionContext`:

- EEG stream when **eeg** plugin enabled (`useSimulatedData` default true)
- Cognitive load from gamma thresholds
- Canvas image state for math
- Intervention flags (auto off: `config.intervention.enabled = false`)
- Posts `eeg_attention` to hub every 30s when authenticated

## Hub and plugins

Backend:

```text
backend/hub/router.py          readings, rollups, plugins, custom features, layout, export
backend/hub/services/catalog.py
backend/hub/services/features.py
alembic/0006_user_features.py
```

Frontend:

```text
src/api/hubClient.ts
src/pages/settings/FeatureStudioPage.tsx
src/plugins/PluginRegistryProvider.tsx
```

Plugins: core hub, math-tutor, gre-vocab, life-tracker, eeg, focus-mirror, nutrinode.

## GRE vocabulary

- **Signed in:** `/api/vocab` — groups, adaptive quiz, `POST /progress/{id}/read`, by-criteria lists
- **Guest:** `public/data/words.json` + `localStorage` fallback
- Docs: [GRE_VOCAB_PHASE1.md](./GRE_VOCAB_PHASE1.md)

## Math tutor

```text
src/pages/math/MathPracticePage.tsx
src/app/components/MathSplitWhiteboard.tsx   exportPng → tutor hint
backend/math/router.py                       POST /api/math/tutor/hint
backend/math/rule_tutor.py                   default (no GPU)
backend/math/ollama_tutor.py                 OLLAMA_ENABLED=1 only
```

Not yet: auto stuckness, `/api/math/intervention`, OpenCV/OCR pipeline, structured Socratic JSON.

## Focus mirror (Python, not browser)

```text
backend/face_tracker.py          OpenCV + MediaPipe, mirrored video, readable HUD text
scripts/run_face_tracker.bat
POST /api/vocab/face/status      → hub face_attention (JWT or dev_mode)
```

Browser `FaceMirror` / MediaPipe frontend was **removed**; use Python window only.

## EEG

```text
backend/eeg/service.py           UDP :5005 when EEG_ENABLED=1
backend/eeg/router.py            WebSocket /ws/eeg
Frontend                         simulation default; WS when useSimulatedData false
```

## Behavior / life / NutriNode

- Chrome extension → behavior WebSocket → hub
- Life tracker daily log → hub rollups → Life Clock widget
- NutriNode: manual meals + optional live WS (off by default)

## Data storage

| Data | Where |
|------|--------|
| Users, progress, hub | SQLite via SQLAlchemy |
| Browser extension logs | `data_logs/DSC_browser_behavior_*.csv` |
| Local DB file | `vocab_app.db` (gitignored in practice) |
| Intervention flywheel (target) | `DSC_*.csv` + `data_logs/interventions/` — partial / example only |

## Legacy reference files (do not treat as production entry)

```text
backend_example.py    UDP/FFT/intervention prototype
vocab_backend.py        older vocab-only server
```

Production API: **`backend/main.py`**.

## Build

```bat
run.bat          migrations + API + frontend
npm run build    succeeds (large chunk warning OK)
```
