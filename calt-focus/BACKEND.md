# CALT Focus — Backend (BE)

Native Productivity runtime. **Zero Python required** for SoftLand decide, Arm/kills, Plan SoT, Bible/Journal SoT, Gate `get_mode`.

## Binaries

| Binary | Path | Owns |
|--------|------|------|
| `calt_enforcer.exe` | `native/calt_enforcer/` | SoftLand SoT, gateway pipe, kills, sessions, planner, life content, mirrors |
| `calt_focus.exe` | `native/calt_focus/` | Tray + WebView2 shell; maps `calt.app` / `calt-data.app` / `calt-bible.app` |
| `calt_msg_host.exe` | `native/calt_msg_host/` | Gate native messaging: SoftLand decide + `track_tab` |

Installer copies: `scripts/desktop_tracker/installer/installer_payload/bin/`

## Enforcer (primary BE)

| Path | Why |
|------|-----|
| `native/calt_enforcer/src/main.cpp` | Default DB → `data/productivity/productivity.db` |
| `native/calt_enforcer/src/cmd_gateway.cpp` | Named pipe ops (`softland.*`, `arm.*`, `plan.*`, `journal.*`, `bible.*`) |
| `native/calt_enforcer/src/productivity_store.cpp` | SQLite SoT |
| `native/calt_enforcer/src/life_content.cpp` | Journal + Bible day |
| `native/calt_enforcer/src/plan_gate.cpp` | Plan block → SoftLand |
| `native/calt_enforcer/src/day_rollup.cpp` | Scoring rollup mirror |
| `native/calt_enforcer/src/softland_*.cpp` | Tick / publish mirrors |
| `native/calt_enforcer/src/policy_db.cpp` | Arm policy mirror |

## Focus shell

| Path | Why |
|------|-----|
| `native/calt_focus/src/app.cpp` | Launch, enforcer ensure, no auto Study `:8000` |
| `native/calt_focus/src/tray_icon.cpp` | Productivity tray; Study under Advanced |
| `native/calt_focus/src/paths.cpp` | `data/productivity/behavior` + `bible` |
| `native/calt_focus/src/webview_host.cpp` | Virtual hosts + FE bridge |
| `native/calt_focus/src/enforcer_cmd.cpp` | Pipe from WebView2 |
| `native/calt_focus/README.md` | Shell docs |

## Msg-host / Gate

| Path | Why |
|------|-----|
| `native/calt_msg_host/src/softland_decide.cpp` | Reads `data/productivity/behavior/softland_policy.json` |
| `native/calt_msg_host/src/track_tab.cpp` | Sessions → productivity DB |
| `calt-gate-extension/**` | Browser Gate (native messaging) |
| `selftracker-extension/**` | Browser track (opt-in) |

## Data / scripts

| Path | Why |
|------|-----|
| `data/productivity/` | Runtime SoT + mirrors (gitignored) |
| `scripts/desktop_tracker/run/migrate_productivity_data.py` | One-shot migrate from Study tree |
| `scripts/desktop_tracker/run/smoke_*.ps1` | Gateway smokes |
| `scripts/desktop_tracker/run/run_calt_desktop.bat` | Launch Focus |
| `scripts/desktop_tracker/build/build_native_*.bat` | Native builds |

## Study Python (compat readers only — not SoftLand brain)

| Path | Why |
|------|-----|
| `backend/paths.py` | `BEHAVIOR_DIR` / `PRODUCTIVITY_DB` / `BIBLE_DATA_DIR` |
| `backend/behavior/enforcer_files.py` | Read mirrors |
| `backend/behavior/softland_policy.py` | Legacy dual-read |
| `backend/behavior/day_rollup.py` | Read rollup |
| `backend/main.py` | Bible/Journal routers **unmounted** |

## Out of BE review scope

`backend/vocab`, math, notes, quiz, EEG, LLM routers — Study content only.
