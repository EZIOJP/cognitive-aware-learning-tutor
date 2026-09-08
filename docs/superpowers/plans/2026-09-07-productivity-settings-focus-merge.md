# Productivity Settings + Focus merge — P0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Mount Focus + SoftLand policy + Wearables into Productivity Settings with SoftLand vs hard-block clarity. Shared FocusControlPanel. No P1/P2.

**Architecture:** Spec `docs/superpowers/specs/2026-09-07-productivity-settings-focus-merge-design.md` (owner-approved 2026-09-07).

**Tech stack:** React Settings host, existing panels, FastAPI enforcer_policy writers.

---

### Task 1: Design lock-ins + SoftLand seed fix

**Files:**
- Modify: `docs/superpowers/specs/2026-09-07-productivity-settings-focus-merge-design.md`
- Modify: `backend/behavior/enforcer_runtime_publish.py`
- Modify: `backend/behavior/enforcer_files.py`
- Test: `tests/test_enforcer_runtime_publish.py` (adjust seed expectations)

- [x] Document: SoftLand callout required; tray Open Focus stays `/productivity/focus`; Open Settings optional later
- [x] Document: DB column `hard_block_enabled` = SoftLand (legacy name); API/UI prefer `softland_enabled` alias; physical rename deferred
- [x] Document: kill-list writes blocked while armed + active lock (same as Disarm)
- [x] Seed policy: never set `hard_block_armed` from SoftLand `hard_block_enabled`
- [x] `write_policy_file`: refuse exe list changes when lock blocks disarm

### Task 2: SoftLand API alias + Policy panel labels

**Files:**
- Modify: `backend/behavior/productivity_policy.py`
- Modify: `src/api/behaviorClient.ts`
- Modify: `src/components/productivity/ProductivityPolicyPanel.tsx`

- [x] Serialize `softland_enabled` (= `hard_block_enabled`); accept either on save
- [x] UI: SoftLand toggle uses SoftLand copy; never say “hard block” for this toggle

### Task 3: Mount Settings hub (P0 UI)

**Files:**
- Modify: `src/pages/ProductivityPage.tsx`
- Modify: `src/components/productivity/FocusControlPanel.tsx` (kill-list disabled when locked)
- Modify: links in Settings / Policy / setup that point at Focus for SoftLand/enforcer

- [x] Import + mount FocusControlPanel `#focus`, ProductivityPolicyPanel `#policy`, WearablesSyncPanel `#watch`
- [x] Top SoftLand vs Arm callout (permanent)
- [x] Anchors; retarget same-tab Focus links
- [x] Focus page unchanged (same component)
- [x] Disable kill-list input when armed + active lock

### Task 4: Verify

Evidence (2026-09-07):

- [x] Kill-list refusal: `tests/test_enforcer_files.py::test_kill_list_locked_while_armed_password` — armed + password lock + different exes → `EnforcerLockError` matching `Kill list locked` (**1 passed**)
- [x] Related suite: `tests/test_enforcer_files.py` + `test_enforcer_runtime_publish.py` (**6 passed** earlier; refusal re-run alone **1 passed**)
- [x] Grep: Settings mounts `FocusControlPanel` / `ProductivityPolicyPanel` / `WearablesSyncPanel`; SoftLand callout + `#focus` anchors present
- [x] IDE lints on touched React/API files: **clean** (`ReadLints`)
- [x] `tsc --noEmit`: **N/A in this repo** — no root `tsconfig.json`, TypeScript not a package dependency (Vite transpile only). Do not treat missing `tsc` as a pass for typecheck; rely on IDE diagnostics + runtime smoke.
- [x] Rollback note: revert Settings mounts in `ProductivityPage.tsx` if broken

**Do not:** P1 GlanceBar, tray Open Settings, kill presets, accordion, Focus nav removal, DB column rename.

**Next (owner):** live-use Settings hub for a few days before P1/P2. Pick Lane 1 (browser list + anti-tamper) vs Lane 2 polish only when ready.
