/** Types for backend hour_slices on GET /api/planner/overlay/actual */

export type HourSliceSource = "desktop" | "sleep" | "plan_actual";

export type SessionSegment = {
  session_group_id: string;
  source: HourSliceSource;
  app_or_label: string;
  category: string;
  start_min: number;
  end_min: number;
  lane_index: number;
  total_lanes_this_hour: number;
  session_ids: string[];
  duration_min: number;
};

export type HourSlice = {
  date: string;
  hour: number;
  lane_count: number;
  segments: SessionSegment[];
};

export function complexityTier(laneCount: number): "full" | "side" | "compressed" | "overflow" {
  if (laneCount <= 1) return "full";
  if (laneCount === 2) return "side";
  if (laneCount <= 4) return "compressed";
  return "overflow";
}

/** Visible segments for an hour (duration-weighted top 3 when overflow). */
export function visibleSegments(slice: HourSlice): {
  shown: SessionSegment[];
  hidden: SessionSegment[];
  overflowN: number;
} {
  const segs = [...slice.segments];
  if (complexityTier(slice.lane_count) !== "overflow") {
    return { shown: segs, hidden: [], overflowN: 0 };
  }
  const ranked = [...segs].sort((a, b) => b.duration_min - a.duration_min || a.lane_index - b.lane_index);
  const shown = ranked.slice(0, 3);
  const hidden = ranked.slice(3);
  return { shown, hidden, overflowN: hidden.length };
}

export function abbreviateLabel(label: string, max = 6): string {
  const t = label.trim();
  if (max <= 0 || !t) return "";
  if (t.length <= max) return t;
  // Single-char chips: first letter only (no ellipsis — no room).
  if (max === 1) return t[0] ?? "";
  return `${t.slice(0, max - 1)}…`;
}
