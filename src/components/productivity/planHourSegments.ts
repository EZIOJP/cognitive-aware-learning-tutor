/**
 * Plan blocks → hour segments for the 2D track (X = minutes 0–60).
 * Each block paints only in its start hour (no carry into later rows).
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
  /** Overlap lane within this hour (0-based). */
  lane_index?: number;
  /** Concurrent lane count for this hour cluster. */
  lane_count?: number;
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

/** Materialize one plan/draft into hour segments for `day` (local).
 *  One segment only — the start hour. No carry into later hour rows.
 */
export function planBlockToHourSegs(block: BlockLike, day: Date): PlanHourSeg[] {
  const dayK = dayKeyLocal(day);
  const start = new Date(block.start_at);
  const end = new Date(block.end_at);
  if (!(end > start)) return [];
  if (dayKeyLocal(start) !== dayK) return [];

  const hour = start.getHours();
  const hourStart = new Date(start);
  hourStart.setMinutes(0, 0, 0);
  const hourEnd = new Date(hourStart);
  hourEnd.setHours(hourEnd.getHours() + 1);

  // Clip paint to the start hour (do not continue into the next row).
  const segStart = start;
  const segEnd = end < hourEnd ? end : hourEnd;
  if (segEnd <= segStart) return [];

  const start_min = Math.max(0, Math.min(59, segStart.getMinutes()));
  const end_min =
    segEnd.getTime() >= hourEnd.getTime()
      ? 60
      : Math.max(start_min + 1, Math.min(60, segEnd.getMinutes()));

  return [
    {
      blockId: block.id,
      title: block.title,
      category: block.category,
      color: block.color,
      hour,
      start_min,
      end_min: Math.max(start_min + 1, end_min),
      seamLeft: false,
      seamRight: false,
      isDraft: block.isDraft,
      status: block.status,
    },
  ];
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

function overlapsMin(a0: number, a1: number, b0: number, b1: number): boolean {
  return a0 < b1 && b0 < a1;
}

/** Pack overlapping plan segs in one hour into vertical lanes (same axis as actuals). */
export function assignPlanLanes(segs: PlanHourSeg[]): PlanHourSeg[] {
  if (!segs.length) return segs;
  const sorted = [...segs].sort(
    (a, b) => a.start_min - b.start_min || b.end_min - a.end_min || a.blockId - b.blockId,
  );
  const occupied: Array<[number, number, number]> = [];
  const out: PlanHourSeg[] = [];
  for (const seg of sorted) {
    let lane = 0;
    while (occupied.some(([o0, o1, oL]) => oL === lane && overlapsMin(seg.start_min, seg.end_min, o0, o1))) {
      lane += 1;
    }
    occupied.push([seg.start_min, seg.end_min, lane]);
    out.push({ ...seg, lane_index: lane });
  }
  const maxLane = Math.max(0, ...out.map((s) => s.lane_index ?? 0));
  const laneCount = maxLane + 1;
  return out.map((s) => ({ ...s, lane_count: laneCount }));
}

export function segsByHour(segs: PlanHourSeg[]): Map<number, PlanHourSeg[]> {
  const m = new Map<number, PlanHourSeg[]>();
  for (const s of segs) {
    const list = m.get(s.hour) ?? [];
    list.push(s);
    m.set(s.hour, list);
  }
  for (const [hour, list] of m) {
    m.set(hour, assignPlanLanes(list));
  }
  return m;
}
