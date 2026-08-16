# Bible reader + game gate — plan

> **For agentic workers:** Implement; do not document tracker bypasses.

## Files

| Path | Role |
|------|------|
| `backend/bible/paths.py` | PDF path + seed from Downloads |
| `backend/bible/store.py` | Day progress JSON + bookmarks SQLite helpers |
| `backend/bible/router.py` | PDF + heartbeat + bookmarks + state |
| `backend/behavior/distraction_gate.py` | Bank + unlimited logic |
| `backend/behavior/tracker_service.py` | Drain bank; ignore pause when locked |
| `src/pages/bible/BibleReaderPage.tsx` | Reader UI |
| `src/plugins/bible_plugin.tsx` | Nav + route |
| `src/api/bibleClient.ts` | API client |

## Tasks

1. Backend bible module + wire router  
2. Gate + tracker drain/harden  
3. Frontend reader + bookmarks  
4. Smoke: heartbeat → bank; gate fields present  
