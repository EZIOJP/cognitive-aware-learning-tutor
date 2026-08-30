import {
  forwardRef,
  useCallback,
  useImperativeHandle,
  useRef,
  useState,
} from "react";
import { ReactSketchCanvas, type ReactSketchCanvasRef } from "react-sketch-canvas";
import { Download, Eraser, NotebookPen, Pencil, Redo2, Trash2, Undo2 } from "lucide-react";
import { Button } from "../../app/components/ui/button";
import { Slider } from "../../app/components/ui/slider";
import { FixedGridOverlay } from "./FixedGridOverlay";
import { useStrokeAnalytics } from "./useStrokeAnalytics";
import type { SketchPath, StrokeMetricsSnapshot } from "./strokeMetrics";
import type { MathCanvasHandle } from "./types";

const COLORS = ["#000000", "#ef4444", "#3b82f6", "#22c55e", "#f59e0b"];

export const MATH_GRID_CELL_PX = 48;

/** Transparent sketch exports need a white matte for OCR ink detection. */
async function compositeOnWhite(dataUrl: string): Promise<string> {
  const img = new Image();
  await new Promise<void>((resolve, reject) => {
    img.onload = () => resolve();
    img.onerror = () => reject(new Error("Failed to load canvas export"));
    img.src = dataUrl;
  });
  const canvas = document.createElement("canvas");
  canvas.width = img.naturalWidth || img.width;
  canvas.height = img.naturalHeight || img.height;
  const ctx = canvas.getContext("2d");
  if (!ctx) return dataUrl;
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(img, 0, 0);
  return canvas.toDataURL("image/png");
}

interface MathGridCanvasProps {
  /** Highlighted training character cells (0 = plain ruled grid). */
  gridCells?: number;
  /** Faded prompt text rendered inside the highlighted cells. */
  ghostText?: string;
  /** Show the amber rough-work side pane (excluded from OCR exports). */
  roughPane?: boolean;
  onCanvasChange?: (stamp: string) => void;
  onEraserStroke?: () => void;
  /** Live stroke analytics callback — fires after every stroke. */
  onMetricsChange?: (snapshot: StrokeMetricsSnapshot) => void;
}

/**
 * Fixed-viewport math canvas for OCR pages (Train / Practice / Recognize).
 * No zoom, no pan. The ruled grid is a CSS layer behind a transparent sketch
 * canvas, so PNG exports contain ink only.
 */
