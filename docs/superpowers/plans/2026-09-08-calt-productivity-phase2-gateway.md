# Phase 2 Productivity Gateway Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Make `calt_enforcer` the only SoftLand/Arm mutator (SQLite SoT + command IPC + clock tick), publish JSON mirrors for `get_mode`/UI, remove Gate SoftLand HTTP fallback, and let Focus issue commands without `:8000`.

**Architecture:** Enforcer owns gateway + tick. SQLite tables in `data/vocab_app.db` (same WAL as sessions). Atomic publish to `softland_policy.json` / `enforcer_policy.json`. Focus → named pipe. msg_host stays read-only decide + track_tab.

**Tech Stack:** C++17, SQLite amalgamation (existing), Win32 named pipes, WebView2 host messages, Gate JS workers.

**Spec:** [docs/superpowers/specs/2026-09-08-calt-productivity-phase2-gateway-design.md](../specs/2026-09-08-calt-productivity-phase2-gateway-design.md)

## Global Constraints

- SoftLand ON ≠ Arm; SoftLand commands never set `hard_block_armed`
- Three exes only — gateway lives **inside** `calt_enforcer`
- Focus control-only — no in-process policy apply
- msg_host ephemeral — no durable write authority / no SoftLand tick
- JSON = hot-read mirror only after cutover
- WAL + `sqlite3_busy_timeout` on all SQLite writers
- No Cold Turkey code
- Commits only when user asks

---

## File map

| File | Responsibility |
|------|----------------|
| `native/calt_enforcer/src/productivity_store.h/.cpp` | Open DB, migrate DDL, import JSON→SQLite, CRUD SoftLand row |
| `native/calt_enforcer/src/softland_publish.h/.cpp` | Build + atomic-write `softland_policy.json` mirror from SoT |
| `native/calt_enforcer/src/softland_tick.h/.cpp` | Expire free/incubation; apply due `pending_changes` |
| `native/calt_enforcer/src/cmd_gateway.h/.cpp` | Named pipe server; parse `op` JSON; dispatch |
| `native/calt_enforcer/src/win_service.cpp` | Call tick + PollGateway each loop; init store on start |
| `native/calt_enforcer/CMakeLists.txt` | Add new sources |
| `native/calt_focus/src/enforcer_cmd.h/.cpp` | Named pipe client |
| `native/calt_focus/src/webview_host.*` | `chrome.webview.postMessage` → enforcer_cmd |
| `src/.../FocusControlPanel.tsx` (or thin helper) | Prefer enforcer commands when in Focus shell |
| `calt-gate-extension/background.js` (+ rebuild workers) | Prod P4: SoftLand HTTP fallback off by default |
| `backend/behavior/softland_policy.py` / `reward_days.py` | Dual-write note / later IPC; keep working during cutover |

---

### Task 1: Productivity SQLite store + JSON import

**Files:**
- Create: `native/calt_enforcer/src/productivity_store.h`
- Create: `native/calt_enforcer/src/productivity_store.cpp`
- Modify: `native/calt_enforcer/CMakeLists.txt`

**Interfaces:**
- Produces: `bool ProductivityStoreOpen(const std::wstring& dbPath);` `bool ProductivityMigrateAndImport(const std::wstring& softlandJsonPath);` `bool ProductivityLoadSoftland(ProductivitySoftland& out);` `bool ProductivitySaveSoftland(const ProductivitySoftland& in);` `unsigned ProductivityBumpSeq();`

- [x] **Step 1:** Add `productivity_store.h` with struct matching SoftLand fields (enabled, site_rules JSON strings, runtime clocks, ledger seconds, etc.) and table DDL constants for `productivity_softland`, `productivity_ledger`, `productivity_pending_changes`, `productivity_gateway_meta`.

- [x] **Step 2:** Implement open with `PRAGMA journal_mode=WAL;` + `sqlite3_busy_timeout(db, 5000);` (same pattern as `session_db.cpp` / `track_tab.cpp`).

