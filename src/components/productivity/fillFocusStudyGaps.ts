import {
  createPlannerBlock,
  deletePlannerBlock,
  type PlannerBlock,
  type StudyTask,
} from "../../api/plannerClient";

type Gap = { start: number; end: number };

const WEEKDAY_KEYS = ["sun", "mon", "tue", "wed", "thu", "fri", "sat"] as const;

export function isFreeCategory(cat: string): boolean {
  const c = (cat || "").trim().toLowerCase();
  return (
    c === "break" ||
    c === "free" ||
    c === "reward" ||
    c === "leisure" ||
    c === "rest" ||
    c === "downtime" ||
    c === "food" ||
    c === "sleep" ||
    c === "commute"
  );
}

/** Counts toward daily focus goal (SoftLand productive target). */
export function isStudyFocusCategory(cat: string): boolean {
  const c = (cat || "").trim().toLowerCase();
  return c === "study" || c === "work" || c === "coursework" || c === "deep_work" || c === "focus";
}

/** Life/routine anchors applied from Routines (not study/work). */
export function isRoutineLifeCategory(cat: string): boolean {
  const c = (cat || "").trim().toLowerCase();
  return c === "food" || c === "personal" || c === "spiritual";
}

/**
 * Free minutes between today's first and last routine blocks.
 *
 * Formula:
 * - Take scheduled routine blocks (food / personal / spiritual)
 * - span = firstRoutine.start → lastRoutine.end (minute-of-day)
 * - available = span length − minutes covered by any routine in that span
 *   (i.e. sum of gaps *between* routines inside the span; no pre-first / post-last)
 * - Study/work blocks do not reduce this capacity (they fill it)
 *
 * Returns 0 when there are no routines, a single routine, or only contiguous
 * routines with no interior gaps. Overnight (end ≤ start) uses duration and
 * clamps to midnight — cross-midnight spans are not modeled as multi-day.
 */
export function availableRoutineGapMinutes(blocks: PlannerBlock[]): number {
  const routines = blocks.filter(
    (b) =>
      b.status !== "cancelled" &&
      b.status !== "rolled" &&
      isRoutineLifeCategory(b.category || ""),
  );
  if (routines.length === 0) return 0;
  return availableGapMinutesFromSpans(routines.map(blockSpanMinutes));
}

/** Same as {@link availableRoutineGapMinutes}, rounded to 0.1h. */
export function availableRoutineGapHours(blocks: PlannerBlock[]): number {
  return Math.round((availableRoutineGapMinutes(blocks) / 60) * 10) / 10;
}

function parseHmToDayMinutes(hm: string | null | undefined): number | null {
  if (!hm || !/^\d{1,2}:\d{2}/.test(hm)) return null;
  const [h, m] = hm.split(":").map((x) => Number(x) || 0);
  if (h < 0 || h > 23 || m < 0 || m > 59) return null;
  return h * 60 + m;
}

export type RoutineScheduleLike = {
  start_time?: string | null;
  end_time?: string | null;
  duration_minutes?: number | null;
  days?: string[] | null;
  enabled?: boolean;
  category?: string | null;
};

/** Enabled routines for this weekday as minute-of-day spans. */
export function routineScheduleSpansForDay(
  routines: RoutineScheduleLike[],
  day: Date = new Date(),
): Gap[] {
  const key = WEEKDAY_KEYS[day.getDay()];
  const out: Gap[] = [];
  for (const r of routines) {
    if (r.enabled === false) continue;
    const cat = (r.category || "").trim().toLowerCase();
    if (cat && isStudyFocusCategory(cat)) continue;
    const days = Array.isArray(r.days) && r.days.length > 0 ? r.days.map((d) => d.toLowerCase()) : null;
    if (days && !days.includes(key)) continue;
    const start = parseHmToDayMinutes(r.start_time);
    if (start == null) continue;
    let end = parseHmToDayMinutes(r.end_time ?? null);
    if (end == null || end <= start) {
      const dur = Math.max(15, Number(r.duration_minutes) || 30);
      end = start + dur;
    }
    if (end > start) out.push({ start, end: Math.min(24 * 60, end) });
  }
  return out;
}

