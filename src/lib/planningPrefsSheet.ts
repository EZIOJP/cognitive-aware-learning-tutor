/** Open Planning prefs sheet during Plan gate (no Settings navigation). */

export const PLANNING_PREFS_OPEN_EVENT = "calt:planning-prefs:open";
export const PLANNING_PREFS_CLOSE_EVENT = "calt:planning-prefs:close";

export function openPlanningPrefsSheet(): void {
  try {
    window.dispatchEvent(new CustomEvent(PLANNING_PREFS_OPEN_EVENT));
  } catch {
    /* ignore */
  }
}

export function closePlanningPrefsSheet(): void {
  try {
    window.dispatchEvent(new CustomEvent(PLANNING_PREFS_CLOSE_EVENT));
  } catch {
    /* ignore */
  }
}
