import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Target } from "lucide-react";
import type { AdherenceSummary } from "../../api/plannerClient";
import type { StudyTask } from "../../api/plannerClient";
import {
  fetchProductivityPolicy,
  saveProductivityPolicy,
} from "../../api/behaviorClient";
import { isFocusDesktopShell } from "../../utils/focusDesktopShell";
import { focusDataUrl } from "../../utils/focusDataUrl";
import { enforcerNativeCmd, isFocusEnforcerBridgeAvailable } from "../../lib/enforcerNativeCmd";
import PlanRulesSettingsCue from "./PlanRulesSettingsCue";
import { GoalsTodayPlanBlocks } from "./GoalsTodayPlanBlocks";

/** Fixed system reward — not user-edited copy */
export const IMPLIED_FOCUS_REWARD =
  "Hit today's on-plan focus target — SoftLand watch sites open in free/reward. SoftLand ON ≠ Armed.";

async function loadDailyFocusHours(): Promise<number | null> {
  if (isFocusDesktopShell()) {
    try {
      const r = await fetch(focusDataUrl("softland_policy.json"), { cache: "no-store" });
      if (r.ok) {
        const j = (await r.json()) as { goals?: { daily_focus_minutes?: number } };
        const mins = Number(j.goals?.daily_focus_minutes);
        if (Number.isFinite(mins) && mins > 0) return goalMinutesToFocusHours(mins);
      }
    } catch {
      /* fall through */
    }
    return null;
  }
  try {
    const p = await fetchProductivityPolicy();
    return goalMinutesToFocusHours(p.daily_goal_minutes ?? 240);
  } catch {
    return null;
  }
}

async function saveDailyFocusHours(hours: number): Promise<void> {
  const minutes = focusHoursToGoalMinutes(hours);
  if (isFocusEnforcerBridgeAvailable()) {
    let goalsObj: Record<string, unknown> = {
      daily_focus_minutes: minutes,
      goal_met: false,
      bible_done: false,
    };
    try {
      const r = await fetch(focusDataUrl("softland_policy.json"), { cache: "no-store" });
      if (r.ok) {
        const j = (await r.json()) as { goals?: Record<string, unknown> };
        if (j.goals && typeof j.goals === "object") {
          goalsObj = { ...j.goals, daily_focus_minutes: minutes };
        }
      }
    } catch {
      /* use defaults */
    }
    const res = await enforcerNativeCmd("softland.patch_goals", { goals: goalsObj });
    if (!res?.ok) {
      throw new Error(typeof res?.error === "string" ? res.error : "Enforcer rejected daily focus");
    }
    return;
  }
  if (isFocusDesktopShell()) {
    // Design host / no pipe — localStorage only (already persisted by the panel).
    return;
  }
  await saveProductivityPolicy({ daily_goal_minutes: minutes });
}

const LS_KEY = "productivity:goals:v1";
export const GOALS_UPDATED_EVENT = "productivity:goals-updated";

export type ExtraGoal = {
  id: string;
  title: string;
  done: boolean;
  /** Minutes this task claims from the daily focus goal (allocator). */
  minutes: number;
};

export type ProductivityGoals = {
  focusHoursPerDay: number;
  weeklyFocusHours: number;
  mainGoal: string;
  reward: string;
  extraGoals: ExtraGoal[];
  studyTasks: StudyTask[];
  weekKey?: string;
};

const DEFAULT_GOALS: ProductivityGoals = {
  focusHoursPerDay: 4,
  weeklyFocusHours: 24,
  mainGoal: "Complete the Scaler AI/ML course — daily lessons + practice before entertainment.",
  reward: IMPLIED_FOCUS_REWARD,
  extraGoals: [],
  studyTasks: [],
};

function newExtraId(): string {
  return `g-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`;
}

function newStudyTaskId(): string {
  return `task-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`;
}

function currentWeekKey(): string {
  const d = new Date();
  const target = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
  const dayNum = target.getUTCDay() || 7;
  target.setUTCDate(target.getUTCDate() + 4 - dayNum);
  const yearStart = new Date(Date.UTC(target.getUTCFullYear(), 0, 1));
  const weekNo = Math.ceil(((target.getTime() - yearStart.getTime()) / 86400000 + 1) / 7);
  return `${target.getUTCFullYear()}-W${String(weekNo).padStart(2, "0")}`;
}

