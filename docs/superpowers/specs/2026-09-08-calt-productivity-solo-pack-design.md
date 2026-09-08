# CALT Productivity — solo tightly packed runtime (design)

**Date:** 2026-09-08  
**Status:** Phase 1 implementation lock  
**Parent:** [2026-09-07-calt-productivity-cpp-product-design.md](./2026-09-07-calt-productivity-cpp-product-design.md)  
**SoftLand store:** [2026-09-07-calt-productivity-softland-state-model.md](./2026-09-07-calt-productivity-softland-state-model.md)

**Phase 1 claim:** SoftLand **decide** + browser **track** + OS **kills** work with `:8000` stopped. Gate interstitial **why/until** from native `get_mode`. Focus Now shows thin read-only why from JSON when API down (as-of) via `https://calt-data.app` in Focus shell.

**Phase 1 verification (2026-09-08):** **verify-phase1 green (owner-confirmed).** Live: Focus quit-rule binary swapped; reward-day → policy → `get_mode` allow/`reward_day`; porn `block`/`enforce:true`; incubation reason/until; Gate/SelfTracker reload + locked.html why/until confirmed by owner. Fixed-window Focus relaunch (3/60s, ~6 straddle) documented as accepted. Deferred: `except Exception: pass` sweep on SoftLand/gate/policy paths. **Settings IA / Figma may start** using the architecture-note data-availability table.

**Companion exports:** [architecture note](../exports/2026-09-08-productivity-settings-architecture-note.md) · [source handoff](../exports/2026-09-08-solo-pack-source-handoff.md)

**Phase 1 does NOT claim:** Focus Settings CRUD solo, live earn ledger, SoftLand clock **writes** without Python.

Do **not** mix Settings IA layout work into this implementation pass.

---

## 1. Locked architecture

| Piece | Role |
|-------|------|
| `calt_enforcer.exe` | Spine: Arm, kills, lock, anti-tamper, non-browser track, Focus watchdog, Service Recovery |
| `calt_msg_host.exe` | Edge door: SoftLand `get_mode` + `track_tab` |
| `calt_focus.exe` | Tray + WebView2 UI only |
| Shared store | `enforcer_policy.json`, `enforcer_status.json`, `softland_policy.json`, `tracked_sessions` |

Three exes, one product. Not one mega-exe.

```text
Gate + SelfTracker
        │ Native Messaging
        ▼
  calt_msg_host ──► softland_policy.json / tracked_sessions
        │
  calt_enforcer ──► kills + desktop track + protect/relaunch Focus
        │
  calt_focus    ──► reads status / policy (Phase 1 Settings still may use :8000)
```

---

## 2. Decisions

| Topic | Lock |
|-------|------|
| Unkillable Focus | Protect + relaunch + **backoff** (max 3 / **fixed** 60s window; auto-clear). Boundary can allow ~6 across a straddle — accepted. Not OS immortality |
| Enforcer crash | Windows Service Recovery (`sc failure` restart/5000 ×3). Brief window while restarting = **Arm fail-open** (kills paused until service back) — acknowledged |
| SoftLand missing policy | Fail-closed (no silent allow-all) |
| Native why/until | `get_mode` returns `mode`, `reason`, `until` |
| Ledger API-down | Frozen snapshot; UI **as-of** |
| Dual SQLite writers | WAL + `sqlite3_busy_timeout` required |
| Hosts porn-block | Out of this pack |

---

## 3. Settings × data availability (cross-walk)

| Group | Availability | API-down | IA note |
|-------|--------------|----------|---------|
| How blocking works | Hybrid → **native-safe (Phase 2)** | SoftLand/Arm writes via enforcer gateway; enforce from JSON mirrors | Commands in Phase 2 gateway spec |
| Now / free time | Hybrid → **native-safe clocks** | Gate why/until native; spend/incubation via enforcer; ledger local | as-of markers |
| Sites SoftLand | Hybrid → **native-safe lists** | Decide + list patch via gateway | |
| Apps Arm | Hybrid → **native-safe Arm** | Arm commands publish `enforcer_policy.json` | Brief fail-open if enforcer restarting |
| Productive scores | Python-required | — | Advanced |
| PC-wide hosts | Python-required | — | Out of solo story |
| Tools / setup | Mixed | Scripts native | |

---

## 4. Phase 1 scope

1. Design spec (this file).  
2. Gate why/until verification (+ until on interstitial if missing).  
3. Protect Focus/msg_host; relaunch + backoff; status fields; Focus thin why from JSON.  
4. Document Service Recovery + Arm fail-open window.  
5. `track_tab` + shared WAL session helper.  
6. Pack docs + smoke (clock expiry, Focus why API-down).

## 5. Phase 2 (later → now unlocked)

**Owner direction (2026-09-08):** backend Phase 2 **before** Settings Figma. Canonical addendum:

→ [2026-09-08-calt-productivity-phase2-gateway-design.md](./2026-09-08-calt-productivity-phase2-gateway-design.md)

Locks: command gateway **inside `calt_enforcer`** (commands + SoftLand clock tick); SQLite SoT from day one; JSON = hot-read mirror only; Focus control-only; msg_host stays ephemeral; Prod P4 remove Gate SoftLand HTTP fallback; `pending_changes` for later akrasia-horizon.

Settings IA layouts stay a **separate pass after** that addendum’s exit criteria.

**Deferred hygiene:** sweep `backend/` for `except Exception: pass` on SoftLand / gate / policy write paths — log or re-raise. Fixed-window Focus relaunch (3/60s) accepted as-is.

## 6. Flaws rejected

Mega-exe; true immortality; msg_host as clock **writer**; Focus as track ingest; claiming Settings/ledger solo in Phase 1; infinite relaunch without backoff.
