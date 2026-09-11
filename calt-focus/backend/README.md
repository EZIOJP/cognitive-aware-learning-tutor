# Focus backend (BE)

C++ Productivity runtime — SoftLand, Arm/kills, planner SoT, Bible/Journal SoT, Gate decide.

| Binary | Folder |
|--------|--------|
| `calt_enforcer.exe` | `calt-focus/backend/calt_enforcer/` |
| `calt_focus.exe` | `calt-focus/backend/calt_focus/` (tray + WebView2) |
| `calt_msg_host.exe` | `calt-focus/backend/calt_msg_host/` |

Build: `scripts/desktop_tracker/build/build_native_*.bat`  
Data: `data/productivity/{productivity.db,behavior/,bible/}` (gitignored)  
Pipe: `\\.\pipe\calt_enforcer_cmd`

## Key sources

- `calt_enforcer/src/cmd_gateway.cpp` — SoftLand / Arm / plan / journal / bible ops
- `calt_enforcer/src/productivity_store.cpp` — SQLite SoT
- `calt_enforcer/src/life_content.cpp` — Journal + Bible day
- `calt_focus/src/tray_icon.cpp` — Productivity tray (Study under Advanced)
- `calt_focus/src/paths.cpp` — productivity data dirs
- `calt_msg_host/src/softland_decide.cpp` — Gate SoftLand decide

Study Python (`backend/` FastAPI) is not the SoftLand brain — optional readers only.
