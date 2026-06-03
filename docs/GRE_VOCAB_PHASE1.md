# GRE Vocabulary — Phase 1 complete

Phase 1 delivers one coherent study loop with server-backed progress when signed in.

## Study loop

```text
GRE hub → Cycle Manager → Read (group) → Quiz → Report → Low-mastery prompt → repeat (max 5)
         ↘ Read modes (all / low / due / …) — same progress API when logged in
```

## Backend (`/api/vocab`)

| Endpoint | Purpose |
|----------|---------|
| `GET /groups/detailed/` | Group stats (`notStarted` = `times_asked === 0`) |
| `GET /words/by-criteria/` | Read lists (`group`, `mastery_min/max`, `due_for_review`, `word_ids`) |
| `POST /progress/{id}/read` | Save read/swipe progress |
| `POST /quiz/adaptive/*` | Cycle quiz (404 on bad session) |
| `GET /progress/summary` | Hub + cycle dashboard metadata |
| `GET/POST /words/export/*` | Full + per-group export (fixed `db` on import JSON + exports) |
| `POST /admin/users/*/reset-progress` | Admin reset workflows |

## Frontend

- **ReadMode** — API criteria when logged in; offline fallback with `words.json`
- **Cycle read step** — calls `markWordRead` on advance (syncs server)
- **GreVocabPage** — loading, error + retry, sign-in banner, admin link
- **CycleDashboard** — empty groups state
- **AdminPanelPage** — per-group JSON/CSV export, import error handling

## Verify

1. `run.bat` → login `admin` / `admin123`
2. `/gre-vocab` — stats load; retry if API stopped
3. `/gre-vocab/read/low-mastery` — list + advance saves progress
4. `/gre-vocab/cycle` — full group cycle + low-mastery loop
5. `/admin` — export group 1 JSON; import JSON; reset user progress
