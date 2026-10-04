# CALT Device lock — native (C++ enforcer) design

**Date:** 2026-09-12  
**Status:** Implemented 2026-09-13 — native cutover landed (Focus Filters uses enforcer; Study routes 410)  
**Parent:** [2026-09-07-calt-productivity-cpp-product-design.md](./2026-09-07-calt-productivity-cpp-product-design.md)  
**Related:** [2026-09-08-calt-productivity-phase2-gateway-design.md](./2026-09-08-calt-productivity-phase2-gateway-design.md), [docs/BLOCKING_RULES.md](../../BLOCKING_RULES.md)  
**UI surface:** Focus → Settings → **Filters** → Device lock (hosts)

**Owner lock (2026-09-12):** Migrate Device lock (Windows hosts porn block) off Study `:8000` into `calt_enforcer` gateway + elevated one-shot CLI. Same sole-mutator pattern as SoftLand/Arm. Include list refresh (WinHTTP scrape) in C++, not deferred.

---

## 0. Why

Device lock is a **permanent, PC-wide** porn block via the Windows `hosts` file. SoftLand Allow / free / reward **cannot** override it. Today status/settings/list-refresh still go through Study FastAPI (`device_block.py` + `/api/behavior/device-block*`). That breaks the Productivity product rule: blocker state must not depend on a live Python process.

Focus already elevates apply/remove via `run_repo_bat` → `scripts\device_block_*.bat`. Those bats still call Python. This design makes **C++ the only writer** of settings, cache, and hosts.

**Out of scope:** SoftLand porn heuristic; Gate extension DNR porn; AI porn detector; community shared lists; Arm lock_mode timer/password on remove (v1.1 optional).

---

## 1. Ownership (no fourth product brain)

| Process | Role | Must not |
|---------|------|----------|
| **`calt_enforcer.exe`** | Sole mutator of Device lock SoT; gateway ops; hosts writer (when elevated enough); scrape worker | Run scrape or hosts I/O on the Arm kill / SoftLand tick thread |
| **`calt_focus.exe`** | UI: gateway commands + `run_repo_bat` for UAC | Write hosts or settings itself; call Study `:8000` for Device lock |
| **Elevated one-shot** | Same `calt_enforcer.exe` with `--device-block-apply` / `--remove` / `--refresh` | Separate product binary (no `calt_device_block.exe` in v1) |
| **Python `:8000`** | Unrelated Study content | Device lock SoT, hosts write, or Filters API after cutover |

```text
Focus Filters UI
    │  enforcer_cmd (pipe)     │  run_repo_bat (UAC)
    ▼                          ▼
calt_enforcer gateway     elevated calt_enforcer.exe --device-block-*
    │                          │
    └──────── same module ─────┘
              │
              │ Global\CALT_DeviceBlockHosts mutex
              ▼
     hosts file  +  JSON SoT under data/productivity/behavior/
```

**Naming:** SoftLand ON ≠ Arm ≠ Device lock. Device lock never sets `hard_block_armed` or SoftLand mode.

---

## 2. Source of truth

| Artifact | Path | Role |
|----------|------|------|
| Settings SoT | `data/productivity/behavior/device_block.json` | `enabled`, `block_porn`, `block_watch`, `block_social`, `extra_domains`, `source`, schema `v` |
| Porn list cache | `data/productivity/behavior/porn_blocklist.json` | Scraped domains + metadata (`as_of`, `source_url`, counts) |
| Migration marker | `data/productivity/behavior/device_block.migrated` | Written **only after** successful legacy copy (temp+rename). Presence ⇒ never re-migrate |
| Legacy (forensics only) | `data/behavior/device_block.json`, `data/behavior/porn_blocklist.json` | **Read once for migration; never written again by product code after cutover** |

**Not SQLite.** Device lock is OS-hosts adjacent and low-churn; JSON mirrors SoftLand/Arm file patterns under `data/productivity/behavior/`. SoftLand tables stay untouched.

### Settings shape (v1)

```json
{
  "v": 1,
  "enabled": false,
  "block_porn": true,
  "block_watch": false,
  "block_social": false,
  "extra_domains": [],
  "source": "calt_enforcer"
}
```

Defaults: porn on, watch/social off (same as today’s Python defaults).

### Effective domain set

```text
effective = union(SEED_PORN_DOMAINS, cache.domains if present, extra_domains)
            + optional SEED_WATCH / SEED_SOCIAL when flags on
```

**Seeds are a floor via union, never replace.** A bad/empty scrape must not thin the lock. Port seed lists from `browser_gate_policy.py` (`DEFAULT_PORN_DOMAINS`, watch, social) into a C++ header or static data file in the enforcer tree.

---

