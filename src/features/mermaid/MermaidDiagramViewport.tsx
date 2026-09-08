import { useCallback, useEffect, useRef, useState } from "react";
import { Maximize2, Minus, Plus, RotateCcw, Type } from "lucide-react";
import { Button } from "../../app/components/ui/button";
import {
  MERMAID_FONT_SIZE_OPTIONS,
  setMermaidNoteFontSize,
} from "./render";

const MIN_SCALE = 0.4;
const MAX_SCALE = 3;
const ZOOM_STEP = 0.15;

function clampScale(value: number): number {
  return Math.min(MAX_SCALE, Math.max(MIN_SCALE, value));
}

export function MermaidZoomControls({
  scale,
  onZoomIn,
  onZoomOut,
  onReset,
  onFit,
  disabled,
  atDefault,
}: {
  scale: number;
  onZoomIn: () => void;
  onZoomOut: () => void;
  onReset: () => void;
  onFit: () => void;
  disabled?: boolean;
  atDefault?: boolean;
}) {
  const pct = Math.round(scale * 100);
  return (
    <div
      className="study-mermaid-zoom-controls flex items-center gap-0.5 shrink-0"
      role="group"
      aria-label="Diagram zoom"
    >
      <Button
        type="button"
        variant="ghost"
        size="sm"
        className="h-7 w-7 p-0"
        onClick={onZoomOut}
        disabled={disabled || scale <= MIN_SCALE + 0.01}
        title="Zoom out"
        aria-label="Zoom out"
      >
        <Minus className="h-3.5 w-3.5" />
      </Button>
      <span className="min-w-[2.75rem] text-center text-[10px] tabular-nums text-muted-foreground">
        {pct}%
      </span>
      <Button
        type="button"
        variant="ghost"
        size="sm"
        className="h-7 w-7 p-0"
        onClick={onZoomIn}
        disabled={disabled || scale >= MAX_SCALE - 0.01}
        title="Zoom in"
        aria-label="Zoom in"
      >
        <Plus className="h-3.5 w-3.5" />
      </Button>
      <Button
        type="button"
        variant="ghost"
        size="sm"
        className="h-7 w-7 p-0"
        onClick={onFit}
        disabled={disabled}
        title="Fit to width"
        aria-label="Fit diagram to width"
      >
        <Maximize2 className="h-3.5 w-3.5" />
      </Button>
      <Button
        type="button"
        variant="ghost"
        size="sm"
        className="h-7 w-7 p-0"
        onClick={onReset}
        disabled={disabled || atDefault}
        title="Reset zoom and pan"
        aria-label="Reset zoom and pan"
      >
        <RotateCcw className="h-3.5 w-3.5" />
      </Button>
    </div>
  );
}

export function MermaidFontSizeControl({
  value,
  onChange,
  disabled,
}: {
  value: string;
  onChange: (size: string) => void;
  disabled?: boolean;
}) {
  const idx = MERMAID_FONT_SIZE_OPTIONS.findIndex((o) => o.value === value);
  const label = MERMAID_FONT_SIZE_OPTIONS[idx]?.label ?? "M";

  const cycle = () => {
    const next = MERMAID_FONT_SIZE_OPTIONS[(idx + 1) % MERMAID_FONT_SIZE_OPTIONS.length];
    onChange(next.value);
  };

  return (
    <Button
      type="button"
      variant="ghost"
      size="sm"
      className="h-7 gap-1 px-1.5 text-[10px] font-medium tabular-nums"
      onClick={cycle}
      disabled={disabled}
      title={`Label text size (${label}) — click to cycle S / M / L`}
      aria-label={`Diagram label text size ${label}`}
    >
      <Type className="h-3 w-3 shrink-0" />
      {label}
    </Button>
  );
}

/** Pan/zoom state for a rendered Mermaid SVG inside the block toolbar + viewport. */
export function useMermaidViewportControls(contentKey?: string) {
  const [scale, setScale] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const viewportRef = useRef<HTMLDivElement>(null);
  const innerRef = useRef<HTMLDivElement>(null);

  const resetView = useCallback(() => {
    setScale(1);
    setPan({ x: 0, y: 0 });
  }, []);

  useEffect(() => {
    resetView();
  }, [contentKey, resetView]);

  const fitToWidth = useCallback(() => {
    const viewport = viewportRef.current;
    const inner = innerRef.current;
    const svg = inner?.querySelector("svg");
    if (!viewport || !svg) return;
    const viewportWidth = viewport.clientWidth;
    const svgWidth = svg.getBoundingClientRect().width / scale;
    if (viewportWidth <= 0 || svgWidth <= 0) return;
    setScale(clampScale(viewportWidth / svgWidth));
    setPan({ x: 0, y: 0 });
  }, [scale]);

  const zoomBy = useCallback((delta: number) => {
    setScale((prev) => clampScale(prev + delta));
  }, []);

  const onWheel = useCallback((e: React.WheelEvent) => {
    if (!e.ctrlKey && !e.metaKey) return;
    e.preventDefault();
    const delta = e.deltaY > 0 ? -ZOOM_STEP : ZOOM_STEP;
    setScale((prev) => clampScale(prev + delta));
  }, []);

  const [panning, setPanning] = useState(false);
  const panStart = useRef<{ x: number; y: number; panX: number; panY: number } | null>(null);

  const onPointerDown = useCallback(
    (e: React.PointerEvent) => {
      if (e.button !== 0) return;
      const target = e.target as HTMLElement;
      if (target.closest("button, a, input, textarea, select")) return;
      panStart.current = { x: e.clientX, y: e.clientY, panX: pan.x, panY: pan.y };
      setPanning(true);
      (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
    },
    [pan.x, pan.y],
  );

  const onPointerMove = useCallback((e: React.PointerEvent) => {
    if (!panStart.current) return;
    const dx = e.clientX - panStart.current.x;
    const dy = e.clientY - panStart.current.y;
    setPan({ x: panStart.current.panX + dx, y: panStart.current.panY + dy });
  }, []);

  const onPointerUp = useCallback((e: React.PointerEvent) => {
    panStart.current = null;
    setPanning(false);
    try {
      (e.currentTarget as HTMLElement).releasePointerCapture(e.pointerId);
    } catch {
      /* already released */
    }
  }, []);

  return {
    scale,
    pan,
    panning,
    viewportRef,
    innerRef,
    resetView,
    fitToWidth,
    zoomBy,
    onWheel,
    onPointerDown,
    onPointerMove,
    onPointerUp,
  };
}
