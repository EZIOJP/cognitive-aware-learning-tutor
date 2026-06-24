import { useCallback, useRef } from "react";
import {
  computeSnapshot,
  type SketchPath,
  type StrokeMetricsSnapshot,
} from "./strokeMetrics";

/**
 * Tracks the live path list + eraser events for MathGridCanvas and produces
 * StrokeMetricsSnapshot on demand (cheap; pure functions over current paths).
 */
export function useStrokeAnalytics(opts: {
  cellPx: number;
  onMetricsChange?: (snapshot: StrokeMetricsSnapshot) => void;
}) {
  const pathsRef = useRef<SketchPath[]>([]);
  const eraserEventsRef = useRef(0);
  const gridCellsRef = useRef(1);
  const { cellPx, onMetricsChange } = opts;
  const onMetricsChangeRef = useRef(onMetricsChange);
  onMetricsChangeRef.current = onMetricsChange;

  const snapshot = useCallback(
    (): StrokeMetricsSnapshot =>
      computeSnapshot(pathsRef.current, {
        cellPx,
        gridCells: gridCellsRef.current,
        eraserEvents: eraserEventsRef.current,
      }),
    [cellPx]
  );

  const onPathsChange = useCallback(
    (paths: SketchPath[]) => {
      pathsRef.current = paths;
      onMetricsChangeRef.current?.(snapshot());
    },
    [snapshot]
  );

  const onEraserStroke = useCallback(() => {
    eraserEventsRef.current += 1;
  }, []);

  const reset = useCallback(() => {
    pathsRef.current = [];
    eraserEventsRef.current = 0;
    onMetricsChangeRef.current?.(snapshot());
  }, [snapshot]);

  return {
    pathsRef,
    eraserEventsRef,
    gridCellsRef,
    snapshot,
    onPathsChange,
    onEraserStroke,
    reset,
  };
}