## 3. Legacy migration (idempotent)

1. If `device_block.migrated` exists → **skip** (never re-read legacy for SoT).
2. Else if legacy settings and/or cache exist under `data/behavior/` → copy each via **temp file + atomic replace** into productivity paths; then create `device_block.migrated`.
3. Else → write default settings JSON (+ empty/seed-only cache as needed) → create marker.
4. Crash mid-copy → no marker → safe retry on next boot / first `device_block.*` op.
5. **Never delete** legacy files (rollback / forensics).

**Trigger:** enforcer startup and/or first `device_block.status|save|…` — either is fine; both must obey the marker.

### Legacy Python path retired

After cutover:

- `backend/behavior/device_block.py` hosts/settings **write path is dead** for product use (read-only / unused; keep on disk for forensics).
- Study routes `/api/behavior/device-block*` must not mutate SoT or hosts (410/stub, or thin redirect docs only — pick in plan; Focus must not call them).
- `scripts\device_block_*.bat` call **native** CLI only — no `python -m backend.behavior…`.
- Tracker hourly Python hosts sync (`tracker_porn_block`) must not write hosts or SoT after cutover (disable or no-op).

Two live writers / two stores after migration = **spec violation**.

---

## 4. Gateway ops

Pipe: `\\.\pipe\calt_enforcer_cmd`  
Request: `{"v":1,"id":"…","op":"…","payload":{…}}`  
Success/failure envelopes match existing gateway style.

| Op | Payload | Behavior |
|----|---------|----------|
| `device_block.status` | `{}` | Ensure migrated; return settings, `active` (hosts section present), counts, verify sample, `refresh` state, `needs_admin` hint if last apply failed for elevation |
| `device_block.save` | patch fields; optional `apply_now`; **`confirm` required iff enabling or disabling** | Patch settings JSON; optional best-effort apply |
| `device_block.apply` | **`confirm` required iff this call causes enable↔disable** | Write/remove hosts under mutex; DoH disable when enabling; DNS flush |
| `device_block.remove` | **`confirm`: `"DEVICE LOCK"` required** | `enabled=false` + remove hosts section (or `needs_admin`) |
| `device_block.refresh_list` | optional `force: true` | Kick async scrape worker only; never block kill tick |

### Confirm phrase (single gate — all entry points)

- Exact string: `DEVICE LOCK` (same as Focus UI).
- **Required for:** any **enable↔disable** transition (`enabled` false→true or true→false), including `device_block.remove`.
- **Not required for:** `block_watch` / `block_social` / `extra_domains` / refresh / hosts **re-apply** when `enabled` is already true and stays true.
- Missing/wrong confirm → `error: confirm_required` or `confirm_mismatch` (gateway) or non-zero exit (CLI).
- **Shared implementation (mandatory):** confirm-check + the actual `enabled` flip live in **one** internal function. Gateway `device_block.save`, `device_block.apply`, `device_block.remove`, and CLI `--device-block-apply` / `--device-block-remove` all call that function — not three (or five) independent copies of the gate. Drift of one path without the others is a spec violation.

### Apply result fields (extraOut)

Include at least: `needs_admin` (bool), `domain_count`, `apply_ok`, optional `error` token (`hosts_busy`, `access_denied`, `confirm_required`, `confirm_mismatch`, …).

When process is not elevated enough to write hosts → settings flip may still succeed via the shared gate (with confirm); return `needs_admin: true` for the hosts write. Focus shows **Apply as Admin** and must pass the same typed confirm into the bat/CLI (see §5). The CLI is often the **primary** hosts writer on real installs — confirm on that path is main-path, not pipe-down-only.

---

## 5. CLI one-shot (elevated bat target)

Same binary, no fourth exe:

```text
calt_enforcer.exe --device-block-apply --confirm "DEVICE LOCK"
calt_enforcer.exe --device-block-remove --confirm "DEVICE LOCK"
calt_enforcer.exe --device-block-refresh [--force]
```

- Load SoT from disk (run migration if needed).
- Use **same** hosts writer / scrape module as gateway.
- Take **same** Global mutex for hosts mutations.
- Exit non-zero on failure; bats surface that.

### CLI confirm (mandatory — closes Focus/pipe bypass)

Focus must not write settings/hosts itself (§1). When the pipe is down — and often when it is up but the service is not Admin — the elevated CLI is the only process that can flip `enabled` and write hosts. Client-side Focus typing is **not** enforcement.

- Binary verifies `--confirm` itself via the **same shared gate** as §4 before any enable↔disable transition.
- `--device-block-remove` always requires a correct `--confirm` (disable transition / explicit remove).
- `--device-block-apply` requires `--confirm` when it would enable (or otherwise flip `enabled`); pure re-apply with `enabled` already true may omit it.
- Missing or wrong `--confirm` on a gated transition → **refuse**, non-zero exit, **no** settings flip, **no** hosts write.
- Smoke: from an elevated shell, `calt_enforcer.exe --device-block-remove` with no/`--confirm` wrong → must refuse.

