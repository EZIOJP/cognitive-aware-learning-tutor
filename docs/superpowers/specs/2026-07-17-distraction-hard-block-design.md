# Distraction hard-block until daily productive goal

**Date:** 2026-07-17  
**Status:** Approved for implementation (v1)  
**Out of scope:** Browser tab closing, Cold Turkey integration, soft-minimize-only mode. User handles streaming sites via Cold Turkey.

## Problem

Desktop tracker only **scores** games as unproductive. User wants OS-level **hard kill** of games (and a custom app list) until today’s productive minutes hit a daily goal, then unlock for the rest of the local day.

## Goals

1. Toggle: hard-block distractions until daily productive goal.
2. Default: block **Gaming** category apps + seed common game/launcher exes.
3. Custom: user-editable `hard_block_exes` list (any `.exe`).
4. Unlock when `productive_minutes_today >= daily_goal_minutes`; reset at local midnight.
5. Enforcement lives in the **desktop tracker** poll loop (same process that already sees foreground exe + pid).

## Non-goals (v1)

- Killing whole browsers for YouTube/Netflix (Cold Turkey).
- Multiple competing blockers inside CALT.
- Weekly goals for unlock.
- Hosts-file / firewall rewriting.

## Design

### Data (extend `productivity_policies`)

| Field | Type | Default | Meaning |
|-------|------|---------|---------|
| `hard_block_enabled` | bool | false | Master toggle |
| `daily_goal_minutes` | int | 240 | Unlock threshold (productive minutes) |
| `hard_block_gaming` | bool | true | Also block anything classified `Gaming` |
| `hard_block_exes` | JSON string[] | seed list | Extra exe names (case-insensitive) |

Scoring `blocked_categories` stays separate (stats only). Hard-block uses its own lists.

### Gate computation

`GET /api/behavior/distraction-gate` (and same logic in-process for tracker):

```text
enabled = hard_block_enabled
productive = today's productive_minutes (same scoring as adherence)
goal = daily_goal_minutes
unlocked = (not enabled) OR (productive >= goal)
locked = enabled AND NOT unlocked
```

### Tracker enforcement

On each poll (or every N polls): if `locked` and foreground exe matches hard-block rules → `terminate`/`kill` that pid (never protect-list: explorer, dwm, python, tracker itself). Toast/log: “Blocked until focus goal.”

### UI

Productivity Policy panel: toggle, goal minutes, gaming checkbox, custom exe list editor, live gate status (locked / X min left / unlocked).

## Safety

- Protect system/shell/self processes.
- Default toggle **off** so existing users are unchanged until they enable.
- Mis-add `chrome.exe` → whole browser dies; UI warns: prefer Cold Turkey for sites.

## Success criteria

- With toggle on and goal unmet, launching a seeded game exe is killed within one poll interval.
- After productive minutes ≥ goal, same exe is left alone until midnight.
- Custom exe on the list is blocked the same way.
- Tests cover match rules + unlock math; API returns gate payload.

---

## Addendum (2026-08-04) — SelfTracker browser policy

Desktop hard-block remains **games/exe only**. Site control is via SelfTracker extensions polling the same gate:

- Payload: `browser` (+ `morning.bible_url` / `redirect_url`) from `backend/behavior/browser_gate_policy.py`
- Allowlist wins (Colab, Scaler, GitHub, localhost, docs, …)
- Always block porn while Armed or morning locked
- Block watch sites (YouTube, Netflix, …) while Armed or morning locked (`block_watch_sites`)
- Morning `bible` / `plan` soft-land to SPA URLs; Armed distractions → `locked.html`
- **Keywords (v1.3):** case-insensitive blocklist on URL path/query + page/window title only (~0 cost; not keylogging). Allowlist still wins. Synced via `browser.block_keywords_list`.
- **Allowed browsers while enforcing:** Zen + Edge only. Other browsers → soft-lock card + canned voice (never kill Cursor/IDEs; browsers stay in `PROTECTED_EXES`).
- **NSFW screen (optional, light):** every ~60s CPU screenshot when Armed — see `backend/behavior/nsfw_screen_scan.py` + `data/nsfw/README.md`. **Not** continuous GPU video.
- **Voice alerts:** canned Jarvis lines from `voice_agent/block_dialogues.py` (random/rotate). Rate-limited (~45s). No LLM/`call_brain` for YouTube/porn blocks.

### Light routine (intervals)

| Path | Interval | Cost |
|------|----------|------|
| Extension keyword/URL check | On navigation / tab focus only | String match |
| Extension gate poll (active) | ~4s opportunistic GET | Tiny JSON |
| Extension gate poll (idle) | 1 min alarm backup | Tiny JSON |
| NSFW screen scan | ~60s when Armed | Brief CPU spike, ~0 VRAM |
| Speak alert | Max ~1 / 45s | edge-tts ephemeral |

### Deferred explicitly

- Keylogging / keyboard content filters
- Continuous webcam or frame-by-frame GPU NSFW
- LLM-generated narration for routine blocks
