# One engine — possibilities, problems, wiring

**Date:** 2026-09-07  
**Status:** Map only — historical options; SoftLand-on-Python brain **superseded**  
**Authoritative product lock:** [2026-09-07-calt-productivity-cpp-product-design.md](./2026-09-07-calt-productivity-cpp-product-design.md)  
**Prior split doc (partially superseded):** [2026-09-07-calt-blocker-study-split-decisions.md](./2026-09-07-calt-blocker-study-split-decisions.md)  
**Phase 2 store:** [2026-09-07-calt-productivity-softland-state-model.md](./2026-09-07-calt-productivity-softland-state-model.md)

**Owner lock (2026-09-07 evening):** **One productivity/blocker engine in C++** (SoftLand + kills + track). Study content stays Python. SoftLand must work with uvicorn stopped.  
**P7** (Python kills) still **rejected**. Do not expand Qt.

This file remains useful as a problem matrix and wiring sketch. For what is locked, use the product design.

---

## 0. Picture of now (two engines)

```text
┌─────────────────────────────────────────────────────────────────┐
│ YOU                                                             │
│  React Settings / Focus  ·  calt_focus tray (WebView2)          │
└───────────────┬─────────────────────────────┬───────────────────┘
                │                             │
                ▼                             ▼
┌───────────────────────────┐   ┌─────────────────────────────────┐
│ ENGINE A — SoftLand       │   │ ENGINE B — Hard block           │
│ Python API :8000          │   │ calt_enforcer.exe (C++)         │
│ distraction_gate          │   │ reads enforcer_policy.json      │
│ productivity_policies     │   │ writes enforcer_status.json     │
│ planner / morning / Bible │   │ TerminateProcess on exes        │
│ tracked_sessions / export │   │ ownership lock / stay-alive     │
└─────────────┬─────────────┘   └─────────────────────────────────┘
              │
              ▼
┌───────────────────────────┐
│ Edge CALT Gate + SelfTracker│
│ polls SoftLand for sites  │
└───────────────────────────┘
```

| Concern | Engine | Data |
|--------|--------|------|
| Site allow/block | A (Gate → API) | Gate JSON / SoftLand mode |
| App process kills | B (native) | `enforcer_policy.json` |
| Study / quiz / notes | A | SQLite `vocab_app.db` |
| Scores / export | A | SQLite + export API |
| Arm / kill list / lock | UI → JSON → B | Focus / Settings `#focus` |

**Naming trap (keep forever):**  
`softland_enabled` (DB legacy: `hard_block_enabled`) ≠ `hard_block_armed` (native kill switch).

---

## 1. What “one engine” could mean (possibilities)

Pick a **target** later. Each row is a different product.

| ID | Target | One sentence |
|----|--------|----------------|
| **P0** | Stay split (current) | SoftLand Python; kills native; polish wiring only |
| **P1** | Strong OS engine | Same split; native feels CT-class (browsers, anti-tamper, service) |
| **P2** | One *policy file* | Still two processes; one schema both read (sites + exes + armed) |
| **P3** | One *control UI* | Already mostly done (Settings hub); tray → Settings only |
| **P4** | Msg-host SoftLand | Gate talks to `calt_msg_host` (native); host may ask Python or own rules |
| **P5** | Native SoftLand | C++ (or host) owns site rules + kills; Python only study |
| **P6** | Full monolith native | Enforcer owns SoftLand + kills + maybe tracking; Python = study web only or gone |
| **P7** | Full monolith Python | Put kills back in Python tracker | **Conflicts with DESKTOP TRACKER RULE — reject unless owner reverses AGENTS.md** |

**Locked ranking (2026-09-07 evening):** Productivity C++ product lock wins. Old **P5/P6 un-parked** as Prod P3–P6. **P7 rejected**. See [product design](./2026-09-07-calt-productivity-cpp-product-design.md).

---

## 2. Problems matrix (why “small swift” fails for P5/P6)

