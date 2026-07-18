import { useEffect, useId, useLayoutEffect, useRef, useState } from "react";
import { renderMermaidInto } from "./render";

export type MermaidBlockViewProps = {
  source: string;
  paused?: boolean;
  toolbar?: React.ReactNode;
  editing?: boolean;
  draft?: string;
  onDraftChange?: (value: string) => void;
  localError?: string | null;
  onRenderError?: (error: string | null) => void;
};

function useMermaidRender(source: string, paused: boolean) {
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

    // Must be measurable — never keep display:none on the host while Mermaid runs.
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
  }, [source, reactId, paused]);

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
  const { ref, error, loading } = useMermaidRender(activeSource, paused);

  useEffect(() => {
    onRenderError?.(error);
  }, [error, onRenderError]);

  return (
    <div className="study-mermaid-block group relative my-4 overflow-hidden rounded-lg border border-border/60 bg-muted/15">
      <div className="study-mermaid-toolbar flex items-center justify-between gap-2 border-b border-border/40 bg-muted/25 px-3 py-1.5">
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-[10px] uppercase tracking-wide text-muted-foreground font-mono shrink-0">
            mermaid
          </span>
          {loading && !paused && (
            <span className="text-[10px] text-muted-foreground truncate">Rendering…</span>
          )}
        </div>
        {toolbar ? <div className="shrink-0">{toolbar}</div> : null}
      </div>

      <div className="p-3 sm:p-4">
        {editing && onDraftChange && (
          <textarea
            value={draft}
            onChange={(e) => onDraftChange(e.target.value)}
            spellCheck={false}
            rows={Math.min(16, Math.max(5, draft.split("\n").length + 1))}
            className="study-note-editor-textarea mb-3 w-full resize-y rounded-md border border-border/40 bg-black/20 px-3 py-2 font-mono text-[12px] leading-relaxed text-emerald-50/95 outline-none focus-visible:ring-1 focus-visible:ring-emerald-500/40"
            aria-label="Edit Mermaid source"
          />
        )}

        {(localError || error) && !paused && (
          <div className="mb-3 space-y-1 rounded-md border border-destructive/25 bg-destructive/10 px-3 py-2">
            <p className="text-xs text-destructive">{localError || error}</p>
            <p className="text-[11px] text-muted-foreground">
              Edit the diagram or use <strong>Fix with AI</strong>.
            </p>
          </div>
        )}

        <div ref={ref} className="study-mermaid-render w-full overflow-x-auto" />

        {!editing && error && !paused && (
          <pre className="mt-3 text-[11px] text-muted-foreground whitespace-pre-wrap font-mono bg-muted/30 rounded-md p-2 border border-border/30">
            {activeSource.trim() || "(empty)"}
          </pre>
        )}
      </div>
    </div>
  );
}
