/**
 * Focus shell mirrors via calt-data.app (WebView2) or /calt-data (dev:focus :5174).
 * Phase 5: day_rollup + enforcer_status for core stats / Arm display offline.
 */
import type { DesktopStats, GoalsStatusResponse } from "./behaviorClient";
import { isFocusDesktopShell } from "../utils/focusDesktopShell";
import { focusDataUrl } from "../utils/focusDataUrl";

export type DayRollupMirror = {
  schema_version?: number;
  local_date?: string;
  updated_at?: string;
  productive_minutes?: number;
  productive_seconds?: number;
  threshold?: number;
  session_count?: number;
  day_unlocked?: boolean;
  goal_met?: boolean;
  source?: string;
};

export type EnforcerStatusMirror = {
  owns?: boolean;
  armed?: boolean;
  lock_present?: boolean;
  locked?: boolean;
  pid?: number;
  service_running?: boolean;
  softland_or_armed?: boolean;
  updated_at?: string;
};

function todayIsoLocal(): string {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function productiveSecondsFromRollup(r: DayRollupMirror | null | undefined): number {
  if (!r) return 0;
  if (typeof r.productive_seconds === "number" && Number.isFinite(r.productive_seconds)) {
    return Math.max(0, Math.floor(r.productive_seconds));
  }
  if (typeof r.productive_minutes === "number" && Number.isFinite(r.productive_minutes)) {
    return Math.max(0, Math.round(r.productive_minutes * 60));
  }
  return 0;
}

/** Fetch day_rollup.json when running inside calt_focus WebView2; else null. */
export async function fetchDayRollupMirror(): Promise<DayRollupMirror | null> {
  if (!isFocusDesktopShell()) return null;
  try {
    const res = await fetch(focusDataUrl("day_rollup.json"), { cache: "no-store" });
    if (!res.ok) return null;
    const j = (await res.json()) as DayRollupMirror;
    return j && typeof j === "object" ? j : null;
  } catch {
    return null;
  }
}

/** Fetch enforcer_status.json for offline Arm/owns when Focus dashboard API is down. */
export async function fetchEnforcerStatusMirror(): Promise<EnforcerStatusMirror | null> {
  if (!isFocusDesktopShell()) return null;
  try {
    const res = await fetch(focusDataUrl("enforcer_status.json"), { cache: "no-store" });
    if (!res.ok) return null;
    const j = (await res.json()) as EnforcerStatusMirror;
    return j && typeof j === "object" ? j : null;
  } catch {
    return null;
  }
}

/** Map rollup → DesktopStats shape for GlanceBar (zeros OK when missing). */
export function dayRollupToDesktopStats(r: DayRollupMirror | null): DesktopStats {
  const productive = productiveSecondsFromRollup(r);
  return {
    sessions: [],
    total_seconds: productive,
    avg_productivity_score: 0,
    productive_seconds: productive,
    distracting_seconds: 0,
    source: r?.source || "day_rollup",
    date: (r?.local_date && String(r.local_date)) || todayIsoLocal(),
    tracker_running: Boolean(r?.session_count && r.session_count > 0),
    last_event_at: r?.updated_at ?? null,
  };
}

/** Empty / zero desktop stats — Focus shell when API + mirror both unavailable. */
export function emptyDesktopStats(day?: string): DesktopStats {
  return {
    sessions: [],
    total_seconds: 0,
    avg_productivity_score: 0,
    productive_seconds: 0,
    distracting_seconds: 0,
    source: "offline",
    date: day || todayIsoLocal(),
    tracker_running: false,
    last_event_at: null,
  };
}

/** Map rollup → GoalsStatus for GlanceBar daily goal ring (tolerant). */
export function dayRollupToGoalsStatus(r: DayRollupMirror | null): GoalsStatusResponse | null {
  if (!r) return null;
  const productive = productiveSecondsFromRollup(r);
  const thresholdMin =
    typeof r.threshold === "number" && Number.isFinite(r.threshold) ? Math.max(0, r.threshold) : 60;
  const targetSeconds = Math.round(thresholdMin * 60);
  const pct =
    targetSeconds > 0 ? Math.min(100, Math.round((productive / targetSeconds) * 100)) : 0;
  const met = Boolean(r.goal_met);
  return {
    date: (r.local_date && String(r.local_date)) || todayIsoLocal(),
    goals: [
      {
        id: "day_rollup",
        label: "Daily productive",
        current_seconds: productive,
        target_seconds: targetSeconds,
        pct,
        met,
        fired: met,
      },
    ],
    alerts: [],
    productive_seconds: productive,
    total_seconds: productive,
  };
}
