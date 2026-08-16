/** Local planning prefs — mirrors ProductivityGoalsPanel localStorage pattern. */

const LS_KEY = "productivity:planning:v1";

export type PlanningPrefs = {
  /** When true, login calls POST /api/planner/routines/auto-apply-today once/day. Default off. */
  autoApplyRoutinesOnLogin: boolean;
};

export const DEFAULT_PLANNING_PREFS: PlanningPrefs = {
  autoApplyRoutinesOnLogin: false,
};

export function loadPlanningPrefs(): PlanningPrefs {
  try {
    const raw = localStorage.getItem(LS_KEY);
    if (!raw) return { ...DEFAULT_PLANNING_PREFS };
    const parsed = JSON.parse(raw) as Partial<PlanningPrefs>;
    return {
      autoApplyRoutinesOnLogin:
        typeof parsed.autoApplyRoutinesOnLogin === "boolean"
          ? parsed.autoApplyRoutinesOnLogin
          : DEFAULT_PLANNING_PREFS.autoApplyRoutinesOnLogin,
    };
  } catch {
    return { ...DEFAULT_PLANNING_PREFS };
  }
}

export function savePlanningPrefs(prefs: PlanningPrefs): void {
  try {
    localStorage.setItem(LS_KEY, JSON.stringify(prefs));
  } catch {
    /* private mode / quota — ignore */
  }
}

export function setAutoApplyRoutinesOnLogin(on: boolean): PlanningPrefs {
  const next = { ...loadPlanningPrefs(), autoApplyRoutinesOnLogin: on };
  savePlanningPrefs(next);
  return next;
}
