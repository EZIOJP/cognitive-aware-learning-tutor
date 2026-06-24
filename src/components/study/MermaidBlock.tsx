import { useEffect, useId, useRef, useState } from "react";
import mermaid from "mermaid";

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

type MermaidBlockProps = {
  code: string;
};

export function MermaidBlock({ code }: MermaidBlockProps) {
  const ref = useRef<HTMLDivElement>(null);
  const reactId = useId().replace(/:/g, "");
  const renderSeq = useRef(0);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    const trimmed = code.trim();
    if (!trimmed) {
      el.innerHTML = "";
      setError(null);
      setLoading(false);
      return;
    }

    renderSeq.current += 1;
    const seq = renderSeq.current;
    setLoading(true);
    setError(null);
    ensureMermaidConfig();

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
  }, [code, reactId]);

  return (
    <div className="study-mermaid-block my-4 overflow-hidden rounded-lg border border-border/60 bg-muted/20">
      <div className="flex items-center justify-between gap-2 border-b border-border/40 bg-muted/30 px-3 py-1.5">
        <span className="text-[10px] uppercase tracking-wide text-muted-foreground font-mono">mermaid</span>
        {loading && <span className="text-[10px] text-muted-foreground">Rendering…</span>}
      </div>
      {error ? (
        <div className="p-3 space-y-2">
          <p className="text-xs text-destructive">{error}</p>
          <pre className="text-[11px] text-muted-foreground whitespace-pre-wrap font-mono bg-muted/40 rounded p-2">
            {code.trim()}
          </pre>
        </div>
      ) : (
        <div ref={ref} className="p-3 overflow-x-auto min-h-[3rem] flex items-center justify-center" />
      )}
    </div>
  );
}
