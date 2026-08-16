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

function normBlockTitle(title: string): string {
  return title.trim().toLowerCase().replace(/\s+/g, " ");
}

function sameLocalDay(a: Date, b: Date): boolean {
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  );
}

/**
 * True when a propose draft already exists as a saved planner block
 * (same title that day, or ≥60% time overlap). Prevents routine+study
 * duplicates in the Plan agenda after Build / Apply routines.
 */
export function draftCoveredBySavedBlocks(
  draft: { title: string; start_at: string; end_at: string },
  blocks: PlannerBlock[],
): boolean {
  const ds = parseApiDate(draft.start_at);
  const de = parseApiDate(draft.end_at);
  if (Number.isNaN(ds.getTime()) || Number.isNaN(de.getTime())) return false;
  const nt = normBlockTitle(draft.title);
  const draftMs = Math.max(1, de.getTime() - ds.getTime());

  return blocks.some((b) => {
    if (b.status === "rolled") return false;
    const bs = parseApiDate(b.start_at);
    const be = parseApiDate(b.end_at);
    if (Number.isNaN(bs.getTime()) || Number.isNaN(be.getTime())) return false;
    if (!sameLocalDay(ds, bs)) return false;
    if (normBlockTitle(b.title) === nt) return true;
    const overlapMs = Math.min(de.getTime(), be.getTime()) - Math.max(ds.getTime(), bs.getTime());
    return overlapMs > 0 && overlapMs / draftMs >= 0.6;
  });
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
  source?: string | null;
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
  source?: string | null;
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
  source?: string | null;
  productivity_score?: number | null;
  duration_seconds?: number;
};


function durationSec(start: string, end: string): number {
  return Math.max(0, Math.round((new Date(end).getTime() - new Date(start).getTime()) / 1000));
}

/** Browser apps often appear as a suffix on the window title (“… — Zen Browser”). */
const TITLE_BROWSER_HINTS: { re: RegExp; app: string }[] = [
  // Match end of title; don't require a specific dash (titles use -, –, —, or |)
  { re: /Zen\s*Browser\s*$/i, app: "zen" },
  { re: /Microsoft\s*Edge\s*$/i, app: "msedge" },
  { re: /Google\s*Chrome\s*$/i, app: "chrome" },
  { re: /\bBrave\s*$/i, app: "brave" },
  { re: /\bFirefox\s*$/i, app: "firefox" },
  { re: /\bOpera\s*$/i, app: "opera" },
  { re: /\bArc\s*$/i, app: "arc" },
  { re: /\bSafari\s*$/i, app: "safari" },
];

/** If the title clearly names a browser, return that app id; else null. */
export function appImpliedByWindowTitle(title: string | null | undefined): string | null {
  const t = (title || "").trim();
  if (!t) return null;
  for (const h of TITLE_BROWSER_HINTS) {
    if (h.re.test(t)) return h.app;
  }
  return null;
}

function appsLookSame(a: string, b: string): boolean {
  const x = shortAppName(a).toLowerCase();
  const y = shortAppName(b).toLowerCase();
  if (!x || !y) return false;
  return x === y || x.includes(y) || y.includes(x);
}

const VIDEO_TITLE_RE = /netflix|youtube|hulu|disney|prime\s*video|\bwatch\b|rookie|twitch|hotstar/i;

/** Normalize exe using window-title browser hint BEFORE merge (fixes Cursor+Zen title). */
export function effectiveAppName(item: {
  app_name?: string | null;
  window_title?: string | null;
}): string {
  const raw = (item.app_name ?? "").trim();
  const implied = appImpliedByWindowTitle(item.window_title);
  if (!implied) return raw;
  if (!raw) return implied;
  if (appsLookSame(raw, implied)) return raw;
  return implied;
}

function categoryForCorrectedBrowser(
  title: string | null | undefined,
  previous: string | null | undefined,
): string {
  if (VIDEO_TITLE_RE.test(title || "")) return "Video Streaming";
  const prev = (previous || "").toLowerCase();
  if (prev.includes("ide") || prev.includes("code") || prev.includes("study")) {
    return "Other (Browser)";
  }
  return previous?.trim() || "Other (Browser)";
}

/**
 * Tracker sometimes pairs the wrong exe with a browser window title
 * (e.g. app=Cursor + title=“… — Zen Browser”). Prefer the title’s browser.
 */
export function reconcileMergedInterval(m: MergedInterval): MergedInterval {
  const implied = appImpliedByWindowTitle(m.window_title);
  if (!implied) return m;
  if (appsLookSame(m.app_name || "", implied)) return m;
  return {
    ...m,
    app_name: implied,
    category: categoryForCorrectedBrowser(m.window_title, m.category),
    productivity_score:
      m.productivity_score != null && m.productivity_score >= 60 ? 35 : m.productivity_score,
  };
}

