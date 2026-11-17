/**
 * Plain-language “tomorrow’s one fix” from day numbers — no “focus quality” scores.
 */
import type { BodyCareDay } from "../api/bodyCareClient";
import type { AdherenceSummary, PlanDriftSummary } from "../api/plannerClient";

export type DayWrapInsightInput = {
  adherence: AdherenceSummary | null;
  planDrift: PlanDriftSummary | null;
  body: BodyCareDay | null;
  sleepHours: number | null;
  productiveMinutes: number | null;
};

export type DayWrapInsight = {
  /** Short headline for the wrap. */
  headline: string;
  /** Single actionable line for tomorrow. */
  tomorrowFix: string;
  /** Why we picked that fix (one sentence). */
  why: string;
};

function mins(n: number | null | undefined): number {
  return typeof n === "number" && Number.isFinite(n) ? n : 0;
}

export function buildDayWrapInsight(input: DayWrapInsightInput): DayWrapInsight {
  const a = input.adherence;
  const planned = mins(a?.planned_minutes);
  const onPlan = mins(a?.effective_focus_minutes);
  const distracted = mins(a?.distraction_on_plan_minutes);
  const gap = Math.max(0, planned - onPlan);
  const sitM = mins(input.body?.sit_hint_sec) / 60;
  const standM = mins(input.body?.stand_hint_sec) / 60;
  const sleep = input.sleepHours;
  const driftLine = input.planDrift?.lines?.[0] || null;

  // Priority: clear, actionable, no jargon.
  if (distracted >= 35 && planned > 0) {
    return {
      headline: "Plan time leaked to distraction",
      tomorrowFix: `SoftLand earlier — you lost ~${Math.round(distracted)}m during plan blocks.`,
      why: "Off-plan apps/sites ate into blocks you had scheduled.",
    };
  }

  if (gap >= 45 && planned > 0) {
    const pct = a?.adherence_pct != null ? Math.round(a.adherence_pct) : null;
    return {
      headline: pct != null ? `Plan done ~${pct}%` : "Plan under-delivered",
      tomorrowFix: driftLine
        ? `Tomorrow: ${driftLine}`
        : `Protect ~${Math.round(gap)}m you planned but didn’t land on-plan.`,
      why: "Scheduled blocks didn’t get enough on-plan time.",
    };
  }

  if (sitM >= 90 && standM < 15 && (input.body?.samples || 0) > 10) {
    return {
      headline: "Long sit day",
      tomorrowFix: `Stand breaks earlier — ~${sitM.toFixed(0)}m sitting vs ~${standM.toFixed(0)}m standing.`,
      why: "Body-care camera saw mostly sitting.",
    };
  }

  if (sleep != null && sleep > 0 && sleep < 6.2) {
    return {
      headline: "Short sleep",
      tomorrowFix: `Aim for an earlier bed — last night ~${sleep.toFixed(1)}h.`,
      why: "Wearable/sleep mirror shows a short night.",
    };
  }

  if (driftLine) {
    return {
      headline: "One plan miss stood out",
      tomorrowFix: `Tomorrow: ${driftLine}`,
      why: "From today’s plan-vs-actual drift.",
    };
  }

  const prod = mins(input.productiveMinutes);
  if (planned <= 0 && prod >= 60) {
    return {
      headline: "Worked without a plan",
      tomorrowFix: "Sketch 2–3 blocks tomorrow morning before Confirm.",
      why: "You put in time, but nothing was scheduled to protect.",
    };
  }

  return {
    headline: planned > 0 ? "Day held together" : "Light plan day",
    tomorrowFix: "Keep the same shape — small plan, SoftLand on, one stand break.",
    why: "No single leak dominated today.",
  };
}

export function fmtHoursFromMinutes(m: number | null | undefined): string {
  if (m == null || !Number.isFinite(m) || m <= 0) return "—";
  if (m < 60) return `${Math.round(m)}m`;
  return `${(m / 60).toFixed(1)}h`;
}
