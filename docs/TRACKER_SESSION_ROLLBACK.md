# Tracker session grouper — rollback plan

Changes: session grouping at poll layer, read-time merge for UI, force-sync button, `max_session_s` default 120.

## What changed (files)

| File | Change |
|------|--------|
| `backend/behavior/session_key.py` | **New** — browser site grouping |
| `backend/behavior/session_merge.py` | **New** — merge adjacent intervals for display |
| `backend/behavior/tracker_service.py` | Group by `group_key`, classify at flush, force-sync poll |
| `backend/behavior/tracker_storage.py` | Flush signal files, `max_session_s` 120 |
| `backend/behavior/router.py` | Merge in stats/timeline, `POST /tracker-force-sync` |
| `src/api/behaviorClient.ts` | `forceTrackerSync()` |
| `src/pages/ProductivityPage.tsx` | Sync tracker button |
| `tests/test_desktop_tracker.py` | New tests |

**Not changed:** DB schema, planner adherence formula, extension, historical `tracked_sessions` rows.

## Quick rollback (no data loss)

### 1. Stop tracker

```bat
REM Tray: right-click → Quit
REM Or kill pythonw running desktop_tracker
taskkill /F /IM pythonw.exe /FI "WINDOWTITLE eq *" 2>nul
```

### 2. Revert code

```bat
git checkout HEAD -- backend/behavior/session_key.py backend/behavior/session_merge.py
git checkout HEAD -- backend/behavior/tracker_service.py backend/behavior/tracker_storage.py
git checkout HEAD -- backend/behavior/router.py
git checkout HEAD -- src/api/behaviorClient.ts src/pages/ProductivityPage.tsx
git checkout HEAD -- tests/test_desktop_tracker.py
```

If new files were never committed, delete them:

```bat
del backend\behavior\session_key.py backend\behavior\session_merge.py
```

### 3. Restore tracker config (optional)

If you want 30s flushes again, edit or delete:

`%LOCALAPPDATA%\CognitiveAwareTutor\tracker.json`

```json
{ "max_session_s": 30.0 }
```

Or set env: `set DESKTOP_MAX_SESSION=30`

### 4. Restart services

```bat
scripts\run_desktop_tracker_headless.bat
REM Restart API (run.bat or uvicorn)
```

### 5. Clear signal files (harmless if left)

```bat
del %LOCALAPPDATA%\CognitiveAwareTutor\tracker_flush.request
del %LOCALAPPDATA%\CognitiveAwareTutor\tracker_flush.ack
```

## Partial rollback

| Symptom | Rollback slice |
|---------|----------------|
| Timeline looks wrong | Revert only `session_merge.py` + merge calls in `router.py` |
| Browser grouping too aggressive | Revert only `session_key.py` + grouping block in `tracker_service.py` |
| Sync button errors | Revert `router.py` endpoint + frontend button; tracker still works |
| Too few DB rows | Set `max_session_s` back to 30 in `tracker.json` |

## Verify after rollback

```bat
python -m pytest tests/test_desktop_tracker.py -q
curl http://localhost:8000/api/behavior/tracker-health
```

Productivity page should load; Refresh works; tracker banner shows running/stale/no_data.

## Verify after forward deploy

1. Restart desktop tracker (required for poll-layer changes).
2. Productivity → **Sync tracker** → message "Synced" if tray app running.
3. Stay on one browser site 2+ min → timeline shows merged bar (not dozens of 30s slivers).
4. `python -m pytest tests/test_desktop_tracker.py -q`

## Data note

Existing `tracked_sessions` rows are **not** rewritten. New grouping applies to **new** flushes only. UI merge smooths old fragmented rows on read.
