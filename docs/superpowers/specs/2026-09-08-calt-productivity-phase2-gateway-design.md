# CALT Productivity — Phase 2 command gateway + SQLite SoT (addendum)

**Date:** 2026-09-08  
**Status:** **Backend closed 2026-09-08** — gateway (SoftLand + Arm + ledger + pending), SQLite SoT, clock tick, import-if-stale and Focus bridge all built and smoked live with `:8000` stopped. Remaining work is the Settings **frontend** overhaul (Figma) only.  
**Parent:** [2026-09-07-calt-productivity-cpp-product-design.md](./2026-09-07-calt-productivity-cpp-product-design.md)  
**SoftLand model (partially superseded for writers):** [2026-09-07-calt-productivity-softland-state-model.md](./2026-09-07-calt-productivity-softland-state-model.md)  
**Solo pack Phase 1 (done):** [2026-09-08-calt-productivity-solo-pack-design.md](./2026-09-08-calt-productivity-solo-pack-design.md)  
**Architecture note (Figma input after this lands):** [../exports/2026-09-08-productivity-settings-architecture-note.md](../exports/2026-09-08-productivity-settings-architecture-note.md)

**Scope choice (owner):** Full Phase 2 before Settings Figma — Settings-write spine + SoftLand clocks + ledger as-of + Gate SoftLand HTTP fallback off.  
**Store choice (owner):** **Gateway + SQLite from day one**; JSON kept only as **hot-read mirror**, not source of truth.

---

## 0. Why this addendum exists

Phase 1 left SoftLand **decide** native and Settings **writes** still hybrid (often via `:8000`). Reframing “JSON vs SQLite” as “command gateway, pluggable store” is correct — but the gateway must not be an unowned box.

This addendum closes three gaps:

1. **Which process owns the gateway**  
2. **Who owns time-based transitions** (not only command-triggered writes)  
3. **Why SQLite-from-day-one** (including future delayed-apply / akrasia-horizon), not JSON-as-SoT with a later migration

---

## 1. Locked ownership (no fourth exe)

| Process | Role after Phase 2 | Must not |
|---------|-------------------|----------|
| **`calt_enforcer.exe`** | **Only mutator.** Command gateway + SoftLand/Arm/runtime **tick** + publish JSON mirrors + kills + Focus watchdog + sessions | Become SoftLand *decide* for Edge (that stays msg-host reading mirrors) |
| **`calt_msg_host.exe`** | Ephemeral Edge door: `get_mode` (read mirrors / shared read API) + `track_tab` | Own durable write authority or clock tick |
| **`calt_focus.exe`** | Control UI only: issue **commands** to enforcer; read mirrors/status for display | Apply policy mutations in-process; SoftLand decide; kill processes |
| **Python `:8000`** | Study content; optional later *emit* study events as commands | SoftLand brain; Gate SoftLand HTTP fallback (removed in Prod P4) |

**Three exes, one product — unchanged.** The gateway is a **new responsibility inside `calt_enforcer`**, not a fourth process.

```text
Focus / Settings UI (React in WebView2)
        │  commands (IPC — see §4)
        ▼
┌──────────────────────────────────────────────┐
│ calt_enforcer  (always-on)                   │
│  • Command gateway (only mutator)            │
│  • SoftLand clock tick (expiry / pending)    │
│  • Publish softland_policy.json mirror       │
│  • Publish enforcer_policy.json (Arm path)   │
│  • Kills + Focus watchdog + desktop track    │
└───────────────┬──────────────────────────────┘
                │ SQLite SoT (WAL)
                ▼
     data/… productivity tables (§5)
                │
                │ atomic mirror publish
                ▼
  softland_policy.json  ·  enforcer_policy.json  ·  enforcer_status.json
                ▲
                │ read-only decide / UI as-of
  calt_msg_host get_mode   ·   Focus thin why   ·   Gate (native only)
```

**Naming forever:** SoftLand ON ≠ Arm. SoftLand commands never set `hard_block_armed`. Arm commands never SoftLand URLs by themselves.

---

## 2. Source of truth vs mirrors

| Layer | Path / store | Role |
|-------|--------------|------|
| **SoT** | SQLite (prefer tables in existing `data/vocab_app.db` under clear `productivity_*` / SoftLand tables, **or** `data/productivity.db` if isolation wins — pick one in implementation plan; default = **same DB file** as sessions for one WAL story) | All SoftLand config, runtime clocks, ledger, day-pass, goals, pending changes |
| **Mirror (hot read)** | `data/behavior/softland_policy.json` | Published by enforcer after mutate/tick; **msg_host SoftLand decide keeps reading this** (no live Python) |
| **Mirror (Arm hot path)** | `data/behavior/enforcer_policy.json` | Published by enforcer on Arm/list/lock commands; kill loop already reads this |
| **Status** | `data/behavior/enforcer_status.json` | Health + focus watchdog fields + optional `gateway_seq` / `softland_as_of` |

