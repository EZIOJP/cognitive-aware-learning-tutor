# CALT Focus shell (C++) — tray + WebView2

```text
CT-class split (pattern only, no CT code):
  calt_focus.exe     = tray + WebView2 control UI (this folder)
  calt_enforcer.exe  = OS kills + stay-alive + non-browser track
```

## No Vite every day

Build the UI **once**, then Focus loads pages from disk (`file://…/dist-focus/…`):

```bat
npm run build:focus
scripts\desktop_tracker\run_calt_desktop.bat
```

`run_calt_desktop.bat` auto-runs `build:focus` if `dist-focus\` is missing.

- **UI:** precompiled React in `dist-focus/` (no `npm run dev`, no port 5173)
- **API:** still need `:8000` only for live Arm/Disarm / SoftLand data (tray can start it)
- **Dev fallback:** if `dist-focus` is absent, can use Vite `:5173`

Does **not** kill processes. Tooltip may read `enforcer_status.json`.

## Build native shell

```bat
scripts\desktop_tracker\build_native_focus.bat
```

## Tray

**Run (enforcer + API; prebuilt UI)** · Start API · Start Frontend (optional Vite) ·
Open Calendar · Open Plan · Open Focus · Open Settings · Quit

**Quit rule (Phase 1):** tray Quit is refused while SoftLand is on or hard-block is armed
(balloon explains). SoftLand off + Disarm → Quit stays quit. Killing `calt_focus.exe`
while SoftLand-or-Arm is on causes enforcer relaunch (backoff-capped).

Default window: **Calendar**. Study (notes, GRE, …) stays in the browser webapp.

## Phase 1 boundary (solo pack)

With `:8000` down, **blocks + browser track (`track_tab`) + OS kills** still work via
`calt_msg_host` / `calt_enforcer`. Focus Settings/Arm toggles and live Python "why"
cards still need the API (hybrid / stale-while-down — see architecture note).
Do not overclaim that the whole Focus UI is offline-capable.

## Env

| Var | Purpose |
|-----|---------|
| `CALT_REPO` | Repo root override |
| `CALT_DB` | Locate `data/behavior` |
| `CALT_FOCUS_URL` | Force a URL (skips prebuilt) |
