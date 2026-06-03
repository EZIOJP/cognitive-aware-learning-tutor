# Project Layout & File Locations

**Last updated:** 2026-06-02

Master map of the repo: what lives where, what to track, and where new files belong.
For GRE Vocab **component** paths only, see [FILE_MAP.md](FILE_MAP.md).

---

## Tracking & kernel (start here)

| File | Role | Update when |
|------|------|-------------|
| [AGENTS.md](../AGENTS.md) | Cursor agent role + Phase 1 scope | Phase or workflow changes |
| [FILE_MAP.md](FILE_MAP.md) | Vocab components, routes, API endpoints | Vocab files or routes move |
| [SESSION_LOG.md](SESSION_LOG.md) | Per-session checklist | Each work session |
| [PROJECT_LAYOUT.md](PROJECT_LAYOUT.md) | **This file** — full repo organization | Folders added/renamed |
| [ROADMAP.md](ROADMAP.md) | Multi-phase product roadmap | Phase milestones |
| [PROJECT_STATUS.md](PROJECT_STATUS.md) | Current focus + what works | Major status change |
| [TASKS.md](TASKS.md) | Simple kanban backlog | Task flow |
| [.cursor/rules/](../.cursor/rules/) | Auto-applied Cursor rules | Conventions change |

**Session prompt:**

```text
@AGENTS.md @docs/PROJECT_LAYOUT.md @docs/FILE_MAP.md @docs/SESSION_LOG.md
```

---

## Root directory

```text
Cognitive-Aware Learning Tutor/
├── run.bat                   # ONLY .bat at root — starts app (calls scripts\run_all.bat)
├── AGENTS.md                 # Cursor agent context (keep at root)
├── README.md                 # Project overview
├── package.json, vite.config.ts, index.html   # Frontend tooling (must stay at root)
├── src/                      # React app
├── public/                   # Static assets (words.json)
├── backend/                  # Python APIs (vocab, EEG reference, plugins)
├── scripts/                  # All other Windows .bat files
├── docs/                     # Documentation + planning
├── assets/                   # face_landmarker.task, theme CSS, ESP32 sample
├── data/                     # vocab_app.db, pipeline output, plate images
├── data_logs/                # Runtime CSV logs
├── refernces/                # Reference copies only
├── selftracker-extension/    # Chrome extension
├── hardware/                 # Firmware (.ino)
├── dist/, node_modules/      # Generated
└── .cursor/rules/            # Cursor rules
```

### Root files (minimal on purpose)

| Category | Files |
|----------|--------|
| **Launcher** | `run.bat` only |
| **App entry** | `index.html`, `vite.config.ts`, `postcss.config.mjs`, `package.json` |
| **Cursor** | `AGENTS.md` |
| **Overview** | `README.md` |

Everything else lives in subfolders — see [scripts/README.md](../scripts/README.md), [backend/](../backend/), [docs/README.md](README.md).

---

## `src/` — frontend application

```text
src/
├── main.tsx                  # React bootstrap
├── config.ts                 # URLs, cognitive load, pomodoro, interventions
├── app/
│   ├── App.tsx               # Router, providers, plugin routes
│   └── components/           # Shared UI (math, pomodoro, shadcn ui/*)
├── layout/                   # AppShell, Sidebar, TopBar, topbar docks
├── pages/                    # Route-level pages
│   ├── HomePage.tsx
│   ├── GreVocabPage.tsx
│   ├── MathTutorPage.tsx
│   ├── LifeTrackerPage.tsx
│   ├── ProfilePage.tsx
│   ├── auth/LoginPage.tsx
│   ├── admin/AdminPanelPage.tsx
│   ├── vocab/VocabReadPage.tsx, VocabCyclePage.tsx
│   └── settings/ThemeSettingsPage.tsx, PluginSettingsPage.tsx
├── features/vocab/           # GRE vocab feature (Phase 1 focus)
│   ├── components/read/      # ReadMode, WordCard
│   ├── cycle/                # cycleService + Cycle* components
│   ├── store/vocabStore.ts
│   └── api/                  # authClient, readModeAPI
├── plugins/                  # Pluggable modules (core, gre-vocab, nutrinode, life)
├── context/                  # Theme, Auth, StudySession, GoalTracker
├── components/theme/         # ThemeToggle
├── lib/                      # Small helpers (e.g. cognitiveLoadDisplay)
├── styles/                   # index.css, theme.css, glossy.css, tailwind.css
├── types/                    # Shared TS types
└── utils/                    # websocket.ts, etc.
```

**Phase 1 — primary touch:** `src/features/vocab/**`, `src/pages/GreVocabPage.tsx`, `src/pages/vocab/**`, `src/context/AuthContext.tsx`, `src/pages/admin/**`