function mergeKey(item: Mergeable): string {
  // MUST use title-corrected app so Cursor+“…Zen Browser” does not merge with real Cursor
  const app = effectiveAppName(item).trim().toLowerCase();
  if (app) return `app:${app}`;
  return `cat:${(item.category ?? "Other").trim().toLowerCase()}`;
}

function childFrom(item: Mergeable): MergedIntervalChild {
  const app = effectiveAppName(item) || item.app_name || null;
  const implied = appImpliedByWindowTitle(item.window_title);
  const corrected =
    implied && item.app_name && !appsLookSame(item.app_name, implied);
  return {
    session_id: item.session_id ?? null,
    start_time: item.start_time,
    end_time: item.end_time,
    app_name: app,
    category: corrected
      ? categoryForCorrectedBrowser(item.window_title, item.category)
      : item.category ?? null,
    window_title: item.window_title ?? null,
    site: item.site ?? null,
    source: item.source ?? null,
    productivity_score: corrected
      ? item.productivity_score != null && item.productivity_score >= 60
        ? 35
        : item.productivity_score ?? null
      : item.productivity_score ?? null,
    duration_seconds: item.duration_seconds ?? durationSec(item.start_time, item.end_time),
  };
}

/**
 * Stitch adjacent tracker rows for visualization only — raw DB rows stay unchanged.
 * Same app merges across small gaps only when no other app sits between them.
 */
export function mergeAdjacentIntervals<T extends Mergeable>(
  items: T[],
  maxGapSec = TRACKER_MERGE_GAP_SEC,
): MergedInterval[] {
  const sorted = [...items]
    .filter((s) => s.start_time && s.end_time)
    .sort((a, b) => new Date(a.start_time).getTime() - new Date(b.start_time).getTime());

  const out: MergedInterval[] = [];
  const lastByKey = new Map<string, MergedInterval>();

  for (const item of sorted) {
    const startMs = new Date(item.start_time).getTime();
    const endMs = new Date(item.end_time).getTime();
    if (endMs <= startMs) continue;

    const key = mergeKey(item);
    const prev = lastByKey.get(key);
    const prevEndMs = prev ? new Date(prev.end_time).getTime() : 0;
    const gapSec = prev ? (startMs - prevEndMs) / 1000 : Infinity;

    if (prev && (gapSec <= maxGapSec || startMs <= prevEndMs)) {
      let intervening = false;
      for (const other of out) {
        if (mergeKey(other) === key) continue;
        const oStart = new Date(other.start_time).getTime();
        const oEnd = new Date(other.end_time).getTime();
        if (oStart < startMs && oEnd > prevEndMs) {
          intervening = true;
          break;
        }
      }
      if (!intervening) {
        const nextEnd = endMs >= prevEndMs ? item.end_time : prev.end_time;
        prev.end_time = nextEnd;
        const child = childFrom(item);
        // Active time = sum of children, not wall-clock span across gaps
        prev.children.push(child);
        prev.merged_count = prev.children.length;
        prev.duration_seconds = prev.children.reduce((n, c) => n + c.duration_seconds, 0);
        if (child.window_title && !prev.window_title) prev.window_title = child.window_title;
        if (child.site && !prev.site) prev.site = child.site;
        if (child.source && !prev.source) prev.source = child.source;
        const score = child.productivity_score ?? 0;
        if (score && (!prev.productivity_score || score > prev.productivity_score)) {
          prev.productivity_score = score;
        }
        // Keep category / title from the longest child (more representative than first)
        let best = prev.children[0];
        for (const c of prev.children) {
          if (c.duration_seconds > (best?.duration_seconds ?? 0)) best = c;
        }
        if (best?.category) prev.category = best.category;
        if (best?.window_title) prev.window_title = best.window_title;
        if (best?.app_name) prev.app_name = best.app_name;
        continue;
      }
    }

    const child = childFrom(item);
    const row: MergedInterval = {
      session_id: child.session_id,
      start_time: child.start_time,
      end_time: child.end_time,
      app_name: child.app_name,
      category: child.category,
      window_title: child.window_title,
      site: child.site,
      source: child.source ?? null,
      productivity_score: child.productivity_score,
      duration_seconds: child.duration_seconds,
      merged_count: 1,
      children: [child],
    };
    out.push(row);
    lastByKey.set(key, row);
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
        app_name: s.app_name ?? null,
        category: s.category ?? null,
        window_title: s.window_title ?? null,
        site: s.site ?? null,
        source: s.source ?? null,
        productivity_score: s.productivity_score ?? null,
      })),
    maxGapSec,
  ).map(reconcileMergedInterval);
}

/** Force-grouper for planner calendar — filters noise apps + merges long gaps.
 * Sleep (Amazfit) wins over desktop: Cursor/idle inside sleep windows is dropped. */