/** Gap minutes from arbitrary routine spans (schedule or applied). */
export function availableGapMinutesFromSpans(spans: { start: number; end: number }[]): number {
  if (!spans.length) return 0;
  const spanStart = Math.min(...spans.map((s) => s.start));
  const spanEnd = Math.max(...spans.map((s) => s.end));
  if (!(spanEnd > spanStart)) return 0;

  const sorted = [...spans]
    .map((g) => ({
      start: Math.max(spanStart, g.start),
      end: Math.min(spanEnd, g.end),
    }))
    .filter((g) => g.end > g.start)
    .sort((a, b) => a.start - b.start);

  const merged: Gap[] = [];
  for (const g of sorted) {
    const last = merged[merged.length - 1];
    if (last && g.start <= last.end) {
      last.end = Math.max(last.end, g.end);
    } else {
      merged.push({ start: g.start, end: g.end });
    }
  }

  let occupied = 0;
  for (const m of merged) occupied += m.end - m.start;
  return Math.max(0, spanEnd - spanStart - occupied);
}

/** Minute-of-day now, rounded up to the next 5 minutes (never plan into the past). */
export function nowMinuteOfDayCeil(day: Date = new Date(), step = 5): number {
  const today = new Date();
  if (
    day.getFullYear() !== today.getFullYear() ||
    day.getMonth() !== today.getMonth() ||
    day.getDate() !== today.getDate()
  ) {
    return 0; // future days: full day from midnight
  }
  const raw = today.getHours() * 60 + today.getMinutes();
  const s = Math.max(1, step);
  return Math.min(24 * 60, Math.ceil(raw / s) * s);
}

/**
 * Waking window from sleep clocks (wake → bed). Overnight bed after midnight
 * clamps end to 24:00 for same-day capacity (multi-day spans not modeled).
 * For today, start is also clamped to now so past morning is not counted.
 */
export function wakingWindowMinutes(
  wakeHm?: string | null,
  bedtimeHm?: string | null,
  day: Date = new Date(),
): { start: number; end: number } | null {
  const wake = parseHmToDayMinutes(wakeHm ?? null);
  const bed = parseHmToDayMinutes(bedtimeHm ?? null);
  if (wake == null || bed == null) return null;
  let end = bed;
  if (end <= wake) end = 24 * 60; // overnight bed → end of waking day
  let start = wake;
  start = Math.max(start, nowMinuteOfDayCeil(day));
  if (end <= start) return null;
  return { start, end };
}

/**
 * Max focus hours for the day: prefer today's enabled routine *schedule*
 * (first→last template), else fall back to applied routine plan blocks.
 * When wake/bed are set, capacity is waking span minus overlapping routines
 * (or the full waking span if no routines).
 */
export function availableFocusGapHours(opts: {
  blocks: PlannerBlock[];
  routines?: RoutineScheduleLike[] | null;
  day?: Date;
  wakeHm?: string | null;
  bedtimeHm?: string | null;
}): number {
  const day = opts.day ?? new Date();
  const wakeWin = wakingWindowMinutes(opts.wakeHm, opts.bedtimeHm, day);
  const scheduleSpans = routineScheduleSpansForDay(opts.routines || [], day);

  if (wakeWin) {
    const routineSpans =
      scheduleSpans.length > 0
        ? scheduleSpans
        : opts.blocks
            .filter(
              (b) =>
                b.status !== "cancelled" &&
                b.status !== "rolled" &&
                isRoutineLifeCategory(b.category || ""),
            )
            .map(blockSpanMinutes);
    const free = freeGapsInsideWindow(routineSpans, wakeWin.start, wakeWin.end);
    return Math.round((Math.max(0, free) / 60) * 10) / 10;
  }

  // No sleep clocks: still ignore gaps before now on today.
  const nowCeil = nowMinuteOfDayCeil(day);
  const routineSpans =
    scheduleSpans.length > 0
      ? scheduleSpans
      : opts.blocks
          .filter(
            (b) =>
              b.status !== "cancelled" &&
              b.status !== "rolled" &&
              isRoutineLifeCategory(b.category || ""),
          )
          .map(blockSpanMinutes);
  if (routineSpans.length > 0) {
    const spanEnd = Math.max(...routineSpans.map((s) => s.end));
    if (spanEnd > nowCeil) {
      const free = freeGapsInsideWindow(routineSpans, nowCeil, spanEnd);
      if (free > 0) return Math.round((free / 60) * 10) / 10;
    }
  }
  const fromSchedule = availableGapMinutesFromSpans(scheduleSpans);
  if (fromSchedule > 0) {
    return Math.round((fromSchedule / 60) * 10) / 10;
  }
  return availableRoutineGapHours(opts.blocks);
}

