import { useEffect, useId, useLayoutEffect, useRef, useState } from "react";
import { layoutSafeMermaidSource } from "./pipeline";
import { renderMermaidSvg, validateMermaidSource } from "./render";

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
  const [renderedSource, setRenderedSource] = useState("");

  useLayoutEffect(() => {
    if (paused) return;

    const trimmed = layoutSafeMermaidSource(source);
    setRenderedSource(trimmed);

    if (!trimmed.trim()) {
      if (ref.current) ref.current.innerHTML = "";
      setError(null);
      setLoading(false);
      return;
    }

    renderSeq.current += 1;
    const seq = renderSeq.current;
    setLoading(true);
    setError(null);

    const timer = window.setTimeout(() => {
      const diagramId = `mermaid-${reactId}-${seq}`;
      void validateMermaidSource(trimmed)
        .then((parseError) => {
          if (parseError) throw new Error(parseError);
          return renderMermaidSvg(diagramId, trimmed);
        })
        .then((svg) => {
          if (seq !== renderSeq.current || !ref.current) return;
          ref.current.innerHTML = svg;
          setLoading(false);
        })
        .catch((err: unknown) => {
          if (seq !== renderSeq.current) return;
          const msg = err instanceof Error ? err.message : "Mermaid render failed";
          setError(msg);
          setLoading(false);
          if (ref.current) ref.current.innerHTML = "";
        });
    }, 50);

    return () => window.clearTimeout(timer);
  }, [source, reactId, paused]);

  return { ref, error, loading, renderedSource };
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
  const { ref, error, loading, renderedSource } = useMermaidRender(activeSource, paused);
  const previewSource = renderedSource || layoutSafeMermaidSource(activeSource);

  useEffect(() => {
    onRenderError?.(error);
  }, [error, onRenderError]);

  return (
    <div className="study-mermaid-block relative my-4 overflow-hidden rounded-lg border border-border/60 bg-muted/20">
      <div className="flex items-center justify-between gap-2 border-b border-border/40 bg-muted/30 px-3 py-1.5">
        <span className="text-[10px] uppercase tracking-wide text-muted-foreground font-mono">mermaid</span>
        <div className="flex items-center gap-2">
          {loading && !paused && (
            <span className="text-[10px] text-muted-foreground">Rendering…</span>
          )}
          {toolbar}
        </div>
      </div>

      {editing && onDraftChange && (
        <>
          <textarea
            value={draft}
            onChange={(e) => onDraftChange(e.target.value)}
            spellCheck={false}
            rows={Math.min(16, Math.max(5, draft.split("\n").length + 1))}
            className="study-note-editor-textarea w-full resize-y bg-black/20 px-3 py-2 font-mono text-[12px] leading-relaxed text-emerald-50/95 outline-none border-b border-border/30"
            aria-label="Edit Mermaid source"
          />
          <div className="px-3 py-1.5 text-[10px] text-emerald-300/70 border-b border-border/20 bg-black/10">
            Edit your diagram → <strong className="text-emerald-200">Regenerate diagram</strong> (AI polish) →{" "}
            <strong className="text-emerald-200">Save block</strong> when preview looks right.
          </div>
        </>
      )}

      {(localError || error) && !paused && (
        <div className="p-3 space-y-2 border-b border-border/30">
          <p className="text-xs text-destructive">{localError || error}</p>
          {error && !localError && (
            <p className="text-[10px] text-muted-foreground">
              Click <strong>Fix syntax</strong> to save layout-safe labels (no AI wait).
            </p>
          )}
        </div>
      )}

      {editing && (
        <div className="px-3 py-1 text-[10px] uppercase tracking-wide text-muted-foreground border-b border-border/20 bg-black/5">
          Live preview
        </div>
      )}

      <div
        ref={ref}
        className={`p-3 overflow-x-auto min-h-[4rem] flex items-center justify-center${error ? " hidden" : ""}`}
        aria-hidden={error ? true : undefined}
      />

      {!editing && error && !paused && (
        <pre className="mx-3 mb-3 text-[11px] text-muted-foreground whitespace-pre-wrap font-mono bg-muted/40 rounded p-2">
          {previewSource || "(empty)"}
        </pre>
      )}
    </div>
  );
}
