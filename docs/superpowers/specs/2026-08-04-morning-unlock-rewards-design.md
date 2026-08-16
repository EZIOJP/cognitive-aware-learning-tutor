# Morning unlock chain + rewards

**Date:** 2026-08-04  
**Status:** Implementing  
**Extends:** Bible chapter goal + `MORNING_GATE` (bible → plan → open)

## Day sequence (user-facing)

1. **Locked** — SPA redirects to `/bible` until today’s chapter goal is met.  
2. **Bible done** → grant **Bible +10** → unlock plan step (`/productivity`).  
3. **Confirm today’s plan/goals** (compulsory) → grant **Plan +10** → day open.  
4. Same pattern every local calendar day.

Desktop game hard-block remains separate (study goal + chapter for unlimited games).

## Today-only Bible UX (2026-08-04)

- Morning `/bible` shows **only today’s assigned chapter** (no book list, chapter grid, or browse).  
- Assignment: sequential Genesis→Revelation from WEB plan; bootstrap from furthest lifetime `completed_chapters`; stable on `day_{user}_{date}.json` (`assigned_book` / `assigned_chapter`); next calendar day uses `plan_cursor`.  
- API: `GET /api/bible/v2/today`; tick only accepts today’s chapter. Gate unchanged: ≥1 chapter in `chapters_completed` still unlocks.

## Unified “bible done”

- Source of truth: `data/bible/day_{user}_{date}.json` → `chapters_completed` (≥1 = goal met).  
- **Web** (`POST /api/bible/v2/chapters/tick` / verse heartbeat) and **tracker embed** (tick / auto chapter) must both write that list.  
- `day_pass` does **not** skip morning Bible.

## Rewards (minimal)

- Store: `data/morning_rewards.json` keyed by `user_id:YYYY-MM-DD`.  
- Fixed awards: `bible` = 10, `plan` = 10. Idempotent on grant.  
- Exposed on `morning.rewards` in distraction-gate (granted flags + total).  
- No full game economy.

## Compulsory plan

- After Bible: `morning.next = "plan"`; only `/bible`, `/productivity`, `/login` allowed.  
- `POST /api/behavior/morning-plan/confirm` requires Bible done; then marks confirm + grants plan reward.

## Disable

- `MORNING_GATE=0` (or `false` / `off` / `no`) → `morning.next = "open"` (rewards still grant if steps completed).

## Voice (canned, 2026-08-04)

- Once/day **morning brief** (no LLM): greet → bible nudge or plan brief → optional yesterday productivity one-liner from desktop CSV.
- Triggers: tracker gate refresh after 5am if `morning.next` is bible/plan; first voice chat open; chat `/brief` forces.
- Flag: `data/voice_agent/morning_briefed_{date}.json`. Bible tick / plan confirm speak praise lines from `dialogues.py`.

## Out of scope

Music player, smart alarm, watch verse.