**Supersedes** the SoftLand state-model v1 rule “UI read/write `softland_policy.json` as SoT.” After Phase 2 cutover, JSON is **export/mirror only**. Python SoftLand writers become dual-write-then-delete, not SoT.

**Atomic publish:** write SQLite → commit → rewrite mirror JSON via temp file + replace. Readers tolerate brief staleness ≤ one tick (~1.5s).

---

## 3. Tick responsibility (not only commands)

Command-triggered writes are not enough. SoftLand clocks expire with **no UI event**.

**Owner:** `calt_enforcer` main loop (same place as Focus watchdog), every poll (~1.5s):

1. Load runtime from SQLite (or cached in-memory copy invalidated on write).  
2. If `incubation_until` ≤ now → clear incubation; mirror SoftLand + clear `enforcer_policy.incubation_active` if used.  
3. If `free_until` ≤ now → clear free window / reward_day flags per policy rules.  
4. Apply any `pending_changes` where `apply_after ≤ now` (§6).  
5. If anything changed → publish mirrors + bump `updated_at` / `gateway_seq`.  
6. Continue kills + Focus watchdog as today.

**`calt_msg_host` does not tick SoftLand.** Decide only *reads* current mirror (or read API). Expiry must already have been applied by enforcer so `get_mode` sees post-transition state.

This is why the gateway lives in enforcer: **one timer**, one mutator, one publish path.

---

## 4. How Focus talks to the gateway (IPC)

Focus must not mutate JSON/SQLite itself (control-only lock).

**Locked shape:**

```text
Focus WebView2 → native host object / postMessage
       → calt_focus.exe IPC client
       → calt_enforcer command listener
```

**Transport (implementation may pick; preference order):**

1. **Named pipe** `\\.\pipe\calt_enforcer_cmd` (or equivalent) — preferred; works with Focus and later Study emitters.  
2. Localhost TCP loopback — acceptable if pipe is painful on MinGW.  
3. **Not:** “write a command JSON file and hope” as primary (racy).  
4. **Not:** route Settings writes through ephemeral `calt_msg_host` / Edge.

**Protocol sketch (length-prefixed JSON, same family as native messaging):**

```json
{ "op": "softland.set_enabled", "v": 1, "id": "uuid", "payload": { "enabled": true } }
```

```json
{ "ok": true, "id": "uuid", "gateway_seq": 42, "as_of": "2026-09-08T12:00:00Z" }
```

If enforcer is down: Focus shows fail-open/fail-closed UI copy (“Enforcer not running — SoftLand/Arm writes unavailable”); does **not** fall back to Python as SoftLand brain.

---

## 5. Command surface (v1 for Figma-truthful Settings)

Commands are the UI contract. Figma/Settings bind to these, not to raw SQL/JSON.

### 5.1 SoftLand

| `op` | Payload (sketch) | Effect |
|------|------------------|--------|
| `softland.set_enabled` | `{ enabled }` | Toggle SoftLand |
| `softland.patch_site_rules` | `{ allow_extra?, watch_extra?, block_extra? }` | Replace or merge lists (plan picks merge semantics) |
| `softland.patch_schedules` | `{ enabled?, windows? }` | Schedule windows |
| `softland.patch_mode_flags` | `{ study?, free?, … }` | Per-mode flags |
| `softland.patch_goals` | `{ daily_focus_minutes?, … }` | Blocker-relevant goals |
| `softland.spend_free` | `{ minutes }` | Debit ledger → set `free_until` |
| `softland.set_incubation` | `{ until_iso }` / `{ minutes }` | Start/extend incubation |
| `softland.clear_incubation` | `{}` | Only if policy allows (may be locked) |
| `softland.set_reward_day` | `{ active, free_until? }` | Align with Bible claim path later (Study may emit) |
| `softland.set_day_pass` | `{ date, spent, remaining_seconds }` | Day-pass accounting |

### 5.2 Arm / hard-block

| `op` | Payload (sketch) | Effect |
|------|------------------|--------|
| `arm.set` | `{ armed, exes?, lock_mode?, …, provided_unlock? }` | Write Arm SoT + publish `enforcer_policy.json` |
| `arm.patch_exes` | `{ exes }` | Kill list |
| `arm.patch_lock` | `{ lock_mode, secret?, timer_minutes? }` | Lock challenge |

### 5.3 Read helpers (optional; Focus may also read mirrors via `calt-data.app`)

| `op` | Effect |
|------|--------|
| `status.snapshot` | SoftLand + Arm + ledger as-of + `gateway_seq` |
| `ledger.snapshot` | Earned seconds + recent entries (frozen when Study offline) |

