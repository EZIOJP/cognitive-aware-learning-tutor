# Adaptive Focus — native Zepp OS Pomodoro (standalone)

**Date:** 2026-07-18  
**Status:** Approved  
**Scope:** Standalone Amazfit Mini Program only — **not** wired to CALT

## Goal

Watch-native stress/HRV-aware Pomodoro that:

- Keeps running with **screen off** (App Service)
- Detects **ZONE** (extend once), **FATIGUE** (shorten / smart break), **SPIKE** (breath interrupt)
- Treats **typing / hand micro-motion** as focus-compatible, not walk/fatigue
- Smart break lengths by ending state

## Architecture

```text
Device App (UI + Accel when raised)
        ↕ local storage session
App Service (continuous): Time/min + Stress + HR + Step
Settings App (optional): durations, lock classic, sensitivity
```

**Constraint:** App Service cannot use Accelerometer/Gyro. Motion typing vs walk runs when the Device App is awake; screen-off adapt uses Step + Stress + HR only.

## Classifier

**Motion** (Device App): `STILL` | `TYPING` | `FIDGET` | `WALK`  
**Autonomic** (always): `CALM` | `ENGAGED` | `LOADED` | `SPIKE`

Combine → Pomodoro action (see product design in conversation). Caps: base 25m, +5m extend once, max ~45m.

## Package

`packages/adaptive-focus/` — Zeus / Zepp OS 3+ Mini Program
