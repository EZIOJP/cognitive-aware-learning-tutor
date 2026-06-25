import { useEffect, useId, useRef, useState } from "react";
import { Loader2 } from "lucide-react";
import { aggressiveSanitizeMermaidSource, sanitizeMermaidSource } from "./mermaidSanitize";
import { renderMermaidSvg, validateMermaidSource } from "./mermaidConfig";
import { isBrokenBlockContent } from "./noteBlockUtils";
import { useSectionBlockEdit, type SectionBlockHandlers } from "./useSectionBlockEdit";

function layoutSafeSource(source: string): string {
  return aggressiveSanitizeMermaidSource(sanitizeMermaidSource(source)).trim();
}

function useMermaidRender(
  source: string,
  paused: boolean,
  onHealed?: (healed: string) => void,
) {
  const ref = useRef<HTMLDivElement>(null);
  const reactId = useId().replace(/:/g, "");
  const renderSeq = useRef(0);
  const healedRef = useRef(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [renderedSource, setRenderedSource] = useState("");

  useEffect(() => {
    healedRef.current = false;
  }, [source]);

  useEffect(() => {
    const el = ref.current;
    if (!el || paused) return;

    const trimmed = layoutSafeSource(source);
    setRenderedSource(trimmed);

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
          if (
            onHealed &&
            !healedRef.current &&
            trimmed !== source.trim() &&
            trimmed.length > 0
          ) {
            healedRef.current = true;
            onHealed(trimmed);
          }
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
  }, [source, reactId, paused, onHealed]);

  return { ref, error, loading, renderedSource };
}

type MermaidBlockProps = {
  code: string;
  sectionHandlers?: SectionBlockHandlers;
};

export function MermaidBlock({ code, sectionHandlers }: MermaidBlockProps) {
  const [renderError, setRenderError] = useState<string | null>(null);

  const handlersWithLang = sectionHandlers
    ? { ...sectionHandlers, language: "mermaid" as const }
    : undefined;

  const aiRegenerating =
    handlersWithLang != null &&
    handlersWithLang.regeneratingBlock === handlersWithLang.blockIndex;

  const { editing, draft, setDraft, toolbar, localError, displayContent } = useSectionBlockEdit(
    code,
    handlersWithLang,
    renderError,
    {
      regenerateAutoSave: true,
      regenerateLabel: "Fix with AI",
      regenerateEditLabel: "Regenerate diagram",
      regenerateModeWhenEditing: "polish",
    },
  );

  const activeSource = editing ? draft : displayContent;

  const handleHealed = (healed: string) => {
    if (!handlersWithLang?.onBlockSave || editing) return;
    void handlersWithLang.onBlockSave(handlersWithLang.blockIndex, "mermaid", healed).catch(() => {
      // useSectionBlockEdit surfaces save errors for toolbar actions; auto-heal is best-effort
    });
  };

  const { ref, error, loading, renderedSource } = useMermaidRender(
    activeSource,
    aiRegenerating,
    handleHealed,
  );

  useEffect(() => {
    setRenderError(error);
  }, [error]);

  const previewSource = renderedSource || layoutSafeSource(activeSource);

  return (
    <div className="study-mermaid-block relative my-4 overflow-hidden rounded-lg border border-border/60 bg-muted/20">
      {aiRegenerating && (
        <div
          className="absolute inset-0 z-20 flex flex-col items-center justify-center gap-2 bg-black/65 backdrop-blur-[1px]"
          aria-live="polite"
          aria-busy="true"
        >
          <Loader2 className="h-6 w-6 animate-spin text-emerald-400" />
          <span className="text-xs font-medium text-emerald-100">Fixing diagram with AI…</span>
          <span className="text-[10px] text-emerald-200/70">Keep this tab open — scroll position is preserved</span>
        </div>
      )}

      <div className="flex items-center justify-between gap-2 border-b border-border/40 bg-muted/30 px-3 py-1.5">
        <span className="text-[10px] uppercase tracking-wide text-muted-foreground font-mono">mermaid</span>
        <div className="flex items-center gap-2">
          {loading && !aiRegenerating && (
            <span className="text-[10px] text-muted-foreground">Rendering…</span>
          )}
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

      {(localError || error) && !aiRegenerating && (
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

      {!error && !isBrokenBlockContent(activeSource) && (
        <div ref={ref} className="p-3 overflow-x-auto min-h-[4rem] flex items-center justify-center" />
      )}

      {!editing && error && !aiRegenerating && (
        <pre className="mx-3 mb-3 text-[11px] text-muted-foreground whitespace-pre-wrap font-mono bg-muted/40 rounded p-2">
          {previewSource || "(empty)"}
        </pre>
      )}
    </div>
  );
}
