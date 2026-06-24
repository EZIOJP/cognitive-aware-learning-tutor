/**
 * Pure stroke-kinematics helpers for MathGridCanvas.
 * Computed from react-sketch-canvas CanvasPath data (withTimestamp enabled),
 * so every metric is reproducible from exported paths_json.
 */

export interface SketchPoint {
  x: number;
  y: number;
}

export interface SketchPath {
  paths: SketchPoint[];
  strokeWidth: number;
  strokeColor: string;
  drawMode: boolean;
  startTimestamp?: number;
  endTimestamp?: number;
}

export interface StrokeMetrics {
  strokeIndex: number;
  tool: "pen" | "eraser";
  startTime: number;
  endTime: number;
  durationMs: number;
  lengthPx: number;
  pointCount: number;
  strokeWidth: number;
  /** Length-weighted mean segment angle, axial 0–180° (0 = horizontal). */
  avgAngleDeg: number;
  dominantDirection: "horizontal" | "vertical" | "diagonal" | "point";
  segmentAnglesDeg: number[];
  gridCell: { col: number; row: number };
  bbox: { x: number; y: number; w: number; h: number };
}

export interface StrokeMetricsSnapshot {
  cellPx: number;
  gridCells: number;
  totalStrokes: number;
  totalInkLengthPx: number;
  totalDrawingTimeMs: number;
  eraserEvents: number;
  /** key "col,row" → pen stroke count in that grid cell */
  strokesPerCell: Record<string, number>;
  pauseBetweenStrokesMs: number[];
  strokes: StrokeMetrics[];
}

function dist(a: SketchPoint, b: SketchPoint): number {
  return Math.hypot(b.x - a.x, b.y - a.y);
}

/** Axial angle of a segment in degrees within [0, 180). 0 = horizontal, 90 = vertical. */
export function segmentAngleDeg(a: SketchPoint, b: SketchPoint): number {
  const deg = (Math.atan2(b.y - a.y, b.x - a.x) * 180) / Math.PI;
  return ((deg % 180) + 180) % 180;
}

export function strokeLengthPx(points: SketchPoint[]): number {
  let len = 0;
  for (let i = 1; i < points.length; i++) len += dist(points[i - 1], points[i]);
  return len;
}

export function strokeBbox(points: SketchPoint[]): { x: number; y: number; w: number; h: number } {
  if (!points.length) return { x: 0, y: 0, w: 0, h: 0 };
  let minX = points[0].x;
  let minY = points[0].y;
  let maxX = points[0].x;
  let maxY = points[0].y;
  for (const p of points) {
    if (p.x < minX) minX = p.x;
    if (p.y < minY) minY = p.y;
    if (p.x > maxX) maxX = p.x;
    if (p.y > maxY) maxY = p.y;
  }
  return { x: minX, y: minY, w: maxX - minX, h: maxY - minY };
}

export function gridCellOf(points: SketchPoint[], cellPx: number): { col: number; row: number } {
  if (!points.length || cellPx <= 0) return { col: 0, row: 0 };
  let cx = 0;
  let cy = 0;
  for (const p of points) {
    cx += p.x;
    cy += p.y;
  }
  cx /= points.length;
  cy /= points.length;
  return { col: Math.max(0, Math.floor(cx / cellPx)), row: Math.max(0, Math.floor(cy / cellPx)) };
}

/**
 * Length-weighted axial mean angle. Axial data (no direction) is averaged by
 * doubling angles so 5° and 175° correctly average near horizontal.
 */
export function avgAxialAngleDeg(points: SketchPoint[]): number {
  let sumSin = 0;
  let sumCos = 0;
  for (let i = 1; i < points.length; i++) {
    const w = dist(points[i - 1], points[i]);
    if (w === 0) continue;
    const theta = (segmentAngleDeg(points[i - 1], points[i]) * Math.PI) / 90; // doubled, radians
    sumSin += w * Math.sin(theta);
    sumCos += w * Math.cos(theta);
  }
  if (sumSin === 0 && sumCos === 0) return 0;
  const halved = Math.atan2(sumSin, sumCos) / 2;
  return ((halved * 180) / Math.PI + 180) % 180;
}

export function dominantDirection(
  avgAngle: number,
  lengthPx: number
): StrokeMetrics["dominantDirection"] {
  if (lengthPx < 2) return "point";
  if (avgAngle < 25 || avgAngle > 155) return "horizontal";
  if (avgAngle > 65 && avgAngle < 115) return "vertical";
  return "diagonal";
}

export function computeStrokeMetrics(
  path: SketchPath,
  strokeIndex: number,
  cellPx: number
): StrokeMetrics {
  const points = path.paths ?? [];
  const lengthPx = strokeLengthPx(points);
  const avgAngle = avgAxialAngleDeg(points);
  const start = path.startTimestamp ?? 0;
  const end = path.endTimestamp ?? start;
  const segmentAngles: number[] = [];
  for (let i = 1; i < points.length; i++) {
    segmentAngles.push(Math.round(segmentAngleDeg(points[i - 1], points[i]) * 10) / 10);
  }
  return {
    strokeIndex,
    tool: path.drawMode ? "pen" : "eraser",
    startTime: start,
    endTime: end,
    durationMs: Math.max(0, end - start),
    lengthPx: Math.round(lengthPx * 10) / 10,
    pointCount: points.length,
    strokeWidth: path.strokeWidth,
    avgAngleDeg: Math.round(avgAngle * 10) / 10,
    dominantDirection: dominantDirection(avgAngle, lengthPx),
    segmentAnglesDeg: segmentAngles,
    gridCell: gridCellOf(points, cellPx),
    bbox: strokeBbox(points),
  };
}

export function computeSnapshot(
  paths: SketchPath[],
  opts: { cellPx: number; gridCells: number; eraserEvents: number }
): StrokeMetricsSnapshot {
  const strokes = paths.map((p, i) => computeStrokeMetrics(p, i, opts.cellPx));
  const strokesPerCell: Record<string, number> = {};
  let totalInk = 0;
  let totalTime = 0;
  for (const s of strokes) {
    if (s.tool !== "pen") continue;
    totalInk += s.lengthPx;
    totalTime += s.durationMs;
    const key = `${s.gridCell.col},${s.gridCell.row}`;
    strokesPerCell[key] = (strokesPerCell[key] ?? 0) + 1;
  }
  const pauses: number[] = [];
  for (let i = 1; i < strokes.length; i++) {
    const gap = strokes[i].startTime - strokes[i - 1].endTime;
    if (strokes[i].startTime > 0 && strokes[i - 1].endTime > 0 && gap >= 0) {
      pauses.push(Math.round(gap));
    }
  }
  return {
    cellPx: opts.cellPx,
    gridCells: opts.gridCells,
    totalStrokes: strokes.filter((s) => s.tool === "pen").length,
    totalInkLengthPx: Math.round(totalInk * 10) / 10,
    totalDrawingTimeMs: Math.round(totalTime),
    eraserEvents: opts.eraserEvents,
    strokesPerCell,
    pauseBetweenStrokesMs: pauses,
    strokes,
  };
}
