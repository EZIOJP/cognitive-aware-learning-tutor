# Focus UX polish — active blocks, Goals blockers, design host

**Date:** 2026-09-11  
**Status:** Implemented (design host + active cards + Goals SoftLand lists)  
**Product:** calt_focus sole Productivity door

## Goals

1. **Design host:** `npm run dev:focus` → `http://127.0.0.1:5180/` (Focus shell; avoids `:5174` static clash). Edit React in Cursor; hot-reload without rebuilding `dist-focus` / native shell.
2. **Dashboard:** Active (+ next) plan-block cards under GlanceBar — title, category, time left, SoftLand mode hint, Start / Complete / Roll actions via gateway.
3. **Goals tab:** Edit SoftLand allow / watch / block lists in-place (reuse SoftLand rules UI + gateway write) so “blockers I’m choosing” live next to focus goals.
4. **Theme:** Reuse existing gloss panels / emerald accents — no new design system.
5. **QoL:** Focus-preview banner on `:5174`; empty states when no active block; soft errors when enforcer down.

## Out of scope

- Native LLM (3b), Google OAuth port, wearables into C++.
- Full Calendar visual redesign.

## Exit

- `dev:focus` documented; active cards work with enforcer up and Study `:8000` stopped; Goals can save SoftLand lists via pipe.