`scripts\device_block_apply.bat` / `device_block_remove.bat`:

1. Accept confirm as an argument (or equivalent) from Focus; re-pass it after self-elevate (`RunAs`) so the elevated instance still sees it.
2. Invoke `calt_enforcer.exe` with `--device-block-apply|remove` and `--confirm "…"`.
3. No Python.

Focus: `run_repo_bat` message includes the confirm string the user typed; `webview_host.cpp` passes it through to the bat (whitelist remains those bat names only — confirm is data, not a new bat).

---

## 6. Hosts writer

Parity with current Python behavior (port, don’t invent):

- Path: `%SystemRoot%\System32\drivers\etc\hosts`
- Markers: `# BEGIN CALT-DEVICE-BLOCK` / `# END CALT-DEVICE-BLOCK`
- Per domain: `0.0.0.0`, `127.0.0.1`, `::1`, plus `www.` expansion where applicable
- Remove = strip managed section only; leave rest of hosts intact
- After successful write/remove: flush DNS (`ipconfig /flushdns` or equivalent API)
- **DoH disable on apply (enable path):** explicit step — set Windows DoH policy keys so DoH cannot silently bypass hosts (same intent as today’s Python `_disable_windows_doh`). Documented as a first-class apply step, not a parenthetical. If the API/reg write fails while hosts succeeded, return warning fields but do not roll back hosts unless implementer finds that unsafe — prefer “hosts on + warn” over “fail closed and leave porn open.”

### Hosts mutex (mandatory)

- Name: **`Global\CALT_DeviceBlockHosts`**
- Scope: entire hosts read → merge → write (+ DNS flush / DoH steps that must not interleave with another apply)
- Acquire wait: **5 seconds**; else fail with `error: hosts_busy` — **no partial write**
- **DACL: not Everyone.** Allow open/synchronize only for:
  - Local Administrators
  - The account the enforcer service/task actually runs as (install-time SID), and/or `CREATOR OWNER` as needed for create
- Rationale: a mutex any process can hold forever is a DoS against Apply (`hosts_busy` forever) — same anti-tamper class as Arm `lock_mode` / protect-uninstall.
- Both gateway apply/remove and CLI `--device-block-*` **must** use this mutex.

---

## 7. List refresh (scrape) — isolation rules

### Hard rules

1. **Never** schedule or run scrape on the Arm kill tick (~1.5s) or SoftLand tick thread.
2. **No auto-scrape-on-tick** at all in v1 — removes fail-open risk at the source. Refresh only via:
   - Gateway `device_block.refresh_list`
   - Elevated CLI `--device-block-refresh`
3. Dedicated **worker thread** (or one-shot CLI process) only.
4. **Hard timeout: 20 seconds** for the HTTP fetch+parse budget.
5. Gateway `refresh_list` **kicks** the worker and returns immediately:

```json
{ "refresh": "started" | "already_running" }
```

6. `device_block.status` exposes refresh machine:

```text
refresh: idle | running | ok | failed
last_error?: string
cache_as_of?: iso/epoch
```

7. On timeout/failure/empty parse: **keep last good cache**; effective set still **union seeds**; Apply remains allowed.

### Scrape sandbox

- HTTPS only; host allowlist: **`theporndude.com`** (and www if needed) — **no off-allowlist redirects**
- Max response size cap (implementation plan picks bytes; must be finite)
- Parse index pages only (parity with current `porn_blocklist.py` intent — not full-site crawl)
- Cache TTL **7 days** for “stale” UX hints; forced refresh ignores TTL

---

## 8. Focus UI states (Filters)

Filters stays **outside** `EnforcerWriteGate` so SoftLand/Arm “enforcer write gate” greying does not hide Device lock. Behavior is keyed off the **enforcer command pipe**, not SoftLand/msg-host, not Study `:8000`.

| State | Filters behavior |
|-------|------------------|
| SoftLand / msg-host down | **No effect** — Device lock does not use SoftLand |
| Study `:8000` down | **No effect** — Filters never calls Study after cutover |
| Enforcer pipe **up** | Full UI: status / save / refresh via gateway; show Apply/Remove as Admin when `needs_admin` |
| Enforcer pipe **down** | Filters still visible. Banner: start `calt_enforcer`. Gateway buttons disabled. **Apply/Remove as Admin still enabled** — elevated one-shot reads disk SoT and writes hosts without the live pipe, **with `--confirm` from the Focus dialog** (§5) |
| After Admin bat, pipe still down | Message: “Hosts updated via Admin — start enforcer to verify.” |
| After Admin bat, pipe up | Poll `device_block.status` to show ACTIVE / counts / verify sample |

