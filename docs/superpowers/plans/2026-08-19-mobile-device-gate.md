# CALT Device Gate Implementation Plan

> **NEXT PLAN:** Android v1 (Phases 0–2). **THEN:** iOS/iPad (Phase 4). PC tracking/blocking/rewards are already shipped — do not rebuild them here.
>
> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a Flutter shell plus Android native blocking that obeys PC `day-status` until daily productivity is done; iOS later.

**Architecture:** PC remains the clock. Flutter polls `GET /api/behavior/day-status` (and hub `:8765` fallback). Kotlin Accessibility overlay (+ optional VPN) enforces porn-hard / distraction-until-unlock / 5‑min rest after unlock. iOS Family Controls is a second phase.

**Tech Stack:** Flutter, Kotlin (Android), Swift (iOS phase 2), existing FastAPI `day-status`, JWT or wearable key.

## Global Constraints

- Do not expand PC study/quiz scope in this lane.
- Flutter must not implement blocking; only MethodChannel to native.
- Fail closed if PC unreachable (keep last lock; never auto-unlock).
- Sideload Android; no Play Store requirement.
- iOS does not start until Android v1 is daily-driver on the owner phone.
- Spec: `docs/superpowers/specs/2026-08-19-mobile-device-gate-design.md`.

---

## File map (when implemented)

| Path | Responsibility |
|------|----------------|
| `backend/behavior/day_status.py` | Add `device_gate` object (`unlocked`, remaining minutes, copy of lists later) |
| `tests/test_day_status.py` | Assert `device_gate.unlocked` matches existing gate unlock |
| `packages/calt-device-gate/` | New Flutter app (not Expo tracker) |
| `packages/calt-device-gate/android/` | Accessibility service, overlay, UsageStats, optional VpnService |
| `packages/calt-device-gate/ios/` | Phase 2: Family Controls extensions |
| `packages/calt-android-tracker/` | Unchanged glance app |

---

## Phase 0 — PC flag only (small, testable)

- [ ] **Task 0.1:** Define `device_gate.unlocked` in one place as the same boolean the PC already uses for “distraction allowed” (`hard_block.unlocked` or `day_unlimited` or `browser_mode == free` — pick **one** rule and comment it).

- [ ] **Task 0.2:** Add `device_gate` to `build_day_status` return dict (`unlocked`, `remaining_minutes`, `poll_hint`).

- [ ] **Task 0.3:** Extend `tests/test_day_status.py` so locked morning ≠ unlocked; goal-met / unlimited ⇒ unlocked.

- [ ] **Task 0.4:** Document the boolean in `docs/API_CONTRACT.md` or a 10-line note under the spec. Stop. Do not build Flutter yet if this flag is wrong.

**Verify:** `pytest tests/test_day_status.py -q`

---

## Phase 1 — Flutter shell (no blocking)

- [ ] **Task 1.1:** Create `packages/calt-device-gate` Flutter app: one screen, server URL, JWT field, poll `day-status` every 30s.

- [ ] **Task 1.2:** Show `device_gate.unlocked` and remaining minutes. Offline banner when poll fails.

- [ ] **Task 1.3:** MethodChannel stub `GateHost.getForeground()` returning `"none"` so the Dart/native split exists.

**Verify:** Run on emulator; toggle PC gate; UI flips without native overlay.

---

## Phase 2 — Android overlay (the product)

- [ ] **Task 2.1:** Kotlin Accessibility service + system overlay permission. Owner-editable JSON: `allow`, `distraction`, `porn` package names.

- [ ] **Task 2.2:** Loop: if foreground in `porn` → overlay always. If in `distraction` and not `unlocked` → overlay. Allow-list never overlaid.

- [ ] **Task 2.3:** After `unlocked`, Flutter “5 minutes” sets native `allowUntil = now+300s` for **non-porn** only.

- [ ] **Task 2.4:** Fail closed: if last successful poll > 2 min and last state was locked → treat as locked.

**Verify:** YouTube blocked until PC unlock; 5‑min works after; porn never gets 5‑min.

---

## Phase 3 — Android porn DNS (backstop)

- [ ] **Task 3.1:** Optional VpnService or Private DNS instructions + in-app host list (reuse PC porn hosts if already in-repo).

- [ ] **Task 3.2:** Document that YouTube **app** is overlay, not DNS.

**Verify:** Browser to a porn host fails; YouTube app still overlay.

---

## Phase 4 — iOS / iPad (after Android is in-pocket)

- [ ] **Task 4.1:** Request Family Controls entitlement; shield distraction apps while `unlocked == false`.

- [ ] **Task 4.2:** DNS/web-content filter for porn. Document Screen Time fallback if entitlement delayed.

- [ ] **Task 4.3:** Map 5‑min rest to whatever Apple allows; do not fake Android overlay.

**Verify:** Owner iPhone/iPad: shields until PC unlock; porn web filtered.

---

## Phase 5 — Ops

- [ ] **Task 5.1:** README: Tailscale vs LAN, OEM battery whitelist (Xiaomi), uninstall/disable Accessibility warning.

- [ ] **Task 5.2:** Do not replace `packages/calt-android-tracker`; link both from `docs/CALT_ANDROID_DOWNLOAD.md` when an APK exists.

---

## Time (solo, this lane only)

| Phase | Calendar |
|-------|----------|
| 0 PC flag | 1–2 days |
| 1 Flutter shell | 3–5 days |
| 2 Android overlay | 2–3 weeks |
| 3 DNS | ~1 week |
| 4 iOS | 2–3 months after 2 |
| 5 Ops | a few days |

**v1 done** = Phase 0–2 (3 optional) on the owner’s Android.  
**Platform done** = Phase 4 as well.  
PC study app does **not** wait on this plan.

---

## Suggested first commit when work starts

`feat(gate): add device_gate.unlocked to day-status`

Then Flutter. Native overlay last in Phase 2 so the flag is never guessed in Dart.