/** Free minutes inside [windowStart, windowEnd] not covered by routine spans. */
function freeGapsInsideWindow(
  spans: { start: number; end: number }[],
  windowStart: number,
  windowEnd: number,
): number {
  if (!(windowEnd > windowStart)) return 0;
  const sorted = [...spans]
    .map((g) => ({
      start: Math.max(windowStart, g.start),
      end: Math.min(windowEnd, g.end),
    }))
    .filter((g) => g.end > g.start)
    .sort((a, b) => a.start - b.start);

  const merged: Gap[] = [];
  for (const g of sorted) {
    const last = merged[merged.length - 1];
    if (last && g.start <= last.end) {
      last.end = Math.max(last.end, g.end);
    } else {
      merged.push({ start: g.start, end: g.end });
    }
  }

  let occupied = 0;
  for (const m of merged) occupied += m.end - m.start;
  return Math.max(0, windowEnd - windowStart - occupied);
}

/** Auto-filled study blocks we may trim when the focus goal shrinks. */
export function isTrimmableStudyBlock(b: PlannerBlock): boolean {
  if (!isStudyFocusCategory(b.category || "")) return false;
  if (b.status === "cancelled" || b.status === "rolled" || b.status === "done") return false;
  const t = (b.title || "").trim().toLowerCase();
  // Keep user-named study blocks unless they look like auto fill.
  return t === "study" || t === "focus" || t === "focus block" || t.startsWith("study ·");
}

function parseHmToMinutes(hm: string | null | undefined, fallback: number): number {
  if (!hm || !/^\d{1,2}:\d{2}/.test(hm)) return fallback;
  const [h, m] = hm.split(":").map((x) => Number(x) || 0);
  if (h < 0 || h > 23 || m < 0 || m > 59) return fallback;
  return h * 60 + m;
}