Confirm UX: type `DEVICE LOCK` to enable; same phrase to remove/disable. Focus must forward that string to gateway **and** to Admin bats — never assume the dialog alone is enough.

Optional streaming/social hosts toggles remain under a details warning (conflict with SoftLand unlock). No confirm phrase for those toggles; apply still may need Admin.

---

## 9. Frontend cutover

- `DeviceBlockPanel` uses `enforcerNativeCmd("device_block.*")` (same bridge as day loop / bible / arm).
- Remove Study `fetchDeviceBlock` / `saveDeviceBlock` / `refreshDeviceBlockList` from Filters path (delete or leave unused).
- Keep `run_repo_bat` for Apply/Remove as Admin — **include the typed confirm** in the message so bats/CLI can enforce §5.
- Settings hub: Filters `availability` reflects **native/gateway**, not Study API.
- Hub copy: Device lock needs enforcer (+ Admin once), not `:8000`.

---

## 10. Acceptance / smoke

With **Study `:8000` stopped**:

1. Enforcer running → Filters status loads via gateway.
2. Enable with confirm → settings on disk; if not Admin → `needs_admin`; Apply as Admin → hosts section present; verify sample blocked.
3. SoftLand Allow cannot open a hosts-blocked porn domain.
4. Refresh list (pipe up) → worker starts; status shows running then ok/failed; seeds still in effective set if scrape fails.
5. Concurrent apply vs elevated bat → one wins under Global mutex; other gets `hosts_busy` or waits ≤5s — no torn hosts file.
6. Reboot / restart enforcer → marker present → no re-migration; legacy files unchanged on disk.
7. Remove with confirm (+ Admin if needed) → hosts section gone; settings `enabled: false`.
8. Kill tick continues while a forced refresh is in flight (no multi-second stall on kill loop).
9. Elevated shell: `--device-block-remove` with no confirm or wrong `--confirm` → refuse; settings and hosts unchanged.
10. Elevated shell: `--device-block-remove --confirm "DEVICE LOCK"` → disable + hosts section removed (when Admin).

---

## 11. Implementation sketch (not the plan)

Suggested enforcer modules (names flexible):

- `device_block_settings.cpp` — load/save JSON, migration, marker
- `device_block_hosts.cpp` — mutex, hosts RMW, DNS flush, DoH
- `device_block_list.cpp` — seeds, cache, WinHTTP scrape worker
- Wire ops in `cmd_gateway.cpp` `HandleOp`
- CLI flags in `main` / win_service entry before service loop
- Update bats; rebuild enforcer + focus payload copy
- Update `docs/BLOCKING_RULES.md` Hosts section to “native SoT”

Full task breakdown → `writing-plans` after owner signs this spec for implementation.

---

## 12. Spec self-review checklist

| Check | Result |
|-------|--------|
| Scrape vs kill tick | Explicit: no tick schedule; worker only; 20s timeout; kick+status |
| Two writers / hosts race | Global mutex + scoped DACL (not Everyone) + `hosts_busy` |
| Migration idempotency | Marker file after temp+rename; legacy never deleted; no re-migrate |
| Filters UI states | Four relevant states tabled (SoftLand, Study, pipe up, pipe down + post-Admin) |
| Remove gate | Confirm required; optional toggles exempt; Admin for hosts clear when needed |
| CLI confirm bypass | `--confirm` verified in binary; bats/Focus pass-through; smoke #9 |
| Shared enable gate | One internal function for save/apply/remove + CLI |
| Dual SoT drift | Legacy Python write path retired post-cutover |
| DoH | First-class apply step |
| Seeds floor | Union, not replace |
| Placeholders | Seed port source named; max scrape bytes left to plan (finite required) |
| Fourth exe | Rejected — same `calt_enforcer.exe` CLI |

---

## 13. Decision log

| Decision | Choice |
|----------|--------|
| Architecture | Gateway-owned everything (Approach 1) |
| Scrape in v1 | Yes (WinHTTP), async, no tick auto-refresh |
| Refresh failure | Keep last cache + seed union; Apply allowed |
| Settings store | JSON under `data/productivity/behavior/` |
| Admin path | Elevated same exe CLI via existing bats |
| Mutex | `Global\CALT_DeviceBlockHosts`, Admin + enforcer account DACL |
| Confirm | Enable + remove/disable only; shared gate; CLI `--confirm` required on transitions |
| Legacy files | Keep on disk; product writes only productivity paths |
| Study API | Dead for Device lock after cutover |
