/**
 * Build 2D day-grid hour_slices from overlay sessions when the native
 * enforcer returns hour_slices: [] (Focus/C++ path).
 * Aligns with mergeForCalendar + backend/planner/hour_slices.py clipping.
 */
import type { ActualSession } from "../../api/plannerClient";
import { agentDebugLog } from "../../lib/agentDebugLog";
import type { HourSlice, HourSliceSource, SessionSegment } from "./hourSliceTypes";
import { mergeForCalendar, shortAppName, type MergedInterval } from "./planVsActualUtils";
import { format } from "date-fns";

function isSleepMerged(m: MergedInterval): boolean {
  const cat = (m.category || "").toLowerCase();
  const src = (m.source || "").toLowerCase();
  const app = (m.app_name || "").toLowerCase();
  return cat === "sleep" || src === "wearable_sleep" || app === "amazfit";
}

function sourceTag(m: MergedInterval): HourSliceSource {
  return isSleepMerged(m) ? "sleep" : "desktop";
}

function overlaps(a0: number, a1: number, b0: number, b1: number): boolean {
  return a0 < b1 && b0 < a1;
}

function laneFree(
  occupied: Array<[number, number, number]>,
  lane: number,
  startMin: number,
  endMin: number,
): boolean {
  return !occupied.some(
    ([o0, o1, oLane]) => oLane === lane && overlaps(startMin, endMin, o0, o1),
  );
}

type HourSeg = {
  session_group_id: string;
  source: HourSliceSource;
  app_or_label: string;
  category: string;
  start_min: number;
  end_min: number;
  session_ids: string[];
  lane_index: number;
};

function clipRunToHour(m: MergedInterval, hourStart: Date): HourSeg | null {
  const runStart = new Date(m.start_time).getTime();
  const runEnd = new Date(m.end_time).getTime();
  const h0 = hourStart.getTime();
  const h1 = h0 + 60 * 60 * 1000;
  const start = Math.max(runStart, h0);
  const end = Math.min(runEnd, h1);
  if (end <= start) return null;
  let startMin = Math.floor((start - h0) / 60_000);
  const endDelta = (end - h0) / 60_000;
  let endMin = endDelta === Math.floor(endDelta) ? endDelta : Math.floor(endDelta) + 1;
  endMin = Math.max(startMin + 1, Math.min(60, endMin));
  startMin = Math.max(0, Math.min(59, startMin));
  if (endMin <= startMin) endMin = Math.min(60, startMin + 1);
  const sleep = isSleepMerged(m);
  let sleepLabel = "Sleep";
  if (sleep) {
    // Keep real wall-clock span in the chip so wake-day clips (00:00…) don't look
    // like a fake midnight bedtime.
    const rs = new Date(m.start_time);
    const re = new Date(m.end_time);
    if (Number.isFinite(rs.getTime()) && Number.isFinite(re.getTime())) {
      const fmt = (d: Date) =>
        d.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
      sleepLabel = `Sleep · ${fmt(rs)}–${fmt(re)}`;
    }
  }
  return {
    session_group_id: `${m.app_name || m.category || "act"}|${m.start_time}`,
    source: sourceTag(m),
    app_or_label: sleep ? sleepLabel : shortAppName(m.app_name) || m.category || "Activity",
    category: sleep ? "Sleep" : m.category || "Other",
    start_min: startMin,
    end_min: endMin,
    session_ids: (m.children?.map((c) => c.session_id).filter(Boolean) as string[]) ||
      (m.session_id ? [m.session_id] : []),
    lane_index: -1,
  };
}

function assignLanes(segments: HourSeg[], pins: Map<string, number>): Map<string, number> {
  if (!segments.length) return new Map();
  const sleepSegs = segments.filter((s) => s.source === "sleep");
  const deskSegs = segments.filter((s) => s.source !== "sleep");
  const sleepReserved = sleepSegs.length > 0;
  const minDesk = sleepReserved ? 1 : 0;
  const occupied: Array<[number, number, number]> = [];

  for (const seg of sleepSegs) {
    seg.lane_index = 0;
    occupied.push([seg.start_min, seg.end_min, 0]);
  }

  deskSegs.sort((a, b) => a.start_min - b.start_min || a.session_group_id.localeCompare(b.session_group_id));
  for (const seg of deskSegs) {
    let assigned: number | null = null;
    const preferred = pins.get(seg.session_group_id);
    if (preferred != null) {
      let lane = preferred;
      if (sleepReserved && lane === 0) lane = minDesk;
      if (lane >= minDesk && laneFree(occupied, lane, seg.start_min, seg.end_min)) {
        assigned = lane;
      }
    }
    if (assigned == null) {
      let lane = minDesk;
      while (!laneFree(occupied, lane, seg.start_min, seg.end_min)) lane += 1;
      assigned = lane;
    }
    seg.lane_index = assigned;
    occupied.push([seg.start_min, seg.end_min, assigned]);
  }

  const next = new Map<string, number>();
  for (const seg of segments) {
    if (seg.lane_index >= 0) next.set(seg.session_group_id, seg.lane_index);
  }
  return next;
}