function normalizeStudyTasks(raw: unknown): StudyTask[] {
  if (!Array.isArray(raw)) return [];
  return raw
    .filter((t): t is StudyTask => Boolean(t && typeof t === "object"))
    .map((t) => ({
      id: String(t.id || newStudyTaskId()),
      title: String(t.title || "Study").trim(),
      minutes: Math.max(25, Number(t.minutes) || 60),
      allowHosts: Array.isArray(t.allowHosts) ? t.allowHosts.map(String) : [],
      blockCategories: Array.isArray(t.blockCategories) ? t.blockCategories.map(String) : [],
    }))
    .filter((t) => t.title);
}

type Props = {
  adherence: AdherenceSummary | null;
  /** Hours already locked by routines / blocks on the selected day */
  lockedHours?: number;
  /** Assumed waking window for capacity hint (default 16h) */
  wakingHours?: number;
  /** Watch sleep score 0–100 for recovery-based capacity hint */
  sleepScore?: number | null;
  onGoalsTextChange?: (text: string) => void;
  /** Fired when the user explicitly Saves — marks the Plan stepper Goals step complete */
  onConfirmed?: () => void;
  /** After apply / plan block changes — refresh calendar mirrors */
  onPlanBlocksChange?: () => void;
  /** Bump when parent reloads planner */
  planRefreshKey?: number;
  /** Switch Productivity tab to Calendar (avoids Router Link crash in Focus). */
  onOpenCalendar?: () => void;
  /** Plan step Confirm / Back / Next — folded into this card */
  footer?: ReactNode;
};

export function focusHoursToGoalMinutes(hours: number): number {
  return Math.min(960, Math.max(15, Math.round(Number(hours) * 60)));
}

export function goalMinutesToFocusHours(mins: number): number {
  return Math.round((Math.max(15, Number(mins) || 240) / 60) * 10) / 10;
}

export function persistProductivityGoals(goals: ProductivityGoals): void {
  localStorage.setItem(LS_KEY, JSON.stringify(goals));
  window.dispatchEvent(new CustomEvent(GOALS_UPDATED_EVENT, { detail: goals }));
}

export function loadProductivityGoals(): ProductivityGoals {
  try {
    const raw = localStorage.getItem(LS_KEY);
    if (!raw) return { ...DEFAULT_GOALS };
    const parsed = { ...DEFAULT_GOALS, ...JSON.parse(raw) } as ProductivityGoals;
    if (!Array.isArray(parsed.extraGoals)) parsed.extraGoals = [];
    parsed.extraGoals = parsed.extraGoals
      .filter((g) => g && typeof g.title === "string")
      .map((g) => ({
        id: g.id || newExtraId(),
        title: g.title,
        done: Boolean(g.done),
        minutes: Math.max(5, Math.min(480, Number((g as ExtraGoal).minutes) || 25)),
      }));
    parsed.studyTasks = normalizeStudyTasks(parsed.studyTasks);
    const wk = currentWeekKey();
    if (parsed.weekKey && parsed.weekKey !== wk) {
      parsed.weekKey = wk;
    } else if (!parsed.weekKey) {
      parsed.weekKey = wk;
    }
    if (
      parsed.mainGoal === "Finish AI/ML and Scaler work before entertainment." ||
      !parsed.mainGoal?.trim()
    ) {
      parsed.mainGoal = DEFAULT_GOALS.mainGoal;
    }
    if (
      !parsed.reward?.trim() ||
      parsed.reward === "Guilt-free break after hitting the focus target." ||
      parsed.reward.startsWith("Unlock games / free time")
    ) {
      parsed.reward = IMPLIED_FOCUS_REWARD;
    }
    return parsed;
  } catch {
    return { ...DEFAULT_GOALS };
  }
}

