import type { PlannerBlock } from "../../api/plannerClient";

export type OvercommitCheck = {
  plannedMinutes: number;
  goalMinutes: number;
  suggestedFocusHours: number | null;
  capacityMinutes: number;
  level: "ok" | "tight" | "over";
  message: string;
};

export function sumPlannedMinutes(blocks: PlannerBlock[]): number {
  return blocks.reduce((sum, b) => {
    if (b.status === "done" || b.status === "cancelled" || b.status === "rolled") return sum;
    return sum + (b.planned_minutes || b.remaining_minutes || 0);
  }, 0);
}

export function checkPlanOvercommit(opts: {
  blocks: PlannerBlock[];
  dailyGoalMinutes: number;
  suggestedFocusHours?: number | null;
  wakingHours?: number;
  lockedMinutes?: number;
}): OvercommitCheck {
  const plannedMinutes = sumPlannedMinutes(opts.blocks);
  const goalMinutes = Math.max(15, opts.dailyGoalMinutes || 240);
  const suggested = opts.suggestedFocusHours ?? null;
  const capacityMinutes = Math.round(
    (suggested != null && suggested > 0
      ? suggested * 60
      : Math.max(goalMinutes, (opts.wakingHours ?? 16) * 60 - (opts.lockedMinutes ?? 0))),
  );
  const ratio = plannedMinutes / Math.max(1, capacityMinutes);
  let level: OvercommitCheck["level"] = "ok";
  let message = "Plan fits today's capacity.";
  if (ratio > 1.05) {
    level = "over";
    message = `Planned ${(plannedMinutes / 60).toFixed(1)}h exceeds capacity ~${(capacityMinutes / 60).toFixed(1)}h — trim blocks or lower the focus target.`;
  } else if (ratio > 0.92) {
    level = "tight";
    message = `Plan is tight: ${(plannedMinutes / 60).toFixed(1)}h planned vs ~${(capacityMinutes / 60).toFixed(1)}h capacity.`;
  }
  return {
    plannedMinutes,
    goalMinutes,
    suggestedFocusHours: suggested,
    capacityMinutes,
    level,
    message,
  };
}
