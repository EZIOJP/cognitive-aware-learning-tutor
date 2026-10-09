/**
 * Morning / planning gate helpers — session-first defaults.
 * SoftLand ≠ Arm. planning_enabled defaults false (Confirm-plan optional).
 */
import type { FocusStatusSnapshot } from "./focusStatusBus";

export function localYmd(): string {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

/** Explicit true only — missing/undefined means session-first (no Confirm phase). */
export function planningEnabled(status: FocusStatusSnapshot): boolean {
  if (typeof status.dayLoop?.planning_enabled === "boolean") {
    return status.dayLoop.planning_enabled;
  }
  const goals = status.softland?.goals as { planning_enabled?: boolean } | undefined;
  return goals?.planning_enabled === true;
}

export function bibleDoneToday(status: FocusStatusSnapshot): boolean {
  const today = localYmd();
  const goals = status.softland?.goals;
  if (goals?.bible_done) {
    const date = typeof goals.bible_done_for_date === "string" ? goals.bible_done_for_date : "";
    if (date === today) return true;
  }
  const loop = status.dayLoop;
  if (!loop?.bible_done) return false;
  const date = typeof loop.date === "string" ? loop.date : "";
  return !date || date === today;
}

export function planConfirmedToday(status: FocusStatusSnapshot): boolean {
  const today = localYmd();
  if (status.dayLoop?.plan_confirmed) {
    const date = typeof status.dayLoop.date === "string" ? status.dayLoop.date : "";
    if (!date || date === today) return true;
  }
  const goals = status.softland?.goals;
  if (!goals?.plan_confirmed) return false;
  const date =
    typeof goals.plan_confirmed_for_date === "string" ? goals.plan_confirmed_for_date : "";
  return date === today;
}

/** Bible pending, or Confirm-plan pending when planning is on. */
export function morningLockActive(status: FocusStatusSnapshot): boolean {
  if (status.dayLoop?.bedtime_active) return false;
  if (!status.dayLoop && !status.softland?.goals) return false;
  if (!bibleDoneToday(status)) return true;
  if (planningEnabled(status) && !planConfirmedToday(status)) return true;
  return false;
}

/**
 * SoftLand site/schedule/mode surgery: free day/pass OR morning lock cleared.
 * Arm / kill-list stay free-day only (callers use useFreeDay).
 */
export function softlandSurgeryOpen(status: FocusStatusSnapshot, freeDay: boolean): boolean {
  if (freeDay) return true;
  return !morningLockActive(status) && bibleDoneToday(status);
}
