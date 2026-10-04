# Focus QA automation suite — design

**Date:** 2026-09-14  
**Status:** Approved by owner (“combine all / do it”)  
**Scope:** SoftLand + Arm + gateway control-plane + Focus UI smoke, one runner, one rich report.

## Goal

Single automation entrypoint that runs **positive, edge, and negative** cases across:

1. SoftLand decide (fixture + live)
2. Arm match + optional live fixture kills
3. Gateway day-loop / reward / unlock / SoftLand patch (snapshot/restore)
4. Focus UI smoke (served `dist-focus`, screenshots)

…and emits a **QA-style report**: case id, title, steps, expected, actual, error code, screenshot paths, PASS/FAIL/SKIP.

## Architecture

```text
focus_qa_suite.py
  ├─ model: CaseResult (steps[], error_code, screenshots[])
  ├─ softland: fixture matrix + negatives/edges
  ├─ arm: unit + live (opt-in)
  ├─ gateway: status/day/reward/unlock negatives (snapshot/restore)
  ├─ ui: serve dist-focus + HTTP/DOM smoke + PIL screenshots
  └─ report: JSON + Markdown (+ HTML index with image links)
```

## Error codes

| Code | Meaning |
|------|---------|
| `OK` | Pass |
| `E100` | SoftLand action mismatch |
| `E101` | SoftLand reason mismatch |
| `E110` | msg_host / decide transport error |
| `E200` | Arm unit match misfire |
| `E210`/`E211` | Arm live kill miss / safe killed |
| `E300` | Gateway timeout / unreachable |
| `E301` | Gateway unexpected response |
| `E302` | Negative: expected reject, got ok |
| `E400` | Sync mismatch JSON↔SQLite |
| `E500`/`E501` | UI load / assertion fail |
| `E900` | Unexpected exception |

## Safety

- Live SoftLand/Arm mutations always **snapshot → restore**.
- Arm kills only disposable `calt_test_*` fixtures (`--arm-kills`).
- Gateway reward/day-pass negatives prefer **read-only** or **self-cancelling** mutations.
- UI smoke does not click SoftLand ON / Arm ON without restore path.

## Out of scope (v1)

- Full Playwright install requirement (optional; HTML serve + PIL screenshots baseline)
- Device-block host porn path
- Study `:8000` content
