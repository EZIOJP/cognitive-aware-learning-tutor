import { useEffect, useId, useRef, useState } from "react";
import mermaid from "mermaid";
import { sanitizeMermaidSource } from "./mermaidSanitize";
import { isBrokenBlockContent } from "./noteBlockUtils";
import { useSectionBlockEdit, type SectionBlockHandlers } from "./useSectionBlockEdit";

let mermaidReady = false;

function ensureMermaidConfig() {
  if (mermaidReady) return;
  mermaid.initialize({
    startOnLoad: false,
    theme: "neutral",
    securityLevel: "loose",
    maxTextSize: 100_000,
    fontFamily: "ui-sans-serif, system-ui, sans-serif",
  });
  mermaidReady = true;
}

function useMermaidRender(source: string) {
  const ref = useRef<HTMLDivElement>(null);
  const reactId = useId().replace(/:/g, "");
  const renderSeq = useRef(0);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    const trimmed = sanitizeMermaidSource(source).trim();
    if (!trimmed || isBrokenBlockContent(trimmed)) {
      el.innerHTML = "";
      setError(isBrokenBlockContent(trimmed) ? "Diagram source is missing or invalid" : null);
      setLoading(false);
      return;
    }

    renderSeq.current += 1;
    const seq = renderSeq.current;
    setLoading(true);
    setError(null);
    ensureMermaidConfig();

    const timer = window.setTimeout(() => {
      const diagramId = `mermaid-${reactId}-${seq}`;
      mermaid
        .render(diagramId, trimmed)
        .then(({ svg }) => {
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
    }, 300);

    return () => window.clearTimeout(timer);
  }, [source, reactId]);

  return { ref, error, loading };
}

type MermaidBlockProps = {
  code: string;
  sectionHandlers?: SectionBlockHandlers;
};

export function MermaidBlock({ code, sectionHandlers }: MermaidBlockProps) {
  const [renderError, setRenderError] = useState<string | null>(null);

  const { editing, draft, setDraft, toolbar, localError, displayContent } = useSectionBlockEdit(
    code,
    sectionHandlers ? { ...sectionHandlers, language: "mermaid" } : undefined,
    renderError,
    {
      regenerateAutoSave: true,
      regenerateLabel: "Fix with AI",
      regenerateEditLabel: "Regenerate diagram",
      regenerateModeWhenEditing: "polish",
    },
  );

  const activeSource = editing ? draft : displayContent;
  const { ref, error, loading } = useMermaidRender(activeSource);

  useEffect(() => {
    setRenderError(error);
  }, [error]);

  return (
    <div className="study-mermaid-block my-4 overflow-hidden rounded-lg border border-border/60 bg-muted/20">
      <div className="flex items-center justify-between gap-2 border-b border-border/40 bg-muted/30 px-3 py-1.5">
        <span className="text-[10px] uppercase tracking-wide text-muted-foreground font-mono">mermaid</span>
        <div className="flex items-center gap-2">
          {loading && <span className="text-[10px] text-muted-foreground">Rendering…</span>}
          {toolbar}
        </div>
      </div>

      {editing && (
        <>
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
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

      {(localError || error) && (
        <div className="p-3 space-y-2 border-b border-border/30">
          <p className="text-xs text-destructive">{localError || error}</p>
          {error && (
            <p className="text-[10px] text-muted-foreground">
              {editing
                ? "Click Regenerate diagram — the parse error below is sent to the AI."
                : "Click Fix with AI — the parse error below is sent to the AI (local syntax fix runs first)."}
            </p>
          )}
        </div>
      )}

      {editing && (
        <div className="px-3 py-1 text-[10px] uppercase tracking-wide text-muted-foreground border-b border-border/20 bg-black/5">
          Live preview
        </div>
      )}

      {!error && !isBrokenBlockContent(activeSource) && (
        <div ref={ref} className="p-3 overflow-x-auto min-h-[4rem] flex items-center justify-center" />
      )}

      {!editing && error && (
        <pre className="mx-3 mb-3 text-[11px] text-muted-foreground whitespace-pre-wrap font-mono bg-muted/40 rounded p-2">
          {displayContent.trim() || "(empty)"}
        </pre>
      )}
    </div>
  );
}
