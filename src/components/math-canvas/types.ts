import type { Editor } from "tldraw";

/**
 * Unified canvas handle — superset of the StudySessionContext CanvasBridge,
 * so the intervention pipeline keeps working across Train/Practice/Study Room.
 */
export interface MathCanvasHandle {
  exportPng: () => Promise<string | null>;
  /** tldraw has no sketch-canvas paths; returns null (backend masking is optional). */
  exportPaths: () => Promise<unknown[] | null>;
  hasContent: () => boolean;
  getEraserEventCount: () => number;
  resetEraserCount: () => void;
  clearAll: () => void;
  getEditor: () => Editor | null;
}
