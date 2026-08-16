# Browser data, sitting, and smart alarm limits (2026-08-04)

Local-first honesty note for CALT desktop tracker, SelfTracker extensions, wearables, and alarms.

## Browser data: tracker vs extension

| Source | What it can see | Good for |
|--------|-----------------|----------|
| **Desktop tracker** | Foreground **window title** (+ exe). For browsers this is usually the active tab title only. | App focus, game hard-block, productivity minutes |
| **SelfTracker extension** (Chromium + Firefox/Zen) | Full **tab list**, active URL/title, optional **history** sample via `tabs` / `history` APIs | Rich browsing telemetry, distraction redirects |

**Not available from the desktop tracker alone:** open tab inventory, full browser history, per-tab URLs behind the focused window.

**v1.4 extensions** lightly POST to `POST /api/behavior/browser-telemetry` (~45s cadence, ~2 min idle backoff):

- Active tab URL + title (query tokens like `token` / `password` stripped)
- Open tab count + top N tabs (domain-preferring)
- Optional recent history **domains** (requires `history` permission)

Logs: `data_logs/DSC_browser_telemetry_YYYY-MM-DD.jsonl` (+ CSV mirror). Existing session stream over WebSocket is unchanged.

Reload unpacked / temporary add-on after upgrade; accept the new history permission if prompted.

## Sitting / stand (wearables)

Zepp / Amazfit mini-program sync already stores **`stand.hours`** (and target). Your live payloads typically include stand, not sitting minutes.

CALT will parse **`sitting_min` / sedentary fields** from activity or a top-level `sitting` object **when present** — we do **not** invent sitting from stand hours. Wearables panel shows Stand, and appends Sitting only if the watch sent it.

## Smart alarm

| Possible now | Deferred |
|--------------|----------|
| Soft **suggested wake** on distraction-gate `morning.suggested_wake` from last sleep end + bible/plan context | Writing a true **Zepp / T-Rex 3 smart alarm** from CALT |
| Morning brief / bible gate as a ritual after wake | Hardware alarm scheduling APIs (device-side only today) |

Stock watch alarms stay on the device. CALT does not fake hardware alarms.

## Reload / restart

1. Restart API (`run.bat` or backend) so distraction-gate includes `browser.mode`.
2. Restart desktop tracker (or wait for keepalive) for tray mode badge / exit PIN.
3. Edge/Chrome: `edge://extensions` → Reload CALT SelfTracker (v1.5).
4. Zen/Firefox: re-Load Temporary Add-on from `selftracker-extension-firefox/manifest.json`.

## Day modes (browser)

| Mode | When | Policy |
|------|------|--------|
| `bible` | morning.next = bible | Strict: CALT bible/login localhost paths only |
| `planning` | morning.next = plan, or planning calendar block | Strict: bible + productivity localhost only |
| `study` | Active study/focus planner block | Goal domains (Colab, GitHub, docs, …); block YT/social/porn/other |
| `free` | Day open, no study block | Porn + adult keywords only |

## Amazfit + Android bridge

Phone Expo Tracker (`packages/calt-android-tracker`) and Zepp Sync 3.2+ use
`GET /api/behavior/day-status` / `GET /api/hub/day-status`. Watch alerts =
Zepp notifications or Android notification mirror — not a full CALT watch APK.
See `docs/superpowers/specs/2026-08-04-amazfit-android-tracker-bridge-design.md`.

## Tracker persistence

```bat
scripts\install_tracker_persistence.bat
```

Uninstall (legitimate):

```bat
REM Optional: TRACKER_PERSIST_PROTECT=0 in .env, restart tracker once
scripts\uninstall_tracker_persistence.bat
```

Tray exit: **Confirm exit…** → type `TRACKER_EXIT_PIN` or `I AM DONE TRACKING`. Closing Tk windows does not stop the service.
