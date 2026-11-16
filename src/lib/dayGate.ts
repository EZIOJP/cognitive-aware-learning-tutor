/**
 * Morning / planning gate helpers.
 * Planning is required. Bible is morning, then afternoon (12:00), then evening (17:00).
 * SoftLand ≠ Arm.
 */
import type { FocusStatusSnapshot } from "./focusStatusBus";

export function localYmd(): string {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function localMinutes(): number {
  const d = new Date();
  return d.getHours() * 60 + d.getMinutes();
}

/** Planning phase cannot be turned off. */
export function planningEnabled(_status: FocusStatusSnapshot): boolean {
  return true;
}

type GoalsDates = {
  bible_afternoon_for_date?: string;
  bible_evening_for_date?: string;
};

function goalsOf(status: FocusStatusSnapshot): GoalsDates | undefined {
  return status.softland?.goals as GoalsDates | undefined;
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

export function afternoonBibleDone(status: FocusStatusSnapshot): boolean {
  const today = localYmd();
  const loop = status.dayLoop as { bible_afternoon_done?: boolean; date?: string } | null;
  if (loop?.bible_afternoon_done && (!loop.date || loop.date === today)) return true;
  return goalsOf(status)?.bible_afternoon_for_date === today;
}

export function eveningBibleDone(status: FocusStatusSnapshot): boolean {
  const today = localYmd();
  const loop = status.dayLoop as { bible_evening_done?: boolean; date?: string } | null;
  if (loop?.bible_evening_done && (!loop.date || loop.date === today)) return true;
  return goalsOf(status)?.bible_evening_for_date === today;
}

/** The bible reading that is due right now, or null when every due slot is done. */
export function dueBibleSlot(status: FocusStatusSnapshot): "morning" | "afternoon" | "evening" | null {
  if (!bibleDoneToday(status)) return "morning";
  const m = localMinutes();
  if (m >= 12 * 60 && !afternoonBibleDone(status)) return "afternoon";
  if (m >= 17 * 60 && !eveningBibleDone(status)) return "evening";
  return null;
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

/**
 * Routine and plan writes: a free day, or the initial planning of a new day
 * (today's plan is not confirmed yet). After Confirm or auto-confirm, locked.
 * No snapshot yet — let the enforcer decide.
 */
export function planEditsOpen(status: FocusStatusSnapshot, freeDay: boolean): boolean {
  if (freeDay) return true;
  if (!status.dayLoop && !status.softland?.goals) return true;
  return !planConfirmedToday(status);
}

/** A due Bible slot is unread, or today's plan is not confirmed yet. */
export function morningLockActive(status: FocusStatusSnapshot): boolean {
  if (status.dayLoop?.bedtime_active) return false;
  if (!status.dayLoop && !status.softland?.goals) return false;
  if (dueBibleSlot(status)) return true;
  if (!planConfirmedToday(status)) return true;
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

/** Where the shell must stay while a Bible slot or Confirm is still open. */
export function dayGateTarget(status: FocusStatusSnapshot): string | null {
  const due = dueBibleSlot(status);
  if (due) return `/bible?slot=${due}`;
  if (!planConfirmedToday(status)) return "/productivity?tab=plan";
  return null;
}

/** True when this route is allowed during the morning / Bible lock. */
export function dayGateAllowsPath(status: FocusStatusSnapshot, routeBlob: string): boolean {
  if (!morningLockActive(status)) return true;
  const blob = (routeBlob || "").toLowerCase();
  const due = dueBibleSlot(status);
  if (due) return blob.includes("/bible");
  return blob.includes("tab=plan");
}
