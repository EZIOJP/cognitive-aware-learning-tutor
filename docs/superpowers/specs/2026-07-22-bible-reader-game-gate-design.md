# Bible reader + game unlock gate

**Date:** 2026-07-22  
**Status:** Approved — implementing  
**Out of scope:** Custom Chromium browser / site blocking (Cold Turkey). Highlights later.

## Goal

Force a Bible habit with an **in-app PDF reader**, then unlock games via a clear bank:

1. **30 min** reading `good-news-bible.pdf` in CALT reader → **30 min** game bank  
2. **Study goal** (productive minutes) **+ 30 min Bible today** → **unlimited games until midnight**  
3. Otherwise games stay hard-blocked; tracker harder to casually disable  

## Bible source

- Canonical file: `data/bible/good-news-bible.pdf`  
- Seeded from `C:\Users\Lenovo\Downloads\good-news-bible.pdf` on first use  

## Reader (FE)

- Route `/bible` — PDF viewer (browser embed), page nav, last page restore  
- Bookmarks: label + page; list + jump  
- Heartbeat every ~20s while tab focused → backend credits Bible minutes  

## Gate (BE + tracker)

| State | Games |
|-------|--------|
| Default + hard-block on | Kill games |
| `game_bank_remaining > 0` | Allow; drain bank while gaming |
| `productive >= goal` AND `bible_minutes >= 30` | Unlimited until local midnight |

## Harden

- Soft pause ignored while hard-block enabled  
- Policy UI: no one-click “turn off hard-block” (confirm phrase)  
- Background process sweep still runs when gate locked  

## APIs

- `GET /api/bible/pdf` — stream PDF  
- `GET/POST /api/bible/state` — last page, today minutes, bank, unlimited  
- `POST /api/bible/heartbeat` — `{ page, focused }`  
- `GET/POST/DELETE /api/bible/bookmarks`  

Distraction-gate payload gains: `bible_minutes`, `game_bank_remaining`, `day_unlimited`.
