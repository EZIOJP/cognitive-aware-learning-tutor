# EEG BioAmp EXG Pill + ESP32-S3 — design

**Date:** 2026-09-06  
**Status:** Approved for implementation (user: BioAmp EXG Pill; SD-first + soft-fail)

## Goal

Flashable ESP32-S3 firmware that samples BioAmp EXG Pill, logs **timestamped** samples to SD, and best-effort UDP to CALT. Software stack stays reliable when the headset/WiFi/SD is absent.

## Principles

1. **Optional lane** — quiz, planner, desktop never depend on EEG.
2. **SD-first** — local CSV is the durable dump; WiFi is best-effort.
3. **Soft-fail** — missing WiFi / SD / stream → warn + continue; never hard-crash or mark API unhealthy.
4. **Timestamps** — NTP `unix_ms` when WiFi sync succeeds; always include `boot_ms`; backend adds `recv_ms`.

## Hardware

- ESP32-S3 + BioAmp EXG Pill on ADC pin (default GPIO **4** on S3; override in `secrets.h`)
- MicroSD on SPI (CS default GPIO **5**)
- 2.4 GHz WiFi (antenna attached)
- Power: USB / power bank

## Firmware

- 250 Hz sampling
- CSV: `unix_ms,boot_ms,voltage_v,raw_adc`
- UDP: little-endian float32 voltage → laptop `:5005` (matches `backend/eeg/service.py`)
- Config: `secrets.h` (SSID, password, laptop IP, pins)

## Backend

- Default `EEG_ENABLED=0` — no UDP task
- When enabled: status `offline | warming | streaming` from last packet age
- `/health` reports eeg as info only; never fails health because stream is quiet

## Flash path

Agent cannot flash without USB COM port + PlatformIO. User plugs board → `scripts\flash_eeg.bat` or PlatformIO IDE extension.
