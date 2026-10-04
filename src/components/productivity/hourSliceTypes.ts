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

/** All segments paint overlapping; no lane/strip truncation. */
export function visibleSegments(slice: HourSlice): {
  shown: SessionSegment[];
  hidden: SessionSegment[];
  overflowN: number;
} {
  return { shown: [...slice.segments], hidden: [], overflowN: 0 };
}

export function abbreviateLabel(label: string, max = 6): string {
  const t = label.trim();
  if (max <= 0 || !t) return "";
  if (t.length <= max) return t;
  // Single-char chips: first letter only (no ellipsis — no room).
  if (max === 1) return t[0] ?? "";
  return `${t.slice(0, max - 1)}…`;
}
