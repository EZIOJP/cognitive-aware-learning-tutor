import type { ProposedPlannerBlock } from "../../api/plannerClient";

const DAY_END_MIN = 23 * 60;

function dayKey(iso: string): string {
  const d = new Date(iso);
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function sourcePriority(source?: string): number {
  // Lower = keeps the earlier slot when two start together
  if (source === "routine") return 0;
  if (source === "existing") return 1;
  if (source === "study" || !source) return 2;
  if (source === "break") return 3;
  return 4;
}

function durationMin(b: ProposedPlannerBlock): number {
  return Math.max(
    10,
    Math.round((new Date(b.end_at).getTime() - new Date(b.start_at).getTime()) / 60_000),
  );
}

function startMin(b: ProposedPlannerBlock): number {
  const d = new Date(b.start_at);
  return d.getHours() * 60 + d.getMinutes();
}

function withLocalRange(
  b: ProposedPlannerBlock,
  day: string,
  startM: number,
  endM: number,
): ProposedPlannerBlock {
  const [y, mo, d] = day.split("-").map(Number);
  const start = new Date(y, mo - 1, d, 0, 0, 0, 0);
  start.setMinutes(startM);
  const end = new Date(y, mo - 1, d, 0, 0, 0, 0);
  end.setMinutes(endM);
  return { ...b, start_at: start.toISOString(), end_at: end.toISOString() };
}

function nearlySame(a: ProposedPlannerBlock, b: ProposedPlannerBlock): boolean {
  if ((a.title || "").trim().toLowerCase() !== (b.title || "").trim().toLowerCase()) return false;
  if ((a.source || "study") !== (b.source || "study")) return false;
  return Math.abs(new Date(a.start_at).getTime() - new Date(b.start_at).getTime()) < 2 * 60_000;
}

/**
 * Remove near-duplicate blocks, then cascade later blocks so nothing overlaps.
 * Same-start ties: routine > existing > study > break (winner keeps the slot).
 */
export function resolveProposedOverlaps(blocks: ProposedPlannerBlock[]): ProposedPlannerBlock[] {
  if (blocks.length <= 1) return blocks;

  // Dedupe near-identical (e.g. double Bible from routine+calendar)
  const deduped: ProposedPlannerBlock[] = [];
  for (const b of blocks) {
    if (deduped.some((x) => nearlySame(x, b))) continue;
    deduped.push(b);
  }

  const byDay = new Map<string, ProposedPlannerBlock[]>();
  for (const b of deduped) {
    const k = dayKey(b.start_at);
    const row = byDay.get(k) ?? [];
    row.push(b);
    byDay.set(k, row);
  }

  const out: ProposedPlannerBlock[] = [];
  for (const [day, dayBlocks] of [...byDay.entries()].sort(([a], [b]) => a.localeCompare(b))) {
    const sorted = [...dayBlocks].sort((a, b) => {
      const ds = startMin(a) - startMin(b);
      if (ds !== 0) return ds;
      return sourcePriority(a.source) - sourcePriority(b.source);
    });

    let cursor = -1;
    for (const b of sorted) {
      let s = startMin(b);
      let dur = durationMin(b);
      if (s < cursor) s = cursor;
      let e = s + dur;
      if (e > DAY_END_MIN) {
        if (s >= DAY_END_MIN - 5) continue;
        e = DAY_END_MIN;
        dur = e - s;
        if (dur < 10) continue;
      }
      out.push(withLocalRange(b, day, s, e));
      cursor = e;
    }
  }
  return out;
}

export function proposedBlocksEqualTimes(
  a: ProposedPlannerBlock[],
  b: ProposedPlannerBlock[],
): boolean {
  if (a.length !== b.length) return false;
  for (let i = 0; i < a.length; i++) {
    if (a[i].start_at !== b[i].start_at || a[i].end_at !== b[i].end_at) return false;
    if ((a[i].title || "") !== (b[i].title || "")) return false;
    if ((a[i].source || "") !== (b[i].source || "")) return false;
  }
  return true;
}
