# Adaptive Focus (standalone Zepp Mini Program)

Stress / HR–aware Pomodoro that runs **entirely on the watch** (Zepp OS 3+ / your OS 5).  
**Not connected to CALT.** Separate from `packages/calt-zepp`.

## Features

- Focus timer with **screen-off** continuation via **App Service**
- States: **ZONE** (optional +5m extend), **FATIGUE** (early smart break), **SPIKE** (breath break)
- **Typing-aware** motion when the dial is awake (Accel + Step): typing ≠ walk ≠ fatigue
- Smart break lengths by ending phase
- Settings on phone: focus length, classic lock, sensitivity
- Haptics on extend / spike

## Install (Zeus)

**With CALT Sync (both apps):**

```bat
packages\sideload-both-watch-apps.bat
```

**Bridge auto-install (if Scan has no options):**

```bat
packages\sideload-both-bridge.bat
```

**This app only:**

```bat
packages\adaptive-focus\sideload.bat
```

Or:

```bash
cd packages/adaptive-focus
zeus login
zeus preview -t "480x480-t-rex-3"
```

`-t` skips the interactive device menu.

## How sensing works

| When | Sensors | Role |
|------|---------|------|
| Screen off (App Service) | Stress, HR, Step, Time/min | Autonomic adapt + walk via steps |
| Screen on (Device App) | + Accel low-rate | STILL / TYPING / FIDGET / WALK |

Typing = micro-motion + almost no steps → still eligible for **ZONE**.

## Caps (mind-safe)

- Base focus default **25m**
- One **+5m** extend in ZONE (max **45m**)
- Classic lock disables all adapts

## Files

- `page/home.js` — timer UI + Accel
- `page/end.js` — smart break / breathe
- `app-service/focus.js` — screen-off ticks
- `shared/classifier.js` — motion + autonomic + phase
- `shared/session.js` — session state in `localStorage`
- `setting/index.js` — phone settings

## Note on appId

`appId` is `1088802`. If Zeus rejects it, change to a free ID from your Zepp developer account.
