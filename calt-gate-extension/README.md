# CALT Gate (blocker) — v1.0.7

Browser **SoftLand** (DNR + locked page) for CALT Desktop · Focus.

## Pair with

- `selftracker-extension` **v1.5.26+** (telemetry)
- **CALT Desktop Enforcer** (Windows Task/Service) — app process kills
- **CALT Desktop · Focus** Dashboard — control UI

## Load in Edge

1. `edge://extensions` → Developer mode  
2. Load unpacked → `calt-gate-extension`  
3. Load unpacked → `selftracker-extension`  
4. Reload after JS edits  

After editing JS:

```bat
powershell -File scripts\build_extension_workers.ps1
```

## Requires

CALT backend: `run.bat` → `http://127.0.0.1:8000`

## v2 notes

- Gate JSON includes `incubation` + `desktop` — leisure stays blocked during incubation even if daily goal is met.
- Customize block lists in Desktop; extension polls the same policy brain.