export const MathGridCanvas = forwardRef<MathCanvasHandle, MathGridCanvasProps>(
  function MathGridCanvas(
    { gridCells = 0, ghostText = "", roughPane = false, onCanvasChange, onEraserStroke, onMetricsChange },
    ref
  ) {
    const mainRef = useRef<ReactSketchCanvasRef>(null);
    const roughRef = useRef<ReactSketchCanvasRef>(null);
    const [tool, setTool] = useState<"pen" | "eraser">("pen");
    const [strokeColor, setStrokeColor] = useState(COLORS[0]);
    const [strokeWidth, setStrokeWidth] = useState(3);
    const [eraserWidth, setEraserWidth] = useState(14);
    const [showRough, setShowRough] = useState(roughPane);
    const [cells, setCells] = useState(gridCells);
    const hasInkRef = useRef(false);

    // Prop drives cells unless setGridCells was called with a different value.
    const lastGridCellsProp = useRef(gridCells);
    if (lastGridCellsProp.current !== gridCells) {
      lastGridCellsProp.current = gridCells;
      setCells(gridCells);
    }

    const analytics = useStrokeAnalytics({ cellPx: MATH_GRID_CELL_PX, onMetricsChange });
    analytics.gridCellsRef.current = cells;

    const onCanvasChangeRef = useRef(onCanvasChange);
    const onEraserStrokeRef = useRef(onEraserStroke);
    onCanvasChangeRef.current = onCanvasChange;
    onEraserStrokeRef.current = onEraserStroke;

    const selectTool = useCallback((next: "pen" | "eraser") => {
      setTool(next);
      mainRef.current?.eraseMode(next === "eraser");
      roughRef.current?.eraseMode(next === "eraser");
    }, []);

    const clearAll = useCallback(() => {
      mainRef.current?.clearCanvas();
      roughRef.current?.clearCanvas();
      hasInkRef.current = false;
      analytics.reset();
      onCanvasChangeRef.current?.("");
    }, [analytics]);

    const exportPng = useCallback(async () => {
      try {
        const raw = await mainRef.current?.exportImage("png");
        if (!raw) return null;
        return compositeOnWhite(raw);
      } catch {
        return null;
      }
    }, []);

    const exportPaths = useCallback(async () => {
      try {
        return (await mainRef.current?.exportPaths()) ?? null;
      } catch {
        return null;
      }
    }, []);

    const handleDownload = useCallback(async () => {
      const png = await exportPng();
      if (!png) return;
      const a = document.createElement("a");
      a.href = png;
      a.download = `math-canvas-${Date.now()}.png`;
      a.click();
    }, [exportPng]);

    useImperativeHandle(
      ref,
      () => ({
        exportPng,
        exportPaths,
        exportStrokeMetrics: () => analytics.snapshot(),
        hasContent: () => hasInkRef.current,
        getEraserEventCount: () => analytics.eraserEventsRef.current,
        resetEraserCount: () => {
          analytics.eraserEventsRef.current = 0;
        },
        clearAll,
        getEditor: () => null,
        setGridCells: (n: number) => setCells(Math.max(0, n)),
        getGridCellCount: () => cells,
      }),
      [exportPng, exportPaths, clearAll, analytics, cells]
    );

    return (
      <div className="math-grid-canvas flex flex-col h-full min-h-[320px]">
        <div className="flex flex-wrap items-center gap-2 p-2 border-b bg-muted/30 shrink-0">
          <Button
            size="sm"
            variant={tool === "pen" ? "default" : "outline"}
            title="Pen"
            onClick={() => selectTool("pen")}
          >
            <Pencil className="w-4 h-4" />
          </Button>
          <Button
            size="sm"
            variant={tool === "eraser" ? "default" : "outline"}
            title="Eraser"
            onClick={() => selectTool("eraser")}
          >
            <Eraser className="w-4 h-4" />
          </Button>
          <div className="flex gap-1">
            {COLORS.map((c) => (
              <button
                key={c}
                type="button"
                title={`Pen color ${c}`}
                onClick={() => {
                  setStrokeColor(c);
                  selectTool("pen");
                }}
                className={`w-7 h-7 rounded border-2 ${
                  strokeColor === c && tool === "pen" ? "border-primary" : "border-transparent"
                }`}
                style={{ backgroundColor: c }}
              />
            ))}
          </div>
          <Slider
            className="w-24"
            min={1}
            max={20}
            step={1}
            value={[tool === "pen" ? strokeWidth : eraserWidth]}
            onValueChange={(v) => (tool === "pen" ? setStrokeWidth(v[0]) : setEraserWidth(v[0]))}
          />
          <Button size="sm" variant="outline" title="Undo" onClick={() => mainRef.current?.undo()}>
            <Undo2 className="w-4 h-4" />
          </Button>
          <Button size="sm" variant="outline" title="Redo" onClick={() => mainRef.current?.redo()}>
            <Redo2 className="w-4 h-4" />
          </Button>
          <Button size="sm" variant="outline" title="Clear" onClick={clearAll}>
            <Trash2 className="w-4 h-4" />
          </Button>
          <Button size="sm" variant="outline" title="Download PNG" onClick={() => void handleDownload()}>
            <Download className="w-4 h-4" />
          </Button>
          <Button
            size="sm"
            variant={showRough ? "secondary" : "ghost"}
            title="Toggle rough-work pane"
            onClick={() => setShowRough((v) => !v)}
          >
            <NotebookPen className="w-4 h-4" />
          </Button>
        </div>

        <div className="flex-1 flex gap-2 p-2 min-h-0">
          <div
            className={`${showRough ? "flex-[0_0_65%]" : "flex-1"} relative min-h-[240px] rounded-lg border overflow-hidden bg-white`}
            style={{ touchAction: "none" }}
          >
            <FixedGridOverlay cellPx={MATH_GRID_CELL_PX} cells={cells} ghostText={ghostText} />
            <ReactSketchCanvas
              ref={mainRef}
              withTimestamp
              strokeWidth={strokeWidth}
              eraserWidth={eraserWidth}
              strokeColor={strokeColor}
              canvasColor="transparent"
              onChange={(paths) => {
                hasInkRef.current = paths.some((p) => p.drawMode && p.paths.length > 0);
                analytics.onPathsChange(paths as SketchPath[]);
              }}
              onStroke={(_path, isEraser) => {
                if (isEraser) {
                  analytics.onEraserStroke();
                  onEraserStrokeRef.current?.();
                }
                onCanvasChangeRef.current?.(`stroke-${Date.now()}`);
              }}
              style={{ position: "absolute", inset: 0, border: "none" }}
              className="w-full h-full"
            />
          </div>

          {showRough && (
            <div
              className="flex-[0_0_35%] flex flex-col min-h-0 rounded-lg border overflow-hidden bg-amber-50 dark:bg-amber-950/30"
              style={{ touchAction: "none" }}
            >
              <div className="text-xs px-2 py-1 bg-amber-600/80 text-white border-b shrink-0">
                Rough work (not recognized)
              </div>
              <div className="flex-1 min-h-[160px]">
                <ReactSketchCanvas
                  ref={roughRef}
                  strokeWidth={strokeWidth}
                  eraserWidth={eraserWidth}
                  strokeColor={strokeColor}
                  canvasColor="transparent"
                  style={{ border: "none" }}
                  className="w-full h-full"
                />
              </div>
            </div>
          )}
        </div>
      </div>
    );
  }
);
