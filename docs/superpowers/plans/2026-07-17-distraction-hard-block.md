# Distraction Hard-Block Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Hard-kill games + custom exes via desktop tracker until daily productive minutes hit the user goal; Cold Turkey remains for sites.

**Architecture:** Extend `productivity_policies` with gate fields; `distraction_gate.py` computes locked/unlocked from today’s TrackedSessions; tracker poll kills matching pids; Productivity UI edits lists + shows status.

**Tech stack:** FastAPI, SQLAlchemy, Alembic, psutil, React ProductivityPolicyPanel.

---

## File map

| File | Responsibility |
|------|----------------|
| `alembic/versions/0026_distraction_hard_block.py` | New policy columns |
| `backend/models/productivity_policy.py` | ORM fields |
| `backend/behavior/productivity_policy.py` | serialize/update defaults |
| `backend/behavior/distraction_gate.py` | Gate math, exe match, kill helpers |
| `backend/behavior/tracker_service.py` | Enforce on poll |
| `backend/behavior/router.py` | `GET /api/behavior/distraction-gate` |
| `src/api/behaviorClient.ts` | Types + fetch gate |
| `src/components/productivity/ProductivityPolicyPanel.tsx` | UI |
| `docs/HLD.md` / `docs/LLD.md` | Short notes |
| `tests/test_distraction_gate.py` | Unit tests |

---

### Task 1: Migration + model + serialize

Add columns; update `default_policy_dict` / `serialize_policy` / `update_policy`.

**Verify:** `alembic upgrade head`; policy GET includes new fields.

### Task 2: distraction_gate module + tests

`should_hard_block(exe, category, policy)`, `compute_gate(db, user_id)`, `terminate_blocked_process(pid)`.

**Verify:** pytest `tests/test_distraction_gate.py`.

### Task 3: API + tracker enforcement

Endpoint + poll hook (refresh gate ~30s).

**Verify:** gate JSON when enabled; manual smoke with fake exe match.

### Task 4: Frontend

Toggle, goal minutes, gaming checkbox, custom exe list, status line.

### Task 5: Docs

HLD Loop E + LLD behavior subsection.
