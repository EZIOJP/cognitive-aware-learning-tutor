# File Map

Quick anchor for GRE Vocab Phase 1. Paths verified against this repo.

For **full repo organization** (all folders, scripts, extension, references), see [PROJECT_LAYOUT.md](PROJECT_LAYOUT.md).

## Routes (plugin-registered)

Defined in `src/plugins/core_plugins.tsx` (`VocabPlugin`):

| URL | Page |
|-----|------|
| `/gre-vocab` | Hub |
| `/gre-vocab/read` | Read all words |
| `/gre-vocab/read/:mode` | Filtered read (`low-mastery`, `due`, etc.) |
| `/gre-vocab/cycle` | Cycle Manager |
| `/login` | Auth |
| `/admin` | Admin panel (admin users) |

## Vocab feature — frontend

| Role | Path |
|------|------|
| Hub page | `src/pages/GreVocabPage.tsx` |
| Read page | `src/pages/vocab/VocabReadPage.tsx` |
| Read UI | `src/features/vocab/components/read/ReadMode.tsx` |
| Word card | `src/features/vocab/components/read/WordCard.tsx` |
| Cycle page | `src/pages/vocab/VocabCyclePage.tsx` |
| Cycle orchestrator | `src/features/vocab/cycle/components/CycleManager.tsx` |
| Cycle dashboard | `src/features/vocab/cycle/components/CycleDashboard.tsx` |
| Cycle read step | `src/features/vocab/cycle/components/CycleReadStep.tsx` |
| Cycle quiz step | `src/features/vocab/cycle/components/CycleQuizStep.tsx` |
| Cycle report step | `src/features/vocab/cycle/components/CycleReportStep.tsx` |
| Low-mastery prompt | `src/features/vocab/cycle/components/LowMasteryPrompt.tsx` |
| Local progress store | `src/features/vocab/store/vocabStore.ts` |
| Cycle logic (local) | `src/features/vocab/cycle/cycleService.ts` |
| Auth API client | `src/features/vocab/api/authClient.ts` |
| Read fetch helpers | `src/features/vocab/api/readModeAPI.ts` *(mostly wraps store today)* |
| Shared types | `src/features/vocab/types.ts` |
| Cycle types | `src/features/vocab/cycle/types.ts` |
| Word data (JSON) | `public/data/words.json` |

**Legacy (do not extend):** `src/features/vocab/components/UniversalReadMode.jsx`, `UniversalReadMode.css`

## Auth & admin

| Role | Path |
|------|------|
| Auth context | `src/context/AuthContext.tsx` |
| Login page | `src/pages/auth/LoginPage.tsx` |
| Admin page | `src/pages/admin/AdminPanelPage.tsx` |

Token key: `vocab:auth-token` · API base: `VITE_VOCAB_API_BASE` or `http://localhost:8000/api/vocab`

## Layout shell

| Role | Path |
|------|------|
| App routes / providers | `src/app/App.tsx` |
| Shell | `src/layout/AppShell.tsx` |
| Sidebar | `src/layout/AppSidebar.tsx` |
| Top bar + account | `src/layout/AppTopBar.tsx` |
| App config | `src/config.ts` |

## Backend

| Role | Path |
|------|------|
| Vocab FastAPI app | `backend/vocab_backend.py` |
| Path constants | `backend/paths.py` |
| EEG prototype (optional mount) | `backend/backend_example.py` |
| SQLite DB | `data/vocab_app.db` |
| Python deps | `backend/requirements.txt` |
| Start (root) | `run.bat` |
| Start (backend only) | `scripts/run_backend.bat` |
| Refresh deps | `scripts/setup.bat` |

**Groups:** 30 words per `group_number` (`GROUP_SIZE = 30` in `vocab_backend.py`).

## Key API endpoints (prefix `/api/vocab`)

All paths below are relative to that prefix. FastAPI routes use trailing slashes where noted.

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/auth/login` | JWT login |
| POST | `/auth/register` | Register |
| GET | `/auth/me` | Current user |
| GET | `/groups/detailed/` | Words by group + merged user progress |
| GET | `/quiz/dashboard/` | Cycle dashboard |
| GET | `/words/by-criteria/` | Filter (group, mastery, due, ids, …) |
| POST | `/quiz/adaptive/start/` | Start quiz session |
| GET | `/quiz/adaptive/{session_id}/question/` | Next question |
| POST | `/quiz/adaptive/{session_id}/answer/` | Submit one answer |
| POST | `/quiz/adaptive/{session_id}/complete/` | Finish quiz session |
| PATCH | `/progress/{word_id}` | Update one word’s progress |
| GET | `/progress/summary` | Aggregate progress |

**Not available:** `GET /words` (use `/groups/detailed/` or `/words/by-criteria/`), bulk `POST /progress`.

### Admin (admin user)

`GET /admin/users`, `POST /admin/users/{id}/reset-progress`, word CRUD `/words`, CSV import/export.

## Known dual data path

Many UI flows still use **localStorage** via `vocabStore.ts` / `cycleService.ts`. Backend endpoints exist for auth, groups, quiz, and progress — Phase 1 goal is to close gaps between UI and API.

## Productivity / Plan vs Actual

| Role | Path |
|------|------|
| Dashboard shell | `src/components/productivity/PlanVsActualDashboard.tsx` |
| Day ribbon | `src/components/productivity/DayRibbon.tsx` |
| Weekly heatmap | `src/components/productivity/WeeklyAdherenceHeatmap.tsx` |
| Streak | `src/components/productivity/AdherenceStreak.tsx` |
| Category chart | `src/components/productivity/CategoryVarianceChart.tsx` |
| Hooks | `src/hooks/usePlanVsActual.ts` |
| Utils | `src/components/productivity/planVsActualUtils.ts` |
| Productivity page | `src/pages/ProductivityPage.tsx` |
| API clients | `src/api/plannerClient.ts`, `src/api/behaviorClient.ts`, `src/api/timetableClient.ts` |

**Endpoints consumed:** `GET /api/planner/blocks`, `/overlay/actual`, `/adherence`; `GET /api/behavior/desktop-timeline`, `/tracker-health`.

## LLM Classification Review

| Role | Path |
|------|------|
| Models | `backend/models/app_classification.py` |
| Service | `backend/behavior/classification_service.py` |
| Router | `backend/behavior/classification_router.py` |
| Migration | `alembic/versions/0022_app_classification.py` |
| Cache bridge | `backend/timetable/tracker_bridge.py` (cache lookup) |
| Frontend panel | `src/components/productivity/ClassificationReview.tsx` |
| API client | `src/api/behaviorClient.ts` (scan/pending/approve/reject/edit/revert) |

**Endpoints:** `POST /api/classification/scan`, `GET /pending`, `GET /{id}/preview`, `POST /{id}/approve`, `POST /{id}/reject`, `POST /{id}/edit-and-approve`, `POST /{id}/revert`.