**Phase 1 — avoid unless asked:** `src/pages/MathTutorPage.tsx`, `src/plugins/life_tracker*`, `src/layout/topbar/*` (Pomodoro/EEG docks), `src/app/components/AITutorIntervention.tsx`

---

## `public/`

| Path | Purpose |
|------|---------|
| `public/data/words.json` | Canonical GRE word list (backend reads/writes same path) |

---

## `backend/`

| File | Purpose |
|------|---------|
| `paths.py` | `ROOT`, `WORDS_PATH`, `DB_PATH`, `DATA_LOGS_DIR` (single source of truth) |
| `vocab_backend.py` | FastAPI vocab API, SQLite, JWT, admin, quiz, behavior WebSocket |
| `backend_example.py` | EEG UDP → WebSocket prototype |
| `face_tracker.py` | Face landmark tracker (model in `assets/`) |
| `requirements.txt` | Python dependencies |
| `plugins/nutrinode_plugin.py` | NutriNode API plugin |
| `plugins/pipeline_nutrition.py` | Nutrition CSV pipeline |

**Database:** `data/vocab_app.db` (falls back to root `vocab_app.db` if still present — stop backend and move file to migrate)

---

## `docs/`

| File | Purpose |
|------|---------|
| [PROJECT_LAYOUT.md](PROJECT_LAYOUT.md) | Repo organization (this file) |
| [FILE_MAP.md](FILE_MAP.md) | Vocab file + endpoint quick reference |
| [SESSION_LOG.md](SESSION_LOG.md) | Session checklist |
| [CURRENT_ARCHITECTURE.md](CURRENT_ARCHITECTURE.md) | Technical architecture |
| [SETUP_AND_COMMANDS.md](SETUP_AND_COMMANDS.md) | Install, deps, batch files |
| [FUTURE_VISION.md](FUTURE_VISION.md) | Long-term product vision |
| [VOCAB_EXECUTION_PLAN.md](VOCAB_EXECUTION_PLAN.md) | Vocab MVP execution steps |

---

## `refernces/` (reference only)

Copied designs and old stacks — **read for UX ideas, do not wire as dependencies.**

| Subfolder | Contents |
|-----------|----------|
| `refernces/vocab/` | Django VocabApp reference |
| `refernces/theme toggole/` | Theme toggle source |
| `refernces/Simplify Quiz UI/` | Quiz UI experiments |
| `refernces/nutrition-system/` | Nutrinode reference stack |
| `refernces/gre math/` | Math-related reference |
| `refernces/top_resdein/` | Design reference |

---

## `selftracker-extension/`

Chrome extension loaded unpacked from `chrome://extensions`.

| File | Role |
|------|------|
| `manifest.json` | Extension config |
| `background.js` | Service worker |
| `content.js` | Page scrapers (YouTube, Scalar, etc.) |
| `popup.html`, `dashboard.html` | UI surfaces |

Streams behavior to backend WebSocket; logs may land in `data_logs/`.

---

## `hardware/`

| Path | Role |
|------|------|
| `hardware/nutrinode/*.ino` | ESP32 firmware sketches |

---

## `data_logs/`

Runtime CSV output (e.g. `DSC_browser_behavior_YYYY-MM-DD.csv`). Created by backend/extension — not source code.

---

## Generated / local-only (usually not edited)

| Path | Notes |
|------|--------|
| `node_modules/` | `npm install` |
| `dist/` | `npm run build` |
| `__pycache__/` | Python |
| `.browser-profiles/` | Launch scripts for extension testing |
| `vocab_app.db` | Dev database |
| `*.crx`, `*.pem` | Packaged extension artifacts |

---

## Where to put **new** files

| You are adding… | Put it in… |
|-----------------|------------|
| Vocab UI component | `src/features/vocab/components/` or `cycle/components/` |
| Vocab page | `src/pages/vocab/` or extend `GreVocabPage.tsx` |
| Vocab API client | `src/features/vocab/api/` |
| New study plugin | `src/plugins/<name>/` + register in `src/plugins/index.ts` |
| Shared UI primitive | `src/app/components/ui/` (shadcn pattern) |
| Global context | `src/context/` |
| Vocab REST endpoint | `backend/vocab_backend.py` (router `/api/vocab`) |
| Project doc | `docs/` + link from this file or [SESSION_LOG](SESSION_LOG.md) |
| Reference / spike | `refernces/<topic>/` — never import into `src/` |
| Session note | Check off [SESSION_LOG.md](SESSION_LOG.md) |

---

## Quick commands

```bat
run.bat
rem or: scripts\run_backend.bat  /  scripts\run_frontend.bat  /  scripts\setup.bat
npm run build
```

Frontend: `http://localhost:5173` · Vocab API: `http://localhost:8000/api/vocab`
