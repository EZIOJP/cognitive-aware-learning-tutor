import type { ActualSession, PlannerBlock } from "../../api/plannerClient";
import type { TimelineInterval } from "../../api/behaviorClient";

export type AdherenceDay = {
  date: string;
  planned: number;
  actual: number;
  productive: number;
  pct: number | null;
  blockCount: number;
  noPlan: boolean;
};

export function toDayString(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

/** Parse API ISO timestamps — naive DB UTC must get a Z suffix for correct local rows. */
export function parseApiDate(iso: string | null | undefined): Date {
  if (!iso) return new Date(NaN);
  const s = /[zZ]$|[+-]\d{2}:\d{2}$/.test(iso.trim()) ? iso.trim() : `${iso.trim()}Z`;
  return new Date(s);
}

export function startOfDay(d: Date): Date {
  const out = new Date(d);
  out.setHours(0, 0, 0, 0);
  return out;
}

export function endOfDay(d: Date): Date {
  const out = new Date(d);
  out.setHours(23, 59, 59, 999);
  return out;
}

export function minutesSinceMidnight(d: Date): number {
  return d.getHours() * 60 + d.getMinutes() + d.getSeconds() / 60;
}

export function computeAxisWindow(
  blocks: PlannerBlock[],
  intervals: TimelineInterval[],
): { axisStart: number; axisEnd: number } {
  const FULL = { axisStart: 0, axisEnd: 24 * 60 };
  const points: number[] = [];

  for (const b of blocks) {
    if (b.start_at) points.push(minutesSinceMidnight(new Date(b.start_at)));
    if (b.end_at) points.push(minutesSinceMidnight(new Date(b.end_at)));
  }
  for (const iv of intervals) {
    if (iv.start_time) points.push(minutesSinceMidnight(new Date(iv.start_time)));
    if (iv.end_time) points.push(minutesSinceMidnight(new Date(iv.end_time)));
  }

  if (points.length === 0) return FULL;

  const min = Math.min(...points);
  const max = Math.max(...points);
  const pad = 60;
  return {
    axisStart: Math.max(0, min - pad),
    axisEnd: Math.min(24 * 60, max + pad),
  };
}

export function toSegmentStyle(
  startMin: number,
  endMin: number,
  axisStart: number,
  axisEnd: number,
): { left: string; width: string } {
  const span = Math.max(1, axisEnd - axisStart);
  const left = ((startMin - axisStart) / span) * 100;
  const width = ((endMin - startMin) / span) * 100;
  return {
    left: `${Math.max(0, left)}%`,
    width: `${Math.max(0.15, width)}%`,
  };
}

export function intervalsOverlap(a0: number, a1: number, b0: number, b1: number): boolean {
  return a0 < b1 && b0 < a1;
}

export function actualOverlapsPlanned(
  intervalStart: number,
  intervalEnd: number,
  blocks: PlannerBlock[],
): boolean {
  for (const b of blocks) {
    if (!b.start_at || !b.end_at) continue;
    const b0 = minutesSinceMidnight(new Date(b.start_at));
    const b1 = minutesSinceMidnight(new Date(b.end_at));
    if (intervalsOverlap(intervalStart, intervalEnd, b0, b1)) return true;
  }
  return false;
}

export function computeStreak(days: AdherenceDay[], threshold = 0.7): number {
  const thresholdPct = threshold * 100;
  const sorted = [...days].sort((a, b) => b.date.localeCompare(a.date));
  let streak = 0;

  for (const d of sorted) {
    if (d.noPlan || d.pct == null) continue;
    if (d.pct >= thresholdPct) {
      streak += 1;
    } else {
      break;
    }
  }
  return streak;
}

export function aggregatePlannedByTask(
  blocks: PlannerBlock[],
  taskTitleById: Map<number, string>,
): { name: string; hours: number }[] {
  const totals = new Map<string, number>();
  for (const b of blocks) {
    const key =
      b.task_id == null
        ? "Unassigned"
        : taskTitleById.get(b.task_id) ?? `Task #${b.task_id}`;
    totals.set(key, (totals.get(key) ?? 0) + b.planned_minutes);
  }
  return [...totals.entries()]
    .map(([name, minutes]) => ({ name, hours: Math.round((minutes / 60) * 10) / 10 }))
    .sort((a, b) => b.hours - a.hours);
}

export function aggregateActualByCategory(sessions: ActualSession[]): { name: string; hours: number }[] {
  const totals = new Map<string, number>();
  for (const s of sessions) {
    if (!s.start_time || !s.end_time) continue;
    const start = new Date(s.start_time).getTime();
    const end = new Date(s.end_time).getTime();
    const minutes = Math.max(0, (end - start) / 60000);
    if (minutes <= 0) continue;
    const key = s.category?.trim() || "Other";
    totals.set(key, (totals.get(key) ?? 0) + minutes);
  }
  return [...totals.entries()]
    .map(([name, minutes]) => ({ name, hours: Math.round((minutes / 60) * 10) / 10 }))
    .sort((a, b) => b.hours - a.hours);
}

export function fmtDurationMinutes(m: number): string {
  if (m < 60) return `${Math.round(m)}m`;
  const h = Math.floor(m / 60);
  const rem = Math.round(m % 60);
  return rem > 0 ? `${h}h ${rem}m` : `${h}h`;
}

export function lastNDays(n: number): string[] {
  return daysEndingOn(new Date(), n);
}

/** Inclusive calendar days ending on `end` (oldest first when reversed for charts). */
export function daysEndingOn(end: Date, n: number): string[] {
  const out: string[] = [];
  const anchor = startOfDay(end);
  for (let i = 0; i < n; i++) {
    const d = new Date(anchor);
    d.setDate(anchor.getDate() - i);
    out.push(toDayString(d));
  }
  return out;
}

export type CalendarStatsView = "day" | "week" | "month";

export function statsRangeForView(
  view: CalendarStatsView,
  anchor: Date,
): { from: Date; to: Date; dayCount: number; label: string } {
  const day = startOfDay(anchor);
  if (view === "day") {
    return { from: day, to: endOfDay(day), dayCount: 1, label: "selected day" };
  }
  if (view === "week") {
    const from = startOfWeekMonday(day);
    const to = endOfWeekSunday(day);
    return { from, to, dayCount: 7, label: "this week" };
  }
  const from = startOfDay(new Date(day.getFullYear(), day.getMonth(), 1));
  const to = endOfDay(new Date(day.getFullYear(), day.getMonth() + 1, 0));
  const dayCount = to.getDate();
  return { from, to, dayCount, label: "this month" };
}

export function startOfWeekMonday(d: Date): Date {
  const out = startOfDay(d);
  const day = out.getDay();
  const diff = day === 0 ? -6 : 1 - day;
  out.setDate(out.getDate() + diff);
  return out;
}

export function endOfWeekSunday(d: Date): Date {
  const mon = startOfWeekMonday(d);
  const out = new Date(mon);
  out.setDate(mon.getDate() + 6);
  out.setHours(23, 59, 59, 999);
  return out;
}

/** Gap (seconds) below which same-app tracker flushes are stitched for display. */
export const TRACKER_MERGE_GAP_SEC = 120;

/** Calendar: aggressive merge so react-big-calendar stays readable. */
export const CALENDAR_MERGE_GAP_SEC = 900;
export const CALENDAR_MIN_DISPLAY_SEC = 120;

const IGNORED_TRACKER_APPS = [/^move\s*mouse/i, /movemouse/i, /^caffeine/i, /dontsleep/i, /lockapp/i, /steamwebhelper/i];

export function isIgnoredTrackerApp(appName?: string | null, title?: string | null): boolean {
  const hay = `${appName ?? ""} ${title ?? ""}`.trim();
  if (!hay) return false;
  return IGNORED_TRACKER_APPS.some((re) => re.test(hay));
}

export type MergedInterval = {
  session_id?: string | null;
  start_time: string;
  end_time: string;
  app_name: string | null;
  category: string | null;
  window_title: string | null;
  site?: string | null;
  productivity_score: number | null;
  duration_seconds: number;
  merged_count: number;
  children: MergedIntervalChild[];
};

export type MergedIntervalChild = {
  session_id?: string | null;
  start_time: string;
  end_time: string;
  app_name?: string | null;
  category?: string | null;
  window_title?: string | null;
  site?: string | null;
  productivity_score?: number | null;
  duration_seconds: number;
};

type Mergeable = {
  session_id?: string | null;
  start_time: string;
  end_time: string;
  app_name?: string | null;
  category?: string | null;
  window_title?: string | null;
  site?: string | null;
  productivity_score?: number | null;
  duration_seconds?: number;
};

function mergeKey(item: Mergeable): string {
  const app = (item.app_name ?? "").trim().toLowerCase();
  if (app) return `app:${app}`;
  return `cat:${(item.category ?? "Other").trim().toLowerCase()}`;
}

function durationSec(start: string, end: string): number {
  return Math.max(0, Math.round((new Date(end).getTime() - new Date(start).getTime()) / 1000));
}

function childFrom(item: Mergeable): MergedIntervalChild {
  return {
    session_id: item.session_id ?? null,
    start_time: item.start_time,
    end_time: item.end_time,
    app_name: item.app_name ?? null,
    category: item.category ?? null,
    window_title: item.window_title ?? null,
    site: item.site ?? null,
    productivity_score: item.productivity_score ?? null,
    duration_seconds: item.duration_seconds ?? durationSec(item.start_time, item.end_time),
  };
}

/**
 * Stitch adjacent tracker rows for visualization only — raw DB rows stay unchanged.
 * Merges when same app (or category) and gap <= maxGapSec.
 */
export function mergeAdjacentIntervals<T extends Mergeable>(
  items: T[],
  maxGapSec = TRACKER_MERGE_GAP_SEC,
): MergedInterval[] {
  const sorted = [...items]
    .filter((s) => s.start_time && s.end_time)
    .sort((a, b) => new Date(a.start_time).getTime() - new Date(b.start_time).getTime());

  const out: MergedInterval[] = [];

  for (const item of sorted) {
    const startMs = new Date(item.start_time).getTime();
    const endMs = new Date(item.end_time).getTime();
    if (endMs <= startMs) continue;

    const key = mergeKey(item);
    const prev = out[out.length - 1];
    const prevEndMs = prev ? new Date(prev.end_time).getTime() : 0;
    const gapSec = prev ? (startMs - prevEndMs) / 1000 : Infinity;

    if (prev && mergeKey(prev) === key && gapSec <= maxGapSec) {
      prev.end_time = item.end_time;
      prev.duration_seconds = durationSec(prev.start_time, prev.end_time);
      prev.merged_count += 1;
      prev.children.push(childFrom(item));
      if (item.window_title && !prev.window_title) prev.window_title = item.window_title;
      if (item.site && !prev.site) prev.site = item.site;
      const score = item.productivity_score ?? 0;
      if (score && (!prev.productivity_score || score > prev.productivity_score)) {
        prev.productivity_score = score;
      }
      continue;
    }

    out.push({
      session_id: item.session_id ?? null,
      start_time: item.start_time,
      end_time: item.end_time,
      app_name: item.app_name ?? null,
      category: item.category ?? null,
      window_title: item.window_title ?? null,
      site: item.site ?? null,
      productivity_score: item.productivity_score ?? null,
      duration_seconds: item.duration_seconds ?? durationSec(item.start_time, item.end_time),
      merged_count: 1,
      children: [childFrom(item)],
    });
  }

  return out;
}

/** Overlay sessions → calendar/ribbon-friendly merged blocks. */
export function mergeActualSessions(sessions: ActualSession[], maxGapSec = TRACKER_MERGE_GAP_SEC): MergedInterval[] {
  return mergeAdjacentIntervals(
    sessions
      .filter((s) => s.start_time && s.end_time && !isIgnoredTrackerApp(s.app_name, s.window_title))
      .map((s) => ({
        session_id: s.session_id,
        start_time: s.start_time!,
        end_time: s.end_time!,
        app_name: (s as ActualSession & { app_name?: string }).app_name ?? null,
        category: s.category ?? null,
        window_title: (s as ActualSession & { window_title?: string }).window_title ?? null,
        productivity_score: s.productivity_score ?? null,
      })),
    maxGapSec,
  );
}

/** Force-grouper for planner calendar — filters noise apps + merges long gaps. */
export function mergeForCalendar(sessions: ActualSession[]): MergedInterval[] {
  return mergeActualSessions(sessions, CALENDAR_MERGE_GAP_SEC).filter(
    (m) => m.duration_seconds >= CALENDAR_MIN_DISPLAY_SEC,
  );
}

export function mergedIntervalLabel(m: MergedInterval): string {
  const name = m.app_name || m.category || "Activity";
  const mins = Math.round(m.duration_seconds / 60);
  const suffix = m.merged_count > 1 ? ` · ${m.merged_count} sessions` : "";
  return `${name} · ${fmtDurationMinutes(mins)}${suffix}`;
}

export type HourlyActualStack = {
  key: string;
  hourStart: Date;
  hourEnd: Date;
  items: MergedInterval[];
  totalSeconds: number;
};

function hourBucketKey(d: Date): string {
  return `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}-${d.getHours()}`;
}

function startOfHour(d: Date): Date {
  const out = new Date(d);
  out.setMinutes(0, 0, 0);
  return out;
}

/** Group merged intervals into per-hour stacks for calendar week/month view. */
export function stackActualByHour(intervals: MergedInterval[]): HourlyActualStack[] {
  const buckets = new Map<string, MergedInterval[]>();

  for (const iv of intervals) {
    const start = parseApiDate(iv.start_time);
    const key = hourBucketKey(start);
    const list = buckets.get(key) ?? [];
    list.push(iv);
    buckets.set(key, list);
  }

  const stacks: HourlyActualStack[] = [];

  for (const [key, items] of buckets) {
    items.sort((a, b) => b.duration_seconds - a.duration_seconds);
    const hourStart = startOfHour(parseApiDate(items[0].start_time));
    const hourEnd = new Date(hourStart);
    hourEnd.setHours(hourEnd.getHours() + 1);
    const totalSeconds = items.reduce((n, i) => n + i.duration_seconds, 0);

    stacks.push({
      key,
      hourStart,
      hourEnd,
      items,
      totalSeconds,
    });
  }

  return stacks.sort((a, b) => a.hourStart.getTime() - b.hourStart.getTime());
}

export function eventsTimeOverlap(
  a: { start: Date; end: Date },
  b: { start: Date; end: Date },
): boolean {
  return a.start < b.end && b.start < a.end;
}

/** Overlap for focus/cycle — includes same clock hour (planned + tracked stack). */
export function eventsOverlapForFocus(
  a: { start: Date; end: Date },
  b: { start: Date; end: Date },
): boolean {
  if (eventsTimeOverlap(a, b)) return true;
  return (
    a.start.getFullYear() === b.start.getFullYear() &&
    a.start.getMonth() === b.start.getMonth() &&
    a.start.getDate() === b.start.getDate() &&
    a.start.getHours() === b.start.getHours()
  );
}

/** All actual calendar events overlapping the target (same slot / hidden stacks). */
export function overlappingActualEvents<T extends { id: number; start: Date; end: Date; isActual?: boolean }>(
  events: T[],
  target: T,
): T[] {
  if (!target.isActual) return [target];
  return events
    .filter((e) => e.isActual && eventsTimeOverlap(e, target))
    .sort((a, b) => a.start.getTime() - b.start.getTime() || a.id - b.id);
}

/** True activity span for a stack (modal / labels). */
export function actualStackTimeSpan(items: MergedInterval[]): { start: Date; end: Date } {
  const starts = items.map((i) => parseApiDate(i.start_time).getTime());
  const ends = items.map((i) => parseApiDate(i.end_time).getTime());
  return {
    start: new Date(Math.min(...starts)),
    end: new Date(Math.max(...ends)),
  };
}

export function shortAppName(name: string | null | undefined): string {
  if (!name) return "Activity";
  return name.replace(/\.exe$/i, "").replace(/\.app$/i, "");
}

export const PRODUCTIVE_THRESHOLD = 60;

export function scoreAccent(score: number | null | undefined): string {
  const s = score ?? 35;
  if (s >= 80) return "bg-emerald-400";
  if (s >= 60) return "bg-green-400";
  if (s >= 40) return "bg-yellow-400";
  if (s >= 20) return "bg-orange-400";
  return "bg-red-400";
}

export function scoreLabel(score: number | null | undefined): string {
  const s = score ?? 35;
  if (s >= 80) return "Highly productive";
  if (s >= PRODUCTIVE_THRESHOLD) return "Productive";
  if (s >= 40) return "Neutral";
  if (s >= 20) return "Low focus";
  return "Distraction";
}
