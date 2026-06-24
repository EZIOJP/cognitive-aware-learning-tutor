import type { Editor } from "tldraw";
import type { StrokeMetricsSnapshot } from "./strokeMetrics";

/**
 * Unified canvas handle — superset of the StudySessionContext CanvasBridge,
 * so the intervention pipeline keeps working across Train/Practice/Study Room.
 *
 * Implemented by MathGridCanvas (fixed-grid sketch, full support) and
 * TldrawMathCanvas (Study Room; optional members are absent).
 */
export interface MathCanvasHandle {
  exportPng: () => Promise<string | null>;
  /** react-sketch-canvas CanvasPath[] (MathGridCanvas) or null (tldraw). */
  exportPaths: () => Promise<unknown[] | null>;
  hasContent: () => boolean;
  getEraserEventCount: () => number;
  resetEraserCount: () => void;
  clearAll: () => void;
  /** tldraw editor when backed by tldraw; null for the sketch canvas. */
  getEditor: () => Editor | null;
  /** Stroke kinematics — MathGridCanvas only. */
  exportStrokeMetrics?: () => StrokeMetricsSnapshot | null;
  /** Dynamic training layout — MathGridCanvas only. */
  setGridCells?: (n: number) => void;
  getGridCellCount?: () => number;
}