export function mergeForCalendar(sessions: ActualSession[]): MergedInterval[] {
  const sleep = sessions.filter(
    (s) =>
      (s.category || "").toLowerCase() === "sleep" ||
      (s.source || "").toLowerCase() === "wearable_sleep" ||
      (s.app_name || "").toLowerCase() === "amazfit",
  );
  const rest = sessions.filter((s) => !sleep.includes(s));
  const clippedRest = clipSessionsAgainstSleep(rest, sleep);
  const mergedRest = mergeActualSessions(clippedRest, CALENDAR_MERGE_GAP_SEC).filter(
    (m) => m.duration_seconds >= CALENDAR_MIN_DISPLAY_SEC,
  );
  const mergedSleep = mergeActualSessions(sleep, CALENDAR_MERGE_GAP_SEC);
  return [...mergedRest, ...mergedSleep].sort(
    (a, b) => new Date(a.start_time).getTime() - new Date(b.start_time).getTime(),
  );
}

/** Remove awake tracker pieces that sit inside sleep intervals. */
export function clipSessionsAgainstSleep(
  sessions: ActualSession[],
  sleepSessions: ActualSession[],
): ActualSession[] {
  if (!sessions.length || !sleepSessions.length) return sessions;
  const sleeps = sleepSessions
    .map((s) => {
      const a = s.start_time ? new Date(s.start_time).getTime() : NaN;
      const b = s.end_time ? new Date(s.end_time).getTime() : NaN;
      return Number.isFinite(a) && Number.isFinite(b) && b > a ? ([a, b] as const) : null;
    })
    .filter((x): x is readonly [number, number] => x != null);
  if (!sleeps.length) return sessions;

  const out: ActualSession[] = [];
  for (const s of sessions) {
    const a = s.start_time ? new Date(s.start_time).getTime() : NaN;
    const b = s.end_time ? new Date(s.end_time).getTime() : NaN;
    if (!Number.isFinite(a) || !Number.isFinite(b) || b <= a) {
      out.push(s);
      continue;
    }
    let pieces: Array<[number, number]> = [[a, b]];
    for (const [ss, se] of sleeps) {
      const next: Array<[number, number]> = [];
      for (const [x, y] of pieces) {
        if (y <= ss || x >= se) {
          next.push([x, y]);
          continue;
        }
        if (x < ss) next.push([x, ss]);
        if (y > se) next.push([se, y]);
      }
      pieces = next.filter(([x, y]) => y - x >= 45_000);
    }
    pieces.forEach(([x, y], i) => {
      out.push({
        ...s,
        session_id: i === 0 && pieces.length === 1 ? s.session_id : `${s.session_id}:awake${i}`,
        start_time: new Date(x).toISOString(),
        end_time: new Date(y).toISOString(),
      });
    });
  }
  return out;
}

export function shortAppName(name: string | null | undefined): string {
  if (!name) return "Activity";
  return name.replace(/\.exe$/i, "").replace(/\.app$/i, "");
}

/** Human label for a merged tracker/sleep interval (Sleep, not Amazfit). */
export function intervalDisplayName(m: {
  app_name?: string | null;
  category?: string | null;
  window_title?: string | null;
  site?: string | null;
}): string {
  const cat = (m.category || "").toLowerCase();
  const app = (m.app_name || "").toLowerCase();
  if (cat === "sleep" || app === "amazfit") return "Sleep";
  const site = (m.site || "").trim();
  if (site && /\./.test(site) && !/\s/.test(site)) return site;
  if (app.includes(".") && !app.endsWith(".exe") && !app.startsWith("calt_spa")) {
    return shortAppName(m.app_name);
  }
  const implied = appImpliedByWindowTitle(m.window_title);
  if (implied && m.app_name && !appsLookSame(m.app_name, implied)) {
    return shortAppName(implied);
  }
  return shortAppName(m.app_name || m.category);
}

export function mergedIntervalLabel(m: MergedInterval): string {
  const name = intervalDisplayName(m);
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

/** Clip merged intervals to a local hour window; duration = overlap only. */
export function intervalsInHour(
  intervals: MergedInterval[],
  hourStart: Date,
): MergedInterval[] {
  const hs = hourStart.getTime();
  const he = hs + 60 * 60 * 1000;
  const out: MergedInterval[] = [];
  for (const iv of intervals) {
    const a = parseApiDate(iv.start_time).getTime();
    const b = parseApiDate(iv.end_time).getTime();
    const start = Math.max(a, hs);
    const end = Math.min(b, he);
    if (end - start < 1000) continue;
    out.push({
      ...iv,
      start_time: new Date(start).toISOString(),
      end_time: new Date(end).toISOString(),
      duration_seconds: Math.round((end - start) / 1000),
      children: iv.children,
    });
  }
  out.sort((x, y) => y.duration_seconds - x.duration_seconds);
  return out;
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