/** Convert overlay sessions → HourSlice[] for DayGridActualLayer. */
export function buildHourSlicesFromSessions(
  sessions: ActualSession[],
  day: Date,
): HourSlice[] {
  if (!sessions.length) return [];
  const merged = mergeForCalendar(sessions);
  if (!merged.length) return [];

  const dayStart = new Date(day);
  dayStart.setHours(0, 0, 0, 0);
  const dateKey = format(dayStart, "yyyy-MM-dd");
  const out: HourSlice[] = [];
  let pins = new Map<string, number>();

  // Overnight sleep that started last evening: expose as negative hours so the
  // wake-day track can show a leading 11 PM row (not a fake midnight bedtime).
  let leadFrom = 0;
  for (const m of merged) {
    if (!isSleepMerged(m)) continue;
    const t0 = new Date(m.start_time).getTime();
    const t1 = new Date(m.end_time).getTime();
    if (!Number.isFinite(t0) || !Number.isFinite(t1)) continue;
    if (t0 >= dayStart.getTime() || t1 <= dayStart.getTime()) continue;
    const startHour = new Date(t0).getHours();
    const hoursBefore = Math.ceil((dayStart.getTime() - t0) / 3_600_000);
    leadFrom = Math.max(leadFrom, Math.min(6, Math.max(1, hoursBefore)));
    for (let h = startHour; h < 24; h++) {
      const hourStart = new Date(t0);
      hourStart.setHours(h, 0, 0, 0);
      if (hourStart.getTime() >= dayStart.getTime()) break;
      const clip = clipRunToHour(m, hourStart);
      if (!clip) continue;
      const railHour = h - 24; // e.g. 23 → -1
      out.push({
        date: dateKey,
        hour: railHour,
        lane_count: 1,
        segments: [
          {
            session_group_id: clip.session_group_id,
            source: clip.source,
            app_or_label: clip.app_or_label,
            category: clip.category,
            start_min: clip.start_min,
            end_min: clip.end_min,
            lane_index: 0,
            total_lanes_this_hour: 1,
            session_ids: clip.session_ids,
            duration_min: Math.max(0, clip.end_min - clip.start_min),
          },
        ],
      });
    }
  }
  for (let hour = 0; hour < 24; hour++) {
    const hourStart = new Date(dayStart);
    hourStart.setHours(hour, 0, 0, 0);
    const segs: HourSeg[] = [];
    for (const m of merged) {
      const clip = clipRunToHour(m, hourStart);
      if (clip) segs.push(clip);
    }
    pins = assignLanes(segs, pins);
    if (!segs.length) continue;
    const laneCount = Math.max(0, ...segs.map((s) => s.lane_index)) + 1;
    const segments: SessionSegment[] = segs.map((s) => ({
      session_group_id: s.session_group_id,
      source: s.source,
      app_or_label: s.app_or_label,
      category: s.category,
      start_min: s.start_min,
      end_min: s.end_min,
      lane_index: s.lane_index,
      total_lanes_this_hour: laneCount,
      session_ids: s.session_ids,
      duration_min: Math.max(0, s.end_min - s.start_min),
    }));
    out.push({ date: dateKey, hour, lane_count: laneCount, segments });
  }
  // #region agent log
  {
    const sleepHours = out
      .filter((h) => h.segments.some((s) => s.source === "sleep"))
      .map((h) => ({
        hour: h.hour,
        segs: h.segments
          .filter((s) => s.source === "sleep")
          .map((s) => ({ start_min: s.start_min, end_min: s.end_min })),
      }));
    const deskHours = out.filter((h) => h.segments.some((s) => s.source === "desktop")).length;
    const mergedSleep = merged.filter(isSleepMerged).map((m) => ({
      start: m.start_time,
      end: m.end_time,
      localStart: new Date(m.start_time).toString(),
      localEnd: new Date(m.end_time).toString(),
    }));
    agentDebugLog({
      hypothesisId: "D",
      location: "buildHourSlices.ts",
      message: "hour slices built",
      data: {
        dateKey,
        sessionCount: sessions.length,
        mergedCount: merged.length,
        sliceHours: out.length,
        deskHoursWithSegs: deskHours,
        sleepHours,
        mergedSleep,
        negRail: out.filter((h) => h.hour < 0).map((h) => h.hour),
        leadFrom,
      },
    });
  }
  // #endregion
  return out;
}

/** Leading rail hours (negative slice.hour count) for overnight sleep on wake day. */
export function overnightLeadHoursFromSlices(slices: HourSlice[]): number {
  let minH = 0;
  for (const s of slices) {
    if (s.hour < minH) minH = s.hour;
  }
  return minH < 0 ? -minH : 0;
}