export function formatGoalsForPrompt(goals: ProductivityGoals): string {
  const extras = goals.extraGoals.filter((g) => g.title.trim());
  const extraBlock =
    extras.length === 0
      ? ""
      : ` Extra goals/todos: ${extras
          .map((g) => `${g.done ? "[done] " : ""}${g.title.trim()}`)
          .join("; ")}.`;
  const tasks = goals.studyTasks || [];
  const taskBlock =
    tasks.length === 0
      ? ""
      : ` Study tasks: ${tasks
          .map((t) => {
            const allow = (t.allowHosts || []).join(", ").slice(0, 120);
            const block = (t.blockCategories || []).join(", ").slice(0, 80);
            return `${t.title} (${t.minutes}m; allow ${allow || "study sites"}; block ${block || "distractions"})`;
          })
          .join(" | ")}.`;
  return `${goals.mainGoal} Daily effective-focus target: ${goals.focusHoursPerDay}h. Weekly target: ${goals.weeklyFocusHours}h. Reward: ${IMPLIED_FOCUS_REWARD}.${extraBlock}${taskBlock}`;
}

export function ProductivityGoalsPanel({
  adherence,
  onGoalsTextChange,
  onPlanBlocksChange,
  planRefreshKey = 0,
  onOpenCalendar,
  footer,
}: Props) {
  const [goals, setGoals] = useState<ProductivityGoals>(() => loadProductivityGoals());
  const [saveError, setSaveError] = useState<string | null>(null);
  const [focusHydrated, setFocusHydrated] = useState(false);
  const lastSavedFocusHours = useRef<number | null>(null);

  const effectiveHours = (adherence?.effective_focus_minutes ?? 0) / 60;

  const goalsText = useMemo(() => formatGoalsForPrompt(goals), [goals]);

  useEffect(() => {
    onGoalsTextChange?.(goalsText);
  }, [goalsText, onGoalsTextChange]);

  useEffect(() => {
    const onUpdated = () => setGoals(loadProductivityGoals());
    window.addEventListener(GOALS_UPDATED_EVENT, onUpdated);
    return () => window.removeEventListener(GOALS_UPDATED_EVENT, onUpdated);
  }, []);

  useEffect(() => {
    let cancelled = false;
    void loadDailyFocusHours().then((hours) => {
      if (cancelled) return;
      if (hours != null) {
        lastSavedFocusHours.current = hours;
        setGoals((prev) =>
          prev.focusHoursPerDay === hours ? prev : { ...prev, focusHoursPerDay: hours },
        );
      } else {
        lastSavedFocusHours.current = loadProductivityGoals().focusHoursPerDay;
      }
      setFocusHydrated(true);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    localStorage.setItem(
      LS_KEY,
      JSON.stringify({ ...goals, reward: IMPLIED_FOCUS_REWARD }),
    );
  }, [goals]);

  useEffect(() => {
    if (!focusHydrated) return;
    if (lastSavedFocusHours.current === goals.focusHoursPerDay) return;
    const t = window.setTimeout(() => {
      void (async () => {
        try {
          await saveDailyFocusHours(goals.focusHoursPerDay);
          lastSavedFocusHours.current = goals.focusHoursPerDay;
          setSaveError(null);
        } catch (e: unknown) {
          setSaveError(e instanceof Error ? e.message : "Could not update daily focus");
        }
      })();
    }, 450);
    return () => window.clearTimeout(t);
  }, [goals.focusHoursPerDay, focusHydrated]);

  return (
    <div className="goals-panel space-y-5">
      <header className="flex items-center justify-between gap-3">
        <h3 className="font-semibold text-sm flex items-center gap-2">
          <Target size={15} className="text-emerald-300" aria-hidden />
          Goals
        </h3>
        {saveError ? <p className="text-[11px] text-rose-300">{saveError}</p> : null}
      </header>

      <GoalsTodayPlanBlocks
        focusHours={goals.focusHoursPerDay}
        onFocusHoursChange={(n) => setGoals({ ...goals, focusHoursPerDay: n })}
        studyTasks={goals.studyTasks}
        refreshKey={planRefreshKey}
        onChanged={onPlanBlocksChange}
        onOpenCalendar={onOpenCalendar}
        extraGoals={goals.extraGoals}
        onExtraGoalsChange={(extraGoals) => setGoals({ ...goals, extraGoals })}
        effectiveHours={effectiveHours}
      />

      {isFocusDesktopShell() ? <PlanRulesSettingsCue /> : null}

      {footer}
    </div>
  );
}

export default ProductivityGoalsPanel;
