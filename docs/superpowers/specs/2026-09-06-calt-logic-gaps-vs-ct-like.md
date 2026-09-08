# Logic gaps: CT-*like* behavior vs CALT native (our decisions)

**Date:** 2026-09-06  
**Method:** Same *kind* of system (native Windows service + UI + local DB).  
**Not:** Reading or copying Cold Turkey files. Gaps = product behaviors; fills = original CALT code.

## How we use this

1. List what a mature desktop blocker *does* (public product shape).
2. Compare to CALT C++ / Python today.
3. For each gap: **own** (C++ / Python / later / never) + decision.

## Matrix

| # | CT-like logic | CALT today | Gap? | Our decision | Fill |
|---|---------------|------------|------|--------------|------|
| L1 | Service stays up after UI close | C++ service / console | Install still manual | Keep C++; Admin install script | Scripts exist |
| L2 | Kill blocked apps by exe name | `kill.cpp` | Yes: browsers always protected; path/case | Protect only OS + self + `python*` so API lives; kill if listed | **This pass** |
| L3 | Respect temporary unlock | `gate_locked` from Python | Soft if publish stale | Trust snapshot; unlocked ⇒ `gate_locked=0` | Already via publish |
| L4 | Track “what was focused” | N3 session writer | Idle/sleep/max were missing | Mirror Python thresholds in C++ | Done prior pass |
| L5 | Split browser by site-ish signal | exe-only before | Yes | `exe\|site` from title | Done prior pass |
| L6 | Rules edited in UI, enforced in service | Web Dashboard → SQLite → C++ | OK | Python compute, C++ enforce | Locked architecture |
| L7 | Website SoftLand | Extension → `:8000` | Different from CT | Keep extension; never CT filter driver | Keep |
| L8 | Study stack | CALT webapp | N/A (not CT) | Stay Python | Keep |
| L9 | See that a kill happened | Silent TerminateProcess | Yes | Append `enforcer_kills.log` | **This pass** |
| L10 | Normalize block list (`Steam.exe` / paths) | Exact basename match | Partial | Basename + lower + optional `.exe` | **This pass** |
| L11 | Category / productive score on sessions | `category` NULL native | Yes | Later: Python backfill or light heuristic | Later |
| L12 | Incubation / earned break | Python `break_reward` | OK for study-first | Stay Python; C++ only reads incubation flag | Keep |
| L13 | Anti-tamper / kernel filters | None | Huge | **Never** clone CT; service + Task Scheduler enough | Out of scope |
| L14 | Comms when API down | Last snapshot kept | Soft | Keep last `enforcer_runtime`; no kill if never published | Keep |

## Fill priority (our order)

1. **L2 + L9 + L10** — kill correctness + visibility (this pass)  
2. L11 category — after live QA  
3. L1 verify install on owner machine  
4. L13 never
