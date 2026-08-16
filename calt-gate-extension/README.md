# CALT Gate (blocker) — v1.0.2

Light **site gate** extension — browser-native DNR only.

## Pair with

`selftracker-extension` **v1.5.23+** (bundled `service_worker.js`).

## Load in Edge

1. `edge://extensions` → Developer mode  
2. **Remove** old CALT Gate / SelfTracker if you saw `importScripts` / NetworkError  
3. Load unpacked → `calt-gate-extension`  
4. Load unpacked → `selftracker-extension`  

After editing JS: `powershell -File scripts\build_extension_workers.ps1` then Reload.

## Requires

CALT backend: `run.bat` → `http://127.0.0.1:8000`