function localIsoFromDayMinutes(day: Date, minuteOfDay: number): string {
  const d = new Date(day);
  d.setHours(0, 0, 0, 0);
  d.setMinutes(minuteOfDay);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}:00`;
}

export function blockSpanMinutes(b: PlannerBlock): { start: number; end: number } {
  const a = new Date(b.start_at);
  const e = new Date(b.end_at);
  const start = a.getHours() * 60 + a.getMinutes();
  let end = e.getHours() * 60 + e.getMinutes();
  if (end <= start) end = start + Math.max(15, b.planned_minutes || 30);
  return { start, end };
}

export function studyMinutesFromBlocks(blocks: PlannerBlock[]): number {
  let n = 0;
  for (const b of blocks) {
    if (b.status === "cancelled" || b.status === "rolled") continue;
    if (!isStudyFocusCategory(b.category || "")) continue;
    const { start, end } = blockSpanMinutes(b);
    n += Math.max(0, end - start);
  }
  return n;
}

function freeGaps(occupied: Gap[], windowStart: number, windowEnd: number): Gap[] {
  const sorted = [...occupied]
    .filter((g) => g.end > windowStart && g.start < windowEnd)
    .map((g) => ({
      start: Math.max(windowStart, g.start),
      end: Math.min(windowEnd, g.end),
    }))
    .sort((a, b) => a.start - b.start);

  const gaps: Gap[] = [];
  let cursor = windowStart;
  for (const o of sorted) {
    if (o.start > cursor) gaps.push({ start: cursor, end: o.start });
    cursor = Math.max(cursor, o.end);
  }
  if (cursor < windowEnd) gaps.push({ start: cursor, end: windowEnd });
  return gaps.filter((g) => g.end - g.start >= 25);
}

export type FillFocusResult = {
  created: number;
  deleted: number;
  minutesAdded: number;
  minutesRemoved: number;
  shortfallBefore: number;
  shortfallAfter: number;
};

/**
 * Align calendar study blocks to daily focus hours:
 * - under goal → pack study into free gaps
 * - over goal → remove trimmable Study/Focus blocks from the end of the day
 * Routines (spiritual/food/personal) are never auto-removed.
 */
export async function syncStudyHoursToFocusGoal(opts: {
  focusHours: number;
  blocks: PlannerBlock[];
  wakeHm?: string | null;
  bedtimeHm?: string | null;
  studyTasks?: StudyTask[];
}): Promise<FillFocusResult> {
  const goalMins = Math.round(Math.max(0, opts.focusHours) * 60);
  const have = studyMinutesFromBlocks(opts.blocks);
  const delta = goalMins - have;

  if (delta >= 25) {
    const fill = await packStudyIntoGaps({ ...opts, needOverride: delta });
    return {
      created: fill.created,
      deleted: 0,
      minutesAdded: fill.minutesAdded,
      minutesRemoved: 0,
      shortfallBefore: delta,
      shortfallAfter: fill.shortfallAfter,
    };
  }

  if (delta <= -25) {
    const trim = await trimStudyBlocksToGoal(opts.blocks, goalMins);
    return {
      created: 0,
      deleted: trim.deleted,
      minutesAdded: 0,
      minutesRemoved: trim.minutesRemoved,
      shortfallBefore: delta,
      shortfallAfter: Math.max(0, goalMins - (have - trim.minutesRemoved)),
    };
  }

  return {
    created: 0,
    deleted: 0,
    minutesAdded: 0,
    minutesRemoved: 0,
    shortfallBefore: delta,
    shortfallAfter: Math.max(0, -delta) < 25 ? 0 : Math.abs(delta),
  };
}

export async function trimStudyBlocksToGoal(
  blocks: PlannerBlock[],
  goalMins: number,
): Promise<{ deleted: number; minutesRemoved: number }> {
  let have = studyMinutesFromBlocks(blocks);
  let needCut = have - goalMins;
  if (needCut < 25) return { deleted: 0, minutesRemoved: 0 };

  // Prefer auto-filled Study/Focus titles, then any other study/work block (newest first).
  const byEndDesc = (a: PlannerBlock, b: PlannerBlock) =>
    new Date(b.start_at).getTime() - new Date(a.start_at).getTime();
  const auto = blocks.filter(isTrimmableStudyBlock).sort(byEndDesc);
  const named = blocks
    .filter(
      (b) =>
        isStudyFocusCategory(b.category || "") &&
        !isTrimmableStudyBlock(b) &&
        b.status !== "cancelled" &&
        b.status !== "rolled" &&
        b.status !== "done",
    )
    .sort(byEndDesc);
  const candidates = [...auto, ...named];

  let deleted = 0;
  let minutesRemoved = 0;
  for (const b of candidates) {
    if (needCut < 25) break;
    const { start, end } = blockSpanMinutes(b);
    const mins = Math.max(0, end - start);
    if (mins <= 0) continue;
    await deletePlannerBlock(b.id);
    deleted += 1;
    minutesRemoved += mins;
    needCut -= mins;
    have -= mins;
  }
  return { deleted, minutesRemoved };
}

async function packStudyIntoGaps(opts: {
  focusHours: number;
  blocks: PlannerBlock[];
  wakeHm?: string | null;
  bedtimeHm?: string | null;
  studyTasks?: StudyTask[];
  needOverride?: number;
}): Promise<{ created: number; minutesAdded: number; shortfallAfter: number }> {
  let need =
    typeof opts.needOverride === "number"
      ? opts.needOverride
      : Math.max(0, Math.round(opts.focusHours * 60) - studyMinutesFromBlocks(opts.blocks));
  if (need < 25) return { created: 0, minutesAdded: 0, shortfallAfter: need };

  const day = new Date();
  const nowCeil = nowMinuteOfDayCeil(day);
  const wake = parseHmToMinutes(opts.wakeHm, 7 * 60);
  const bed = parseHmToMinutes(opts.bedtimeHm, 23 * 60);
  // Pack from wake (or now — never the past) through bed; no morning-only clamp.
  let winStart = Math.max(wake, nowCeil);
  let winEnd = bed > wake ? bed : 24 * 60;
  if (winEnd <= winStart) {
    winStart = nowCeil;
    winEnd = Math.max(winStart + 60, 21 * 60);
    if (winEnd > 24 * 60) winEnd = 24 * 60;
  }
  if (winEnd - winStart < 25) {
    return { created: 0, minutesAdded: 0, shortfallAfter: need };
  }

  const occupied = opts.blocks
    .filter((b) => b.status !== "cancelled" && b.status !== "rolled")
    .map(blockSpanMinutes);

  const gaps = freeGaps(occupied, winStart, winEnd);
  const tasks = (opts.studyTasks || []).filter((t) => t.title?.trim());
  let taskIdx = 0;
  let created = 0;
  let minutesAdded = 0;

  for (const gap of gaps) {
    let cursor = Math.max(gap.start, nowCeil);
    while (need >= 25 && cursor + 25 <= gap.end) {
      const room = gap.end - cursor;
      const task = tasks[taskIdx];
      const prefer = task?.minutes && task.minutes >= 25 ? task.minutes : 60;
      const take = Math.min(90, prefer, need, room);
      if (take < 25) break;

      const title = task?.title?.trim() ? `Study · ${task.title.trim()}` : "Study";
      await createPlannerBlock({
        title,
        category: "study",
        start_at: localIsoFromDayMinutes(day, cursor),
        duration_minutes: take,
      });
      created += 1;
      minutesAdded += take;
      need -= take;
      cursor += take + 5;
      if (task) taskIdx += 1;
    }
    if (need < 25) break;
  }

  return { created, minutesAdded, shortfallAfter: Math.max(0, need) };
}

