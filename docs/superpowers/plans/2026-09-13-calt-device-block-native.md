# CALT Device lock native — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans or subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Move Device lock (hosts porn) off Study `:8000` into `calt_enforcer` gateway + elevated CLI so Focus Filters works with Python stopped.

**Architecture:** JSON SoT under `data/productivity/behavior/`; shared confirm+enabled gate; Global hosts mutex; scrape on worker thread only; bats call same exe with `--confirm`.

**Tech Stack:** C++20 (`calt_enforcer`), WinHTTP, Focus WebView2 bridge, React Filters panel.

**Spec:** [2026-09-12-calt-device-block-native-design.md](../specs/2026-09-12-calt-device-block-native-design.md)

## Global Constraints

- SoftLand/Arm untouched; Device lock never sets `hard_block_armed`
- Confirm phrase exact: `DEVICE LOCK` (shared gate for save/apply/remove/CLI)
- No scrape on kill/SoftLand tick; no auto-scrape-on-tick
- Mutex: `Global\CALT_DeviceBlockHosts` — Administrators + enforcer account, not Everyone
- Torn hosts section (BEGIN without END) → refuse write
- Legacy Python writers retired at cutover; legacy files kept on disk
- Commits only if user asks

## File map

| File | Role |
|------|------|
| `calt-focus/backend/calt_enforcer/src/device_block_*.cpp/h` | Settings, migrate, hosts, list/scrape, shared gate |
| `cmd_gateway.cpp` | Ops |
| `main.cpp` | CLI flags |
| `CMakeLists.txt` | Wire sources + winhttp |
| `scripts/device_block_*.bat` | Elevate + native CLI + confirm |
| `webview_host.cpp` | Pass confirm to bat |
| `DeviceBlockPanel.tsx` + thin client | Gateway + bat confirm |
| `tracker_porn_block.py`, Study routes | No-op / stub |
| `docs/BLOCKING_RULES.md` | Native SoT |

## Tasks

### Task 1: Settings + migration + shared confirm gate
- Create settings load/save under productivity path; marker migrate from `data/behavior/`
- `DeviceBlockTrySetEnabled(want, confirm, err)` — single gate

### Task 2: Hosts RMW + Global mutex + DoH/DNS
- Port markers/merge; refuse unbalanced markers; apply/remove under mutex

### Task 3: Seeds + cache + async scrape
- Port porn/watch/social seeds; WinHTTP allowlisted scrape; worker + 20s timeout; union seeds

### Task 4: Gateway ops + CLI
- `device_block.status|save|apply|remove|refresh_list`
- `--device-block-apply|remove|refresh` + `--confirm`

### Task 5: Focus + bats
- `enforcerNativeCmd`; `run_repo_bat` + confirm args; bats native-only

### Task 6: Retire Python writers + rebuild + smoke
- Tracker no-op; routes stub; `:8000` stopped smoke checklist

## Acceptance (must-not-fail)

1. Hosts merge unit-tested / string smoke; unbalanced markers refuse
2. Elevated `--device-block-remove` without confirm refuses
3. Confirm survives Focus → webview → bat → RunAs → exe
4. No Python hosts write after cutover
5. Filters works with Study stopped (enforcer up)
