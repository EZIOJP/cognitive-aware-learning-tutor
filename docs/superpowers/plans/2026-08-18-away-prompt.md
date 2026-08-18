# Away-from-Desk Prompt — Implementation Plan (deferred)

**Goal:** RescueTime-style prompt when user returns from idle: “Were you working away from the computer?”

**Architecture:** On idle return in `tracker_service.py`, if gap ≥ threshold and productive goal not met, enqueue tray toast or gate alert. User picks Working / Break / Ignore → optional manual time block or dismiss.

---

### Scope (when scheduled)

**Files (planned):**
- Modify: `backend/behavior/tracker_service.py` — detect idle→active transition
- Create: `backend/behavior/tracker_away_prompt.py` — Tk mini-dialog (reuse block_gui patterns)
- Modify: `backend/behavior/router.py` — POST log away response (optional manual session)

**Constraints:**
- Max one prompt per idle episode; respect `GATE_ALERT_SPEAK_GAP_S`
- Default gap: 10 minutes idle
- Do not double-count if user ignores

**Prerequisite:** Goals module for “goal not met” guard.

**Verify:** manual idle test on Windows tracker