### 5.4 As built (2026-09-08)

Every reply carries `ok`, `id`, `gateway_seq`, `as_of` and the SoftLand cache
(`softland_enabled`, `free_until`, `incubation_until`, `reward_day_active`,
`earned_ledger_seconds`); errors reply `{"ok":false,"error":"<token>"}`.

| Shipped `op` | Notes vs sketch above |
|--------------|-----------------------|
| `softland.set_enabled` | as designed |
| `softland.patch_site_rules` | **replace** semantics per list; hosts sanitized (lowercased, must contain a dot) so UI text can never inject JSON |
| `softland.patch_schedules` | `{ enabled?, windows? }`, patched inside the `schedules` object |
| `softland.patch_mode_flags` / `softland.patch_goals` | take the whole `mode_flags` / `goals` object |
| `softland.spend_free` | debits ledger, **stacks** onto a running free window instead of shortening it, writes a `spend` ledger row |
| `softland.set_incubation` / `softland.clear_incubation` | `{minutes}` or `{until_iso}` |
| `softland.set_reward_day` | `{active, free_until?}` — defaults to end of local day |
| `softland.set_day_pass` | `{date?, spent?, remaining_seconds?}` |
| `ledger.add` | `{kind: earn\|spend\|adjust, seconds, note?}` — balance clamped at 0 |
| `ledger.snapshot` | adds `ledger[]` + `balance_seconds` |
| `pending.add` / `pending.list` / `pending.cancel` | akrasia horizon: `{delay_minutes}` or `{apply_after_iso}` + inner `op`/`payload` |
| `arm.set` | writes the `enforcer_policy.json` Arm mirror; honours `lock_mode` password/phrase on disarm |
| `status.snapshot` | as designed |

`arm.patch_lock` was not needed — `arm.set` carries `lock_mode`, secrets and
`lock_until_unix`, so lock changes ride the same command.

**Out of Phase 2 command surface:** productive category scoring CRUD, hosts porn-block, Study notes/GRE — stay Study/Python or later.

---

## 6. SQLite schema shape (v1)

Names illustrative; implementation plan freezes exact DDL.

### 6.1 SoftLand config + runtime

```sql
-- Single-row (or keyed) SoftLand document; JSON columns OK for nested lists/flags
CREATE TABLE productivity_softland (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  schema_version INTEGER NOT NULL,
  softland_enabled INTEGER NOT NULL,
  site_rules_json TEXT NOT NULL,      -- allow/watch/block extras
  schedules_json TEXT NOT NULL,
  mode_flags_json TEXT NOT NULL,
  goals_json TEXT NOT NULL,
  free_until TEXT,                   -- ISO or NULL
  free_after_hm TEXT,
  incubation_until TEXT,
  day_pass_json TEXT NOT NULL,
  reward_day_active INTEGER NOT NULL,
  earned_ledger_seconds INTEGER NOT NULL DEFAULT 0,
  updated_at TEXT NOT NULL
);
```

### 6.2 Ledger (history + as-of)

```sql
CREATE TABLE productivity_ledger (
  id INTEGER PRIMARY KEY,
  ts TEXT NOT NULL,
  kind TEXT NOT NULL,              -- earn | spend | adjust | reward_day
  seconds INTEGER NOT NULL,
  note TEXT,
  source TEXT                      -- focus | study_event | tick | migrate
);
```

UI “live ledger” = query when enforcer up; “as-of” = last published snapshot fields on status/mirror when Study API down (ledger itself is local — **no Python required to read ledger** after cutover).

### 6.3 Pending changes (akrasia-horizon — schema now, apply in tick)

```sql
CREATE TABLE productivity_pending_changes (
  id INTEGER PRIMARY KEY,
  created_at TEXT NOT NULL,
  apply_after TEXT NOT NULL,       -- ISO
  op TEXT NOT NULL,                -- same op strings as §5
  payload_json TEXT NOT NULL,
  status TEXT NOT NULL             -- pending | applied | cancelled
);
```

**Phase 2a:** table exists; tick applies due rows (even if UI does not yet create delayed edits).  
**Phase 2b / Settings IA:** “edit allowed, effect delayed” UX writes `pending` instead of immediate `op`.

This is a concrete reason **SQLite from day one** beats JSON-as-SoT: pending-vs-applied is a first-class row, not hand-rolled twin files.

### 6.4 Gateway meta

```sql
CREATE TABLE productivity_gateway_meta (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  gateway_seq INTEGER NOT NULL,
  last_publish_at TEXT
);
```

---

## 7. SoftLand decide + Prod P4