- [x] **Step 3:** Create tables if missing; if softland row absent and `softland_policy.json` exists, parse minimally (reuse simple JsonBoolNear/JsonStringNear style from `focus_watchdog.cpp` / msg_host) and INSERT.

- [x] **Step 4:** Build enforcer; smoke: start once, confirm tables exist via `sqlite3` CLI or Python.

- [x] **Step 5:** Manual verify — no commit unless user asks.

---

### Task 2: SoftLand mirror publish

**Files:**
- Create: `native/calt_enforcer/src/softland_publish.h`
- Create: `native/calt_enforcer/src/softland_publish.cpp`
- Modify: `CMakeLists.txt`

**Interfaces:**
- Consumes: `ProductivityLoadSoftland`
- Produces: `bool PublishSoftlandMirror(const std::wstring& behaviorDir, const ProductivitySoftland& s);` (temp file + `MoveFileEx` replace)

- [x] **Step 1:** Serialize SoftLand struct to JSON matching existing `softland_policy.json` shape (`schema_version`, `site_rules`, `runtime`, `goals`, `mode_flags`).

- [x] **Step 2:** Write `softland_policy.json.tmp` then replace.

- [x] **Step 3:** Call publish after successful import in Task 1 path (idempotent).

- [x] **Step 4:** Smoke: change `earned_ledger_seconds` in DB → publish → file updates.

---

### Task 3: SoftLand clock tick + pending apply

**Files:**
- Create: `native/calt_enforcer/src/softland_tick.h`
- Create: `native/calt_enforcer/src/softland_tick.cpp`
- Modify: `native/calt_enforcer/src/win_service.cpp` (after Focus watchdog or before)

**Interfaces:**
- Produces: `bool TickSoftlandClocks(const std::wstring& dbPath, const std::wstring& behaviorDir);` returns true if mirrors republished

- [x] **Step 1:** Compare `incubation_until` / `free_until` to local now; clear expired fields; if free expired clear `reward_day_active` when tied to that window.

- [x] **Step 2:** SELECT pending where `status='pending' AND apply_after <= now`; apply supported ops (start with `softland.set_enabled`); mark applied.

- [x] **Step 3:** On any change: SaveSoftland + PublishSoftlandMirror + bump seq; mirror `incubation_active` into enforcer_policy if that field is still used for kills.

- [x] **Step 4:** Wire into `RunEnforcerLoop` each poll.

- [x] **Step 5:** Smoke with past `incubation_until` in DB → after one tick, cleared in DB + mirror.

---

### Task 4: Named pipe command gateway

**Files:**
- Create: `native/calt_enforcer/src/cmd_gateway.h`
- Create: `native/calt_enforcer/src/cmd_gateway.cpp`
- Modify: `win_service.cpp`, `CMakeLists.txt`

**Interfaces:**
- Pipe name: `\\\\.\\pipe\\calt_enforcer_cmd`
- Message: length-prefixed UTF-8 JSON `{ "op", "v", "id", "payload" }`
- Produces: `void CmdGatewayInit();` `void CmdGatewayPoll();` (non-blocking accept/read one cmd per poll) `void CmdGatewayShutdown();`

- [x] **Step 1:** Create pipe with `PIPE_TYPE_MESSAGE | PIPE_READMODE_MESSAGE | PIPE_NOWAIT` or overlapped; handle one client command per `CmdGatewayPoll`.

- [x] **Step 2:** Dispatch v1 ops: `softland.set_enabled`, `softland.spend_free`, `softland.set_incubation`, `arm.set` (write/publish enforcer_policy via existing policy writers), `status.snapshot`.

- [x] **Step 3:** Reply `{ ok, id, gateway_seq, as_of }` or `{ ok:false, error }`.

- [x] **Step 4:** Smoke with a tiny PowerShell/`python` pipe client setting SoftLand enabled.

---

### Task 5: Focus enforcer command client + WebView bridge

