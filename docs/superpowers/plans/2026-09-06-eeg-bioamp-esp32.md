# EEG BioAmp ESP32 Implementation Plan

> **For agentic workers:** Implement tasks in order. Soft-fail and timestamped SD logging are mandatory.

**Goal:** Mature BioAmp firmware + soft-fail EEG status so CALT stays reliable with or without the headset.

**Architecture:** SD-first CSV on device → optional UDP float32 → `backend/eeg` FFT bands → `/ws/eeg` when plugin on.

## File map

| Path | Role |
|------|------|
| `hardware/eeg/` | PlatformIO sketch + `secrets.h.example` |
| `scripts/flash_eeg.bat` | One-click build/upload |
| `backend/eeg/service.py` | Soft status + recv timestamp |
| `backend/eeg/router.py` | `GET /api/eeg/status` |
| `docs/firmware/EEG_ESP32.md` | User flash guide |

## Tasks

### Task 1: Firmware package
- PlatformIO `platformio.ini` for esp32-s3
- `src/main.cpp`: 250 Hz, NTP, SD CSV, UDP, soft-fail
- `secrets.h.example`

### Task 2: Flash helper
- `scripts/flash_eeg.bat` (pio install hint + upload)

### Task 3: Backend soft status
- Track `last_packet_ms`, status enum
- Health/info endpoint; no hard fail

### Task 4: Docs
- [x] Update `docs/firmware/EEG_ESP32.md`

**Status (2026-09-07):** Firmware package completed (SPI pins, NTP retry, serial cmds, auto-secrets, fixed CSV buffer). Soft-fail + flash docs remain. Physical flash requires owner USB/COM.

