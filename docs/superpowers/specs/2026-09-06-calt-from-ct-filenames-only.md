# CT install *names* → CALT roles (no binary reading)

**Source:** Owner listed files under `Desktop\ZXCazsd\` (Cold Turkey Blocker install tree).  
**Allowed:** Infer roles from **filenames only**.  
**Forbidden:** Open / decompile / copy any CT exe/dll/db/web assets into CALT.

## Filename → likely role → CALT equivalent

| CT filename (listed) | Inferred role | CALT owner | Our code / decision |
|----------------------|---------------|------------|---------------------|
| `Cold Turkey Blocker.exe` | Main control UI | Web Dashboard + Desktop Focus | `calt_desktop/dashboard/` — keep web UI, not CT clone |
| `web\` | UI assets (likely embedded web) | Same | Our HTML/JS dashboard |
| `CTServiceInstaller.exe` | Install Windows service | Install script | `scripts/desktop_tracker/install_native_enforcer.ps1` |
| `CTHostInstaller.exe` | Host / helper install | Optional later | Skip unless needed |
| `ServiceHub.Power.exe` / `ServiceHub.Helper.exe` | Background enforcement hub | Native enforcer | `native/calt_enforcer/` (kills + session track) |
| `ServiceTools.dll` | Service helpers | Inside enforcer | Our `win_service.cpp`, `owner_lock.cpp` |
| `CTMsgHostChrome.exe` + `.json` | Browser native-messaging host | CALT Gate extension | `calt-gate-extension/` → polls `:8000` (no CT msg host) |
| `CTMsgHostEdge.exe` + `.json` | Edge messaging | Same | Same extension path |
| `CTMsgHostFirefox.exe` + `.json` | Firefox messaging | Later if needed | Out of scope for now |
| `Microsoft.Data.Sqlite.dll` + SQLitePCL* | Local SQLite | Shared `vocab_app.db` | Python + C++ sqlite amalgamation |
| `Microsoft.Win32.TaskScheduler.dll` | Autostart / recovery tasks | Task Scheduler / service | `sc.exe` create + optional Python fallback scheduler |
| `Microsoft.Toolkit.Uwp.Notifications*` | Toast notifications | Optional | Python/Desktop toasts if we want later |
| `Newtonsoft.Json.dll` | JSON config/IPC | Python json + our minimal C++ JSON parse | Keep |
| `runtimes\` + `System.*.dll` | .NET runtime | N/A | CALT enforcer is **C++**, not .NET — intentional |
| `unins000.exe` | Uninstaller | Later | v2d / simple uninstall script |

## Logic gaps implied by this split (fill with CALT)

| Gap from CT-like layout | Status |
|-------------------------|--------|
| Separate **UI exe** vs **service hub** | UI = Desktop/Web; service = `calt_enforcer` — **done pattern** |
| Browser bridge as **msg host** | We use **extension → HTTP :8000** — different, keep |
| SQLite next to product | We use **one study DB** — keep |
| Installer for service | Script exists; **owner must run Admin** |
| Kill + track in hub | N3 + kill harden — **in our C++** |
| Toasts on block | Optional follow-up (our notify), not CT toolkit |

## Hard rules

1. Do **not** copy `ZXCazsd` into the CALT repo.  
2. Do **not** decompile `Cold Turkey Blocker.exe` / `ServiceHub.*`.  
3. Improve only via public product shape + our Python tracker parity + Win32 APIs.
