# CALT Desktop Tracker — Backend Export (full)

**Date:** 2026-09-06  
**Pack:** [README](./2026-09-06-calt-desktop-tracker-README.md) · [Architecture](./2026-09-06-desktop-tracker-architecture-export.md)  
**Legal:** CALT original only.

---

## 1. Role of the backend

FastAPI owns:

- Gate / SoftLand **compute** + JSON for extensions  
- `SESSION_END` ingest → `tracked_sessions`  
- Desktop / browser **stats** aggregation  
- Focus dashboard snapshot + PIN free / spend earned  
- Publish `enforcer_runtime` for C++ kills  
- Category backfill for native rows  

Does **not** own OS kills when native lock is active.

---

## 2. Database

**File:** `data/vocab_app.db`

### `tracked_sessions`

| Column | Notes |
|--------|--------|
| `session_id` | PK / dedupe |
| `user_id` | Owner |
| `start_time` / `end_time` | UTC |
| `source` | `extension` \| `desktop_tracker` \| `calt_spa` |
| `app_name` | Exe — Edge = `msedge.exe` |
| `window_title` | Page · URL · domain for tabs |
| `category` | Productivity category |
| `category_source` | e.g. `native`, `extension_label`, `url_rule` |

Model: `backend/models/timetable.py` → `TrackedSession`

### `enforcer_runtime`

| Column | Notes |
|--------|--------|
| `hard_block_armed` / `gate_locked` / `incubation_active` | Flags |
| `exes_json` | Kill list for C++ |
| `updated_at` | Freshness |

Model: `backend/models/enforcer_runtime.py`  
Alembic: `0034_enforcer_runtime`  
Publish: `backend/behavior/enforcer_runtime_publish.py`

### `productivity_policies`

Allow/deny/overrides + scores — `backend/behavior/productivity_policy.py`

---

## 3. Ingest pipeline

```text
SESSION_END (WS or HTTP batch)
  → router._persist_behavior_event / batch
  → tracker_bridge.ingest_behavior_session
  → TrackedSession row
```

**Extension branch:** normalize `exe` → `msedge.exe`, enrich title with URL/domain.  
**Bridge:** `backend/timetable/tracker_bridge.py`  
**Labels:** `backend/behavior/browser_labels.py`  
**Ignore:** `backend/behavior/tracker_ignore.py` — keep `source=extension` Edge; drop bare desktop Edge.

`LIVE_SNAPSHOT` — UI only; **not** written as sessions.

---

## 4. Aggregation

| Module | Job |
|--------|-----|
| `stats_aggregate.py` | App buckets; browsers nest `sites[]`; `display_name` |
| `session_merge.py` | Merge/filter for calendar |
| `native_session_backfill.py` | Classify `category_source=native` on Focus/stats refresh |
| `csv_backfill.py` | CSV → SQLite when writes lagged |

Payload example:

```json
{
  "kind": "browser",
  "exe": "msedge.exe",
  "display_name": "Microsoft Edge",
  "seconds": 120,
  "sites": [{ "site": "youtube.com", "seconds": 90 }]
}
```

---

## 5. Key HTTP / WS APIs

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/behavior/desktop-stats` | App/site bars |
| GET | `/api/behavior/stats` | Browser day stats |
| GET | `/api/behavior/desktop-timeline` | Day intervals |
| GET | `/api/behavior/tracker-health` | Alive / last beat |
| GET | `/api/behavior/focus-dashboard` | Focus snapshot |
| POST | `/api/behavior/focus-free-override` | PIN free |
| POST | `/api/behavior/focus-spend-earned` | Spend earned |
| GET | `/api/behavior/distraction-gate` | Gate + SoftLand |
| GET/PUT | `/api/behavior/policy` | Productivity policy |
| POST | `/api/behavior/browser-telemetry` | Light telemetry |
| WS | behavior socket (see `router.py`) | Extension events |

Router hub: `backend/behavior/router.py`  
Focus snapshot: `backend/behavior/calt_desktop/dashboard_bridge.py`

---

## 6. Gate + enforcer publish

| File | Role |
|------|------|
| `distraction_gate.py` | Gate brain |
| `browser_gate_policy.py` | Browser mode payload |
| `enforcer_runtime_publish.py` | Write kill snapshot |
| `enforcer_ownership.py` | Who owns kills/track |
| `native_enforcer_status.py` | Exe / service / last kill |

---

## 7. Backend file list (read order)

1. `backend/timetable/tracker_bridge.py`  
2. `backend/behavior/browser_labels.py`  
3. `backend/behavior/tracker_ignore.py`  
4. `backend/behavior/stats_aggregate.py`  
5. `backend/behavior/router.py` (desktop-stats + focus + WS)  
6. `backend/behavior/distraction_gate.py`  
7. `backend/behavior/enforcer_runtime_publish.py`  
8. `backend/behavior/native_session_backfill.py`  
9. `backend/behavior/calt_desktop/dashboard_bridge.py`  
10. `backend/models/timetable.py` + `enforcer_runtime.py`

---

## 8. Tests

```bat
set PYTHONPATH=%CD%
python -m pytest tests/test_edge_tab_tracking.py tests/test_native_session_backfill.py tests/test_desktop_tracker.py -q
```

---

## 9. Cross-links

- Architecture: [architecture-export](./2026-09-06-desktop-tracker-architecture-export.md)  
- Frontend: [frontend-export](./2026-09-06-desktop-tracker-frontend-export.md)  
- Native: [native-export](./2026-09-06-desktop-tracker-native-export.md)
