# Amazfit T-Rex 3 — Negative Digital Watchface (v1)

> **Canonical copy:** `C:\Users\Lenovo\Desktop\watch_face\docs\2026-07-21-trex3-negative-digital-design.md`  
> Project lives outside this repo.

**Date:** 2026-07-21  
**Status:** Built v1 in `C:\Users\Lenovo\Desktop\watch_face` — Casio negative, no seconds  
**Project root:** `C:\Users\Lenovo\Desktop\watch_face`

## Goal

A calm, real-feeling **digital watch** face: pure black background, large time, and day / date / month. Normal mode and Always-On Display (AOD) look the same. No heavy redraws or widgets.

## Device

| Item | Value |
|------|--------|
| Watch | Amazfit T-Rex 3 |
| Resolution | 480 × 480 round |
| deviceSource | `8716544`, `8716545`, `8716547` |
| Preview asset | 324 × 324 |
| Target API | Zepp OS 3+ / API_LEVEL suitable for T-Rex 3 (≤ 4.0) |

## Visual design

```text
            WED  21  JUL
              14:36
```

- **Background:** `#000000` full screen
- **Time:** large centered `HH:MM` (24-hour in v1), soft white / light grey digits (not neon)
- **Date line (above time):** weekday abbreviation · day-of-month · month abbreviation  
  Example: `WED  21  JUL`
- **No seconds** in v1 (keeps AOD quiet and battery-friendly)
- **No** steps, HR, weather, battery, animations, or second hand in v1
- **AOD:** identical layout and assets; system may dim brightness only

## Behavior

- Update on **minute** boundary (and on wake), not every second
- Bitmap / system digital fonts preferred over custom canvas redraw loops
- Same widget tree for normal + AOD where the platform allows

## Tooling

1. Node.js LTS  
2. Zeus CLI: `npm i @zeppos/zeus-cli -g`  
3. Zepp OS simulator (official) for desktop preview  
4. Real device: `zeus preview` → QR → Zepp app Developer Mode  

## Project layout (to create)

```text
C:\Users\Lenovo\Desktop\watch_face\
  docs\          # this design + notes
  package.json   # Zeus watchface project (after scaffold)
  app.json       # device targets (T-Rex 3)
  assets\        # digit / preview images if needed
  watchface\     # face entry + AOD
```

Exact Zeus scaffold names may differ slightly after `zeus create`; keep T-Rex 3 as the only required device target for v1.

## Out of scope (v1)

- 12-hour AM/PM  
- Seconds  
- Complications (HR, steps, weather)  
- Color themes / tap zones  
- Store listing polish beyond a basic preview image  

## Success criteria

1. Simulator shows black digital face with time + day/date/month  
2. AOD preview matches normal layout  
3. Installable on T-Rex 3 via `zeus preview`  
4. Feels like a normal digital watch: quiet, readable, no flicker or heavy animation  

## Next

After this spec is reviewed: write an implementation plan, then scaffold with Zeus CLI and build v1.