**Files:**
- Create: `native/calt_focus/src/enforcer_cmd.h/.cpp`
- Modify: `native/calt_focus/src/webview_host.cpp` (WebMessageReceived)
- Modify: `native/calt_focus/CMakeLists.txt`
- Modify: Focus React (`FocusControlPanel.tsx` or `window.chrome.webview.postMessage` helper)

**Interfaces:**
- Produces: `bool EnforcerSendCommand(const std::string& jsonReq, std::string& jsonResp);`
- Web message: `{ type: "enforcer_cmd", op, payload }` → reply via `PostWebMessageAsJson`

- [x] **Step 1:** Implement pipe client connect/send/recv with short timeout.

- [x] **Step 2:** Hook WebView2 `add_WebMessageReceived`; forward enforcer_cmd; post result back.

- [x] **Step 3:** In Focus UI, SoftLand toggle / Arm prefer `enforcer_cmd` when `window.chrome?.webview` present; keep HTTP as fallback only outside Focus shell.

- [x] **Step 4:** Smoke: SoftLand toggle in Focus with API stopped → mirror updates.

---

### Task 6: Prod P4 — Gate SoftLand HTTP fallback off

**Files:**
- Modify: `calt-gate-extension/background.js` (and SelfTracker if duplicated)
- Run: `scripts/build_extension_workers.ps1`

**Interfaces:**
- Default: if native fails → **do not** SoftLand via HTTP; fail closed or allow only if SoftLand mirror says off (prefer: treat as block/study fail-closed when SoftLand was on — match Phase 1 missing-policy spirit for “host dead while SoftLand expected�?)
- Keep `caltSoftlandHttpFallback=true` as explicit debug opt-in only

- [x] **Step 1:** Invert default: HTTP SoftLand path only when flag true.

- [x] **Step 2:** Rebuild workers; reload extensions.

- [x] **Step 3:** Smoke: stop msg-host registration briefly — confirm no Python SoftLand brain path used (API can be up; still must not SoftLand via distraction-gate for mode).

---

### Task 7: Python dual-write / cutover notes + architecture table

**Files:**
- Modify: `backend/behavior/softland_policy.py` or `reward_days.py` — after patch JSON, also best-effort pipe command or document “restart enforcer imports on next start�?
- Modify: `docs/superpowers/exports/2026-09-08-productivity-settings-architecture-note.md` § data availability → SoftLand/Arm/Now **native-safe** for §5 commands
- Modify: spec status → Implementation in progress / Done when exit criteria met

- [x] **Step 1:** Prefer: reward-day / patch_softland still write JSON; enforcer import-on-start + tick republish from SQLite once SoT wins — OR send `softland.set_reward_day` via pipe from a small Python helper. Pick one in-task; default = **import-if-SQLite-stale** on enforcer start comparing `updated_at`.

- [x] **Step 2:** Update architecture note availability rows.

- [x] **Step 3:** Full exit-criteria smoke from spec §9.

---

### Task 8: Verification gate (before Figma)

- [x] SoftLand enable + Arm with uvicorn stopped  
- [x] Spend-free / incubation via Focus command; tick clears past `until`  
- [x] Ledger as-of without Python  
- [x] Gate SoftLand native-only; locked why/until still works  
- [x] No fourth exe  

**How these were verified (2026-09-08):** every command was driven through the
real named pipe with `scripts\desktop_tracker\run\gateway_cmd.ps1` and the real
Gate stdio framing with `msg_host_cmd.ps1`, with uvicorn stopped for the
offline runs. Both binaries were rebuilt and swapped into the live
`native\*\build\` paths and are the running processes.

Still owner-only (a human has to click it): saving a site list / schedule and
arming **from the Focus window**, confirming the "via enforcer gateway" hints.
Code path and pipe path are both proven; the click is not.

---

## Execution order

1 → 2 → 3 → 4 → 5 → 6 → 7 → 8  

Do not start Settings Figma until Task 8 is green.
