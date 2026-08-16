/**
 * Last-line / active-band bbox from StrokeMetricsSnapshot (mirrors backend Y-cluster lightly).
 */
import type { StrokeMetricsSnapshot } from "./strokeMetrics";

export type CropBbox = { x: number; y: number; w: number; h: number };

export function lastBandBboxFromMetrics(
  snapshot: StrokeMetricsSnapshot | null | undefined,
  gapRatio = 0.55,
  minGapPx = 8,
  pad = 12,
): CropBbox | null {
  if (!snapshot?.strokes?.length) return null;
  const pens = snapshot.strokes.filter((s) => s.tool === "pen" && s.bbox.w >= 0 && s.bbox.h >= 0);
  if (!pens.length) return null;

  const heights = pens.map((s) => Math.max(s.bbox.h, 1));
  const medianH = heights.slice().sort((a, b) => a - b)[Math.floor(heights.length / 2)] || 12;
  const mergeGap = Math.max(minGapPx, gapRatio * medianH);

  const sorted = pens.slice().sort((a, b) => a.bbox.y - b.bbox.y || a.bbox.x - b.bbox.x);
  type Cluster = { y0: number; y1: number; x0: number; x1: number };
  const clusters: Cluster[] = [];
  for (const s of sorted) {
    const { x, y, w, h } = s.bbox;
    const y1 = y + Math.max(h, 1);
    const x1 = x + Math.max(w, 1);
    let placed = false;
    for (const cl of clusters) {
      const gap = Math.max(0, y - cl.y1, cl.y0 - y1);
      if (gap <= mergeGap) {
        cl.y0 = Math.min(cl.y0, y);
        cl.y1 = Math.max(cl.y1, y1);
        cl.x0 = Math.min(cl.x0, x);
        cl.x1 = Math.max(cl.x1, x1);
        placed = true;
        break;
      }
    }
    if (!placed) clusters.push({ y0: y, y1, x0: x, x1 });
  }
  if (!clusters.length) return null;
  clusters.sort((a, b) => a.y0 - b.y0);
  const last = clusters[clusters.length - 1];
  return {
    x: Math.max(0, Math.round(last.x0 - pad)),
    y: Math.max(0, Math.round(last.y0 - pad)),
    w: Math.max(1, Math.round(last.x1 - last.x0 + 2 * pad)),
    h: Math.max(1, Math.round(last.y1 - last.y0 + 2 * pad)),
  };
}
