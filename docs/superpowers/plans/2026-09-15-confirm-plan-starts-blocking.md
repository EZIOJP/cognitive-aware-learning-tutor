# Confirm plan starts blocking — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Confirm plan turns SoftLand+Arm on; no plan ledger credit; goal-met opens free until midnight; free/reward day claimable at plan window after Bible.

**Architecture:** Enforcer `day.confirm_plan` mutates SoftLand SoT + `enforcer_policy.json`. Tick grants goal free. Focus Confirm UI adds REWARD/PASS.

**Tech stack:** C++ enforcer (`day_loop.cpp`, `day_rollup.cpp`, `cmd_gateway.cpp`), Focus React (`ConfirmPlanButton.tsx`, `dayLoopClient.ts`).

---

### Task 1: Confirm plan arms SoftLand + Arm

**Files:** `calt-focus/backend/calt_enforcer/src/day_loop.cpp`, `day_loop.h`

- Require `bible_done` else `bible_required`
- Set `softland_enabled=true`, save/publish
- Load/write Arm snapshot armed+locked (preserve exes/lock_mode)
- Delete plan_confirmed 10‑min ledger block
- extraOut includes softland_enabled + armed

### Task 2: Goal-met EOD free in tick

**Files:** `day_loop.cpp`

- Once/day when plan_confirmed && tracked ≥ daily_focus_minutes: set goal_met, free_until EOD, runtime `goal_free_granted_date`

### Task 3: Rollup threshold from policy

**Files:** `day_rollup.cpp` — read `daily_focus_minutes` from softland mirror (default 180)

### Task 4: Free-day claim path

**Files:** `cmd_gateway.cpp` reward.claim + day_pass spent — SoftLand on + plan_confirmed

### Task 5: Focus plan window UI

**Files:** `ConfirmPlanButton.tsx`, `dayLoopClient.ts` — REWARD / PASS buttons after Bible

### Task 6: Build + smoke

- Build enforcer; gateway confirm_plan; get_mode youtube; redeploy if service locked