| Piece | Phase 2 rule |
|-------|----------------|
| `get_mode` | Stays in `calt_msg_host`; reads **published** `softland_policy.json` (or a tiny read-only snapshot API from enforcer — prefer mirror file to keep decide offline if pipe down) |
| Gate SoftLand HTTP `:8000` fallback | **Removed** (Prod P4). Optional hidden storage flag for emergency debug only — default off; not a product path |
| Fail modes | Missing/corrupt SoftLand mirror → fail-closed (already Phase 1). Enforcer down → kills/tick stop (Arm fail-open window already acknowledged); SoftLand decide uses last mirror until stale policy rules say otherwise |

---

## 8. Migration from Phase 1

1. On enforcer start: if SoftLand SQLite empty and `softland_policy.json` exists → import JSON → SoT.  
2. Import Arm fields from `enforcer_policy.json` into Arm tables or keep Arm SoT as JSON until Arm commands land — **preference:** Arm remains JSON-backed through gateway publish for v1 *or* move Arm into SQLite in same pass (implementation plan picks; SoftLand SQLite is mandatory day one).  
3. Python `patch_softland_policy` / reward-day claim: **as built** — Python keeps writing the JSON mirror and the enforcer imports it when the file's `updated_at` is newer than the SQLite row (`ProductivityImportIfStale`, run in the tick *and* before every command's read-modify-write). No Python pipe client, no new Python runtime dependency, and no lost writes in either direction — verified live: a `patch_softland_policy` site-rule write landed in SQLite within a tick, and the next gateway patch preserved it.  
4. Gate: delete SoftLand HTTP fallback after smoke.  
5. Focus: route SoftLand/Arm Settings mutations through IPC; stop requiring `:8000` for those controls.

---

## 9. Exit criteria (before Figma Settings overhaul) — **met 2026-09-08**

| # | Criterion | Evidence (live, this machine) |
|---|-----------|-------------------------------|
| 1 | SoftLand enable + site list + Arm toggle with **uvicorn stopped** | uvicorn killed → `softland.set_enabled` off/on, `softland.patch_site_rules`, `arm.set armed=true` all `ok:true`; `enforcer_status.json` showed `armed: true` |
| 2 | Spend-free / incubation set by command; **tick clears** without UI | `set_incubation 30m` then tick cleared an expired `free_until` and turned reward day off on its own; `pending.add` (apply_after in past) applied `set_incubation 45m` from the tick, row `status='applied'` |
| 3 | Ledger readable as-of without Python | `ledger.add earn 1800` → `ledger.snapshot` returned rows + `balance_seconds` straight from SQLite |
| 4 | Gate SoftLand native-only, why/until intact | `calt_msg_host get_mode`: youtube/pornhub → `action=block, enforce=true, reason=incubation, until=…`; gateway-written `docs.google.com` → `allow_list` (proves gateway list edits reach decide) |
| 5 | Architecture note availability table updated | see [architecture note](../exports/2026-09-08-productivity-settings-architecture-note.md) |
| 6 | No fourth exe; Focus does not decide or kill | gateway lives in `calt_enforcer`; Focus only sends pipe commands |

Two bugs found by running it (not by review): spending earned minutes during a
reward day **shortened** the free window (now stacks), and back-to-back commands
could hit a broken pipe (enforcer recycles the instance immediately, clients
retry 3×).

---

## 10. Explicit non-goals (this addendum)

- Settings IA / Figma layouts (starts **after** exit criteria).  
- Mega-exe / Focus immortality.  
- Making msg_host the write authority.  
- Sliding-window Focus relaunch (fixed 60s accepted).  
- Full `except Exception: pass` sweep (deferred hygiene).  
- Cloning Cold Turkey — pattern only, no CT code.

---

## 11. Self-review checklist

| Check | Result |
|-------|--------|
| Gateway owner named | **`calt_enforcer` only** |
| Clock tick owner | **Same enforcer loop** |
| Focus control-only preserved | Commands only; no in-process apply |
| msg_host stays ephemeral | Read/decide + track; no durable mutator |
| JSON role | Mirror / hot read only |
| SQLite from day one | SoftLand + ledger + pending |
| Akrasia hook | `productivity_pending_changes` + tick apply |
| No fourth process | Locked |
| Conflicts with solo Phase 1 | Extends; SoftLand decide path kept via mirrors |

---

## 12. Next step

Backend is closed. Next is the **Settings frontend overhaul** (Figma) against
§5.4 as the truthful command list and the architecture note's availability
table. Two owner-side checks remain that only a human click can produce:

- Save a site list / schedule from the Focus window and see “saved via enforcer gateway”.
- Arm from Focus and see “Armed via enforcer gateway”.

Verification tools (no browser, no `:8000`):

```bat
powershell -File scripts\desktop_tracker\run\gateway_cmd.ps1 -Op status.snapshot
powershell -File scripts\desktop_tracker\run\msg_host_cmd.ps1 -Json "{\"type\":\"get_mode\",\"url\":\"https://youtube.com\"}"
```
