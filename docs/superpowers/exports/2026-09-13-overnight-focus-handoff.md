# Overnight Focus polish — handoff (2026-09-13)

Worked while you slept on **live Settings + unlock gateway + shell polish**. Enforcer was started; `dist-focus` rebuilt twice.

## Shipped this session

### Settings (Make shell — live, not demo)
- `MakeSettingsApp.tsx` rewritten: Overview / Rules / Unlock / Productive / Tools compose **real** panels (SoftLand, schedules, app kills, device lock, FocusControlPanel, scoring).
- Mounted from `ProductivitySettingsTab` (replaces hub as the Focus Settings door).
- Legacy `?section=now|sites|apps|filters` map into Make sections.

### Backend wiring (Focus offline)
- `requestRewardDay` → `reward.claim` (gateway)
- `requestBibleDayPass` → `day.grant_pass` (gateway)
- `fetchDistractionGate` / `fetchProductivityPolicy` / `saveProductivityPolicy` prefer Focus mirrors + pipe
- Unlock UI: day-pass button + reward; stale “until P5a” copy removed from hub

### Goals Blocker (prior + kept)
- Unified Sites tags Allow|Focus|Always; Apps = Arm list; SoftLand/Armed chips

### Shell
- Journal added to Focus sidebar
- Bible/Journal nav taxonomy → Focus
- DayLoopLanding uses `focusDataUrl` (not hardcoded `/calt-data/`)
- FocusControlPanel free-window copy no longer says “needs API”

## Verified on machine
- `npm run build:focus` — green
- Started `calt_enforcer` (console); SoftLand relaunch counted Focus
- Gateway: `status.snapshot`, `day.status`, `day.loop_snapshot`, `reward.status`, `softland.patch_site_rules` OK

## When you wake
1. Tray **Reload UI** once more (Goals copy + dashboard native path landed after first restart)
2. Settings → Overview / Rules / Unlock — SoftLand ≠ Arm still teaching
3. Unlock: reward / day pass need enforcer (console enforcer was left running)
4. SoftLand is currently **off** on this machine (`softland_enabled: false`) — turn on intentionally; disable later requires typing UNLOCK
5. Full notes: this file + spec `2026-09-13-focus-overnight-live-settings-design.md`

## Still soft / optional next
- Productive category score **writes** still Study-API (reads classify_rules mirror)
- Watch sync / Google Calendar remain Advanced sidecar
- Make visual tokens already melt-in; deeper shadcn rebuild deferred
- Rebuild `calt_enforcer` from tree only if you need C++ changes (none required for this FE pass)

## Key files
- `src/components/productivity/settings/make/MakeSettingsApp.tsx`
- `src/components/productivity/ProductivitySettingsTab.tsx`
- `src/api/bibleClient.ts`, `src/api/behaviorClient.ts`
- `src/components/productivity/BlockerPanel.tsx`, `SoftLandSiteRulesPanel.tsx`
- Spec: `docs/superpowers/specs/2026-09-13-focus-overnight-live-settings-design.md`
