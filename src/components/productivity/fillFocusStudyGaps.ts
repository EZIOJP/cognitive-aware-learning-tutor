import {
  createPlannerBlock,
  deletePlannerBlock,
  type PlannerBlock,
  type StudyTask,
} from "../../api/plannerClient";

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

type Gap = { start: number; end: number };

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

  const wake = parseHmToMinutes(opts.wakeHm, 7 * 60);
  const bed = parseHmToMinutes(opts.bedtimeHm, 23 * 60);
  let winStart = Math.min(Math.max(wake + 30, 8 * 60), 12 * 60);
  let winEnd = bed > 12 * 60 ? Math.max(winStart + 60, bed - 60) : 21 * 60;
  if (winEnd <= winStart) {
    winStart = 9 * 60;
    winEnd = 18 * 60;
  }

  const occupied = opts.blocks
    .filter((b) => b.status !== "cancelled" && b.status !== "rolled")
    .map(blockSpanMinutes);

  const gaps = freeGaps(occupied, winStart, winEnd);
  const day = new Date();
  const tasks = (opts.studyTasks || []).filter((t) => t.title?.trim());
  let taskIdx = 0;
  let created = 0;
  let minutesAdded = 0;

  for (const gap of gaps) {
    let cursor = gap.start;
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

