/**
 * Split calendar plan blocks into per-hour segments for 2D track (X = minutes 0–60).
 */
import type { PlannerBlock, ProposedPlannerBlock } from "../../api/plannerClient";

export type PlanHourSeg = {
  blockId: number;
  title: string;
  category: string;
  color?: string | null;
  /** Hour of day 0–23 */
  hour: number;
  /** Inclusive start minute within the hour [0, 60) */
  start_min: number;
  /** Exclusive end minute within the hour (0, 60] */
  end_min: number;
  /** Continues from previous hour */
  seamLeft: boolean;
  /** Continues into next hour */
  seamRight: boolean;
  isDraft?: boolean;
  status?: string;
};

function dayKeyLocal(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

type BlockLike = {
  id: number;
  title: string;
  category: string;
  color?: string | null;
  start_at: string;
  end_at: string;
  status?: string;
  isDraft?: boolean;
};

/** Materialize one plan/draft into hour segments for `day` (local). */
export function planBlockToHourSegs(block: BlockLike, day: Date): PlanHourSeg[] {
  const dayK = dayKeyLocal(day);
  const start = new Date(block.start_at);
  const end = new Date(block.end_at);
  if (!(end > start)) return [];

  const out: PlanHourSeg[] = [];
  // Walk each local hour the block touches
  const cursor = new Date(start);
  cursor.setSeconds(0, 0);
  // Align to hour floor of start
  let guard = 0;
  while (cursor < end && guard++ < 48) {
    if (dayKeyLocal(cursor) !== dayK) {
      cursor.setHours(cursor.getHours() + 1, 0, 0, 0);
      continue;
    }
    const hour = cursor.getHours();
    const hourStart = new Date(cursor);
    hourStart.setMinutes(0, 0, 0);
    const hourEnd = new Date(hourStart);
    hourEnd.setHours(hourEnd.getHours() + 1);

    const segStart = start > hourStart ? start : hourStart;
    const segEnd = end < hourEnd ? end : hourEnd;
    if (segEnd <= segStart) {
      cursor.setTime(hourEnd.getTime());
      continue;
    }

    const start_min = Math.max(0, Math.min(59, segStart.getMinutes()));
    let end_min =
      segEnd.getTime() >= hourEnd.getTime()
        ? 60
        : Math.max(start_min + 1, Math.min(60, segEnd.getMinutes()));
    // If end is exactly on hour boundary minutes=0 → already handled as 60
    if (segEnd.getTime() < hourEnd.getTime() && segEnd.getSeconds() === 0 && segEnd.getMinutes() === 0) {
      end_min = 60;
    }

    out.push({
      blockId: block.id,
      title: block.title,
      category: block.category,
      color: block.color,
      hour,
      start_min,
      end_min: Math.max(start_min + 1, end_min),
      seamLeft: start < hourStart,
      seamRight: end > hourEnd,
      isDraft: block.isDraft,
      status: block.status,
    });

    cursor.setTime(hourEnd.getTime());
  }
  return out;
}

export function planBlocksToHourSegs(
  blocks: PlannerBlock[],
  day: Date,
  drafts?: ProposedPlannerBlock[] | null,
): PlanHourSeg[] {
  const dayK = dayKeyLocal(day);
  const segs: PlanHourSeg[] = [];

  for (const b of blocks) {
    const s = new Date(b.start_at);
    if (dayKeyLocal(s) !== dayK && dayKeyLocal(new Date(b.end_at)) !== dayK) {
      // may still span midnight into day — let splitter decide
    }
    segs.push(...planBlockToHourSegs(b, day));
  }

  (drafts || []).forEach((d, i) => {
    segs.push(
      ...planBlockToHourSegs(
        {
          id: -5000 - i,
          title: d.title,
          category: d.category,
          start_at: d.start_at,
          end_at: d.end_at,
          isDraft: true,
        },
        day,
      ),
    );
  });

  return segs;
}

export function segsByHour(segs: PlanHourSeg[]): Map<number, PlanHourSeg[]> {
  const m = new Map<number, PlanHourSeg[]>();
  for (const s of segs) {
    const list = m.get(s.hour) ?? [];
    list.push(s);
    m.set(s.hour, list);
  }
  return m;
}
