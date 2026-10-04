# Focus QA Automation Implementation Plan

> **For agentic workers:** Execute task-by-task. Checkboxes track progress.

**Goal:** Ship one Focus QA runner (SoftLand + Arm + gateway + UI smoke) with rich PASS/FAIL reports (steps, error codes, screenshots).

**Architecture:** New package under `scripts/desktop_tracker/run/focus_qa/` + thin `focus_qa_suite.py` entry. Reuse helpers from `block_mode_suite.py` where practical.

**Tech Stack:** Python 3, existing msg_host/gateway, PIL ImageGrab for screenshots, stdlib `http.server` for `dist-focus` UI smoke.

## Global Constraints

- SoftLand ON ≠ Arm
- SoftLand decide via msg_host, not Study `:8000`
- Snapshot/restore on live mutations
- No CT code; no commits unless asked

---

### Task 1: Model + error codes + report writer

- [ ] `focus_qa/model.py`, `error_codes.py`, `report.py` (MD + JSON + HTML)
- [ ] Screenshot helper (`screenshots.py`)

### Task 2: SoftLand + Arm suites (edges + negatives)

- [ ] Expand fixture cases; negative expectations documented
- [ ] Arm unit negatives; wire into runner

### Task 3: Gateway control-plane suite

- [ ] status/day/reward/loop reads
- [ ] Negative: bad unlock, bad payload
- [ ] Snapshot/restore around any write

### Task 4: UI smoke + screenshots

- [ ] Serve `dist-focus`; hit home/settings/blocker hash routes
- [ ] Capture screenshots per case / on fail

### Task 5: Entry script + run + export report

- [ ] `focus_qa_suite.py` CLI
- [ ] Run safe+live (arm-kills if fixtures exist)
- [ ] Write under `docs/superpowers/exports/`
