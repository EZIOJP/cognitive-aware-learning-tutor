# EEG — ESP32-S3 + BioAmp EXG Pill (flash-ready)

Backend stays reliable without the headset. Firmware lives under `hardware/eeg/`.

## Flash checklist (full path)

1. **Plug ESP32-S3 USB** — Device Manager must show a COM port.
2. **Install PlatformIO** — Cursor extension **PlatformIO IDE**, or `pip install platformio`.
3. **Edit secrets** — `hardware/eeg/src/secrets.h` (created automatically on first flash/build):
   - `WIFI_SSID` / `WIFI_PASSWORD` (2.4 GHz)
   - `UDP_TARGET_IP` = your PC LAN IP (`ipconfig`)
   - Leave **`SELF_TEST_MODE 1`** for first flash (synthetic snaps, no BioAmp)
   - Optional SD SPI: `SD_CS_PIN` / `SD_SCK_PIN` / `SD_MISO_PIN` / `SD_MOSI_PIN`
4. **Flash:**

```bat
scripts\flash_eeg.bat
```

Or from `hardware/eeg`: `pio run -t upload` (creates `src/secrets.h` from the example if missing).

5. **On the PC** (while board is powered):

```bat
.venv\Scripts\python.exe scripts\eeg_udp_listen.py
```

You should see lines like:

```text
SNAP #1  v=2.850V  from=192.168.x.x  packets=…  t=03:05:12
```

Serial monitor also prints `[eeg] SELF_TEST SNAP`. Commands: `s` status, `c` WiFi, `n` NTP, `r` restart, `h` help.

6. When that works: set `SELF_TEST_MODE` to `0`, wire BioAmp EXG Pill → `EEG_PIN` (default GPIO 4), re-flash.
7. Optional live hub: `.env` → `EEG_ENABLED=1`, restart API.

## SELF_TEST vs live

| Mode | `SELF_TEST_MODE` | What happens |
|------|------------------|--------------|
| Bring-up | `1` (default) | ~2s snap pulses → UDP + SD — proves WiFi/flash |
| Real EEG | `0` | ADC from BioAmp EXG Pill |

## SD dump

`/DSC_YYYYMMDD_HHMMSS.csv` → `unix_ms,boot_ms,voltage_v,raw_adc,wifi,ntp`

## Backend (optional after UDP works)

```env
EEG_ENABLED=1
```

`GET /api/eeg/status` → `offline|warming|streaming|disabled` (never fails stack health).

`GET /health` includes `"eeg": { "ok": true, ... }` even when the board is unplugged.

## Soft-fail behavior

| Missing | Firmware | Backend |
|---------|----------|---------|
| WiFi | Samples + SD continue; UDP off; retries | status `offline` |
| SD | Samples + UDP continue | unchanged |
| Board unplugged | — | status `offline`, `/health` still ok |

## Wiring (live mode)

```text
BioAmp OUT → GPIO 4 (EEG_PIN)
BioAmp GND → GND
BioAmp VCC → 3V3 (confirm Pill rating)

SD (optional, ESP32-S3 DevKitC defaults):
  CS→5  SCK→12  MISO→13  MOSI→11  VCC→3V3  GND→GND
```

## Owner note

Software + firmware package are complete. Physical flash still needs your USB COM port + PlatformIO on the machine with the board.