| Problem | Hits | Why it hurts |
|---------|------|----------------|
| SoftLand is **stateful study logic** | P5, P6 | Bible → plan → Study Loop → goal → day-pass → free/spend → incubation. Not “block youtube.com” |
| Site block ≠ process kill | P1–P6 | Killing `msedge.exe` ends all study tabs. SoftLand needs **per-URL** Gate |
| Extension must talk to someone | P4–P6 | Today `:8000`. Native needs **Native Messaging Host** (+ install) |
| Morning / planner / rewards | P5, P6 | Live in Python + SQLite; port or keep calling Python |
| Session tracking | P5, P6 | Still Python `tracker_service` (or native track later — separate project) |
| Zero-Python kill rule | P5, P6 | SoftLand compute can stay Python; **kills** must not require live uvicorn |
| Qt / old tray / name collision | All | Cognitive mess, not engine power — archive/ignore |
| Two Focus doors | P3 | `/productivity/focus` vs Settings `#focus` — polish, not engine |
| Anti-tamper / time cheat | P1 | Native-only; does not unify SoftLand |
| Energy / monolith fatigue | P6, P7 | Large rewrite; easy to strand half-migrated |

---

## 3. Wiring map (every important wire)

### 3.1 SoftLand path (Engine A)

```text
Edge tab URL
  → CALT Gate extension
  → HTTP GET/poll FastAPI :8000 (distraction_gate / browser mode)
  → allow / SoftLand interstitial / study-only
SelfTracker
  → tab/domain stats → API → tracked_sessions / browser stats
```

**Key files (indicative):**  
`calt-gate-extension/` · `backend/behavior/distraction_gate.py` · `browser_gate_policy.py` · `productivity_policy.py` · `backend/behavior/router.py`

### 3.2 Hard-block path (Engine B)

```text
Settings / Focus UI
  → PUT enforcer-policy (API writes file)  OR  UI → file
  → data/behavior/enforcer_policy.json
  → calt_enforcer reads loop
  → TerminateProcess(exes) + status JSON
```

**Key files:**  
`src/components/productivity/FocusControlPanel.tsx` · `backend/behavior/enforcer_files.py` · `native/calt_enforcer/` · `enforcer_status.json`

### 3.3 SoftLand → native (narrow wire today)

```text
Gate publish (Python)
  → enforcer_runtime_publish.py
  → may set incubation_active on existing policy file
  → MUST NOT set hard_block_armed from SoftLand (seed stays disarmed)
```

### 3.4 Focus snapshot (shared, still under calt_desktop path)

```text
GET focus-dashboard
  → backend.behavior.calt_desktop.dashboard_bridge.snapshot_for_user
  → React FocusControlPanel
```

**Debt:** bridge lives under `calt_desktop/` but is **not** Qt UI — extract before deleting Qt package.

### 3.5 Control UI

```text
calt_focus.exe → WebView2 → dist-focus / calt.app → React
  /productivity/focus          → FocusControlPanel (tray default)
  /productivity?tab=settings   → same panel @ #focus + SoftLand @ #policy
```

### 3.6 Legacy (ignore / archive later — not engines)

```text
run_calt_desktop_qt.bat → PySide6 calt_desktop UI
run_desktop_tracker.bat → old Python tray / kill path
enforcer_service (Python) → legacy kill fallback only
focus_desktop → deprecated stub
```

---

## 4. Possibility deep-dives (deal with later)

### P1 — Strong OS engine (low regret)

**Do:** Broad `IsBrowserExe` + display names · anti-tamper while locked · Admin/`install_native_enforcer.ps1` once · optional tray badge.  
**Don’t:** Move SoftLand into C++.  
**Problems left:** SoftLand still needs API; site cheating via non-Edge browsers if not killed/listed.  
**When:** Next coding energy after Settings live-use.

### P2 — One policy schema

**Do:** Single JSON/SQLite doc: `{ softland: {...}, enforcer: { armed, exes, lock } }` both engines read.  
**Problems:** Migration · Gate still needs HTTP or host · easy to reintroduce SoftLand→armed bugs.  
**When:** After P1 if dual files confuse you.

### P3 — One control door

**Do:** Tray “Open Settings” → `?tab=settings#focus` · optional hide Focus nav.  
**Problems:** None serious.  
**When:** After a few days on Settings hub (P1 polish from merge design).

### P4 — Native Messaging Host skeleton

**Do:** `calt_msg_host` answers ping from Gate; still forward SoftLand to Python first.  
**Problems:** Edge host install · manifest · debugging.  
**Unlocks:** Path to P5 without big bang (P5 still parked).  
**When:** Approved optional wire — after/with P1 if calm. Does **not** make SoftLand work with Python dead.

