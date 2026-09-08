import { lazy, Suspense, useEffect, useId, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import {
  MermaidFontSizeControl,
  MermaidZoomControls,
  useMermaidViewportControls,
} from "./MermaidDiagramViewport";
import { getMermaidNoteFontSize, renderMermaidInto, setMermaidNoteFontSize } from "./render";

const SuperMermaidEditor = lazy(() =>
  import("./editor/SuperMermaidEditor").then((m) => ({ default: m.SuperMermaidEditor })),
);

export type MermaidBlockViewProps = {
  source: string;
  paused?: boolean;
  toolbar?: ReactNode;
  editing?: boolean;
  draft?: string;
  onDraftChange?: (value: string) => void;
  localError?: string | null;
  onRenderError?: (error: string | null) => void;
};

function useMermaidRender(source: string, paused: boolean, fontSize: string) {
  const ref = useRef<HTMLDivElement>(null);
  const reactId = useId().replace(/:/g, "");
  const renderSeq = useRef(0);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useLayoutEffect(() => {
    if (paused) return;

    const trimmed = source.trim();
    const host = ref.current;
    if (!host) return;

    host.hidden = false;
    host.style.display = "block";

    if (!trimmed) {
      host.replaceChildren();
      setError(null);
      setLoading(false);
      return;
    }

    renderSeq.current += 1;
    const seq = renderSeq.current;
    setLoading(true);
    setError(null);

    let cancelled = false;
    void renderMermaidInto(host, trimmed)
      .then(() => {
        if (cancelled || seq !== renderSeq.current) return;
        setLoading(false);
      })
      .catch((err: unknown) => {
        if (cancelled || seq !== renderSeq.current) return;
        const msg = err instanceof Error ? err.message : "Mermaid render failed";
        setError(msg);
        setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [source, reactId, paused, fontSize]);

  return { ref, error, loading };
}

export function MermaidBlockView({
  source,
  paused = false,
  toolbar,
  editing = false,
  draft = "",
  onDraftChange,
  localError,
  onRenderError,
}: MermaidBlockViewProps) {
  const activeSource = editing ? draft : source;
  const [fontSize, setFontSize] = useState(getMermaidNoteFontSize);
  const { ref, error, loading } = useMermaidRender(activeSource, paused || editing, fontSize);
  const contentKey = `${activeSource.trim()}:${fontSize}`;
  const viewport = useMermaidViewportControls(contentKey);

  useEffect(() => {
    onRenderError?.(error);
  }, [error, onRenderError]);

  const onFontSizeChange = (size: string) => {
    setMermaidNoteFontSize(size);
    setFontSize(size);
  };

  const viewDisabled = paused || loading || !!error || !activeSource.trim();
  const atDefault = viewport.scale === 1 && viewport.pan.x === 0 && viewport.pan.y === 0;

  return (
    <div className="study-mermaid-block group relative my-4 overflow-hidden rounded-lg border border-border/60 bg-muted/15">
      <div className="study-mermaid-toolbar flex items-center justify-between gap-2 border-b border-border/40 bg-muted/25 px-3 py-1.5">
        <div className="flex items-center gap-2 min-w-0 flex-wrap">
          <span className="text-[10px] uppercase tracking-wide text-muted-foreground font-mono shrink-0">
            mermaid
          </span>
          {loading && !paused && !editing && (
            <span className="text-[10px] text-muted-foreground truncate">Rendering…</span>
          )}
          {!editing && (
            <>
              <MermaidFontSizeControl
                value={fontSize}
                onChange={onFontSizeChange}
                disabled={viewDisabled}
              />
              <MermaidZoomControls
                scale={viewport.scale}
                onZoomIn={() => viewport.zoomBy(0.15)}
                onZoomOut={() => viewport.zoomBy(-0.15)}
                onReset={viewport.resetView}
                onFit={viewport.fitToWidth}
                disabled={viewDisabled}
                atDefault={atDefault}
              />
            </>
          )}
        </div>
        {toolbar ? <div className="shrink-0">{toolbar}</div> : null}
      </div>

      <div className="p-3 sm:p-4">
        {editing && onDraftChange ? (
          <Suspense
            fallback={
              <p className="mb-3 text-xs text-muted-foreground" aria-busy="true">
                Loading visual editor…
              </p>
            }
          >
            <SuperMermaidEditor source={draft} onSourceChange={onDraftChange} />
          </Suspense>
        ) : null}
        {(localError || error) && !paused && !editing && (
          <div className="mb-3 space-y-1 rounded-md border border-destructive/25 bg-destructive/10 px-3 py-2">
            <p className="text-xs text-destructive">{localError || error}</p>
            <p className="text-[11px] text-muted-foreground">
              Edit the diagram or use <strong>Fix with AI</strong>.
            </p>
          </div>
        )}

        {!editing && (
          <div
            ref={viewport.viewportRef}
            className={`study-mermaid-viewport${viewport.panning ? " is-panning" : ""}`}
            onWheel={viewport.onWheel}
            onPointerDown={viewport.onPointerDown}
            onPointerMove={viewport.onPointerMove}
            onPointerUp={viewport.onPointerUp}
            onPointerCancel={viewport.onPointerUp}
            title="Ctrl+scroll to zoom · drag to pan"
          >
            <div
              ref={viewport.innerRef}
              className="study-mermaid-viewport-inner"
              style={{
                transform: `translate(${viewport.pan.x}px, ${viewport.pan.y}px) scale(${viewport.scale})`,
              }}
            >
              <div ref={ref} className="study-mermaid-render w-full" />
            </div>
          </div>
        )}

        {!editing && error && !paused && (
          <pre className="mt-3 text-[11px] text-muted-foreground whitespace-pre-wrap font-mono bg-muted/30 rounded-md p-2 border border-border/30">
            {activeSource.trim() || "(empty)"}
          </pre>
        )}
      </div>
    </div>
  );
}