### P5 — Native SoftLand (sites)

**Do:** Host or enforcer evaluates allow/block; Gate stops calling `:8000` for mode.  
**Need:** Port or RPC for morning/Bible/goal/passes **or** simplify SoftLand rules drastically.  
**Problems:** Largest product risk after study itself · must not require uvicorn for kills.  
**When:** **Parked** — only after P4 works and energy exists. Not next work.

### P6 — Full native blocker monolith

**Do:** One process: kills + SoftLand + optionally track.  
**Problems:** Rebuild Gate contract · study coupling · years of Python logic · **high energy**.  
**Owner note:** You said you don’t have energy for monolith again — treat P6 as **parked fantasy** until P1–P4 are boring.

### P7 — Python kills again

**Do:** TrackerService kills.  
**Problems:** Violates locked DESKTOP TRACKER RULE · kills die with Python · undoes native work.  
**Verdict:** Out unless AGENTS.md is explicitly reversed.

---

## 5. “We already have everything” — inventory (reuse, don’t rewrite)

| Already have | Reuse for |
|--------------|-----------|
| `calt_enforcer` kill loop + policy JSON | P1 anti-tamper / browser exes |
| `enforcer_policy` lock modes | Same lock gate for kill-list + anti-tamper |
| Focus / Settings UI | P3 one door |
| `distraction_gate` + Gate extension | SoftLand until P4/P5 |
| SQLite policies / planner / Bible | SoftLand inputs forever (or RPC into host) |
| `browser_labels.py` + native browser checks | P1 broaden list |
| `install_native_enforcer.ps1` | Stay-alive |
| Msg-host scripts (if started) | P4 |

**Missing for true one SoftLand engine:** per-URL decision in native/host · host install · ported or RPC’d study gates · tests that SoftLand ON ≠ Arm.

---

## 6. Decision log (fill when you choose)

| Date | Choice | Notes |
|------|--------|-------|
| 2026-09-06 | Split locked | Native kills; Python SoftLand/study |
| 2026-09-07 | Settings hub P0 | One UI home; two engines unchanged |
| 2026-09-07 | Combined decisions locked | SoftLand compute Python; P5 parked; P1/P3 next then done |
| 2026-09-07 | P1 + P3 completed | Browsers/anti-tamper already in enforcer; tray Open Settings shipped |
| 2026-09-07 | Combined lock | SoftLand compute stays Python; P1 next; P4 approved optional; P5/P6 parked; P7 rejected — see [decisions doc](./2026-09-07-calt-blocker-study-split-decisions.md) |
| 2026-09-07 | P5a draft | Written then **parked** (not next work) |
| _TBD_ | Implement P1 / optional P4 | |

---

## 7. If energy is low — only do this

1. **Use:** `run_calt_desktop.bat` + Settings + API. Ignore Qt.  
2. **Code next (when ready):** P1 browser list + anti-tamper. Optional P4 msg-host relay after/with P1.  
3. **Don’t:** P5/P5a/P6/P7, Qt deletion mega-PR, “move SoftLand into enforcer this weekend.”  
4. **Reopen** the [decisions doc](./2026-09-07-calt-blocker-study-split-decisions.md) first; use this map for options only.

---

## 8. Related docs

- [2026-09-07-calt-blocker-study-split-decisions.md](./2026-09-07-calt-blocker-study-split-decisions.md) — **locked choices**  
- [AGENTS.md](../../../AGENTS.md) — DESKTOP TRACKER RULE  
- [2026-09-06-calt-native-enforcer-design.md](./2026-09-06-calt-native-enforcer-design.md)  
- [2026-09-07-productivity-settings-focus-merge-design.md](./2026-09-07-productivity-settings-focus-merge-design.md)  
- [2026-09-07-p5a-native-softland-study-flags-design.md](./2026-09-07-p5a-native-softland-study-flags-design.md) — parked draft only  
- [2026-09-07-ct-maturity-ideas-reminder.md](../exports/2026-09-07-ct-maturity-ideas-reminder.md)  

---

**Bottom line:** Locked path ≈ **P1** (then optional **P4** relay). One *literal* SoftLand+kill process ≈ **P5** (parked). This file holds the option mess; the decisions doc holds what is locked.
