import { useCallback, useEffect, useState } from "react";
import { FlowchartCanvas, type CanvasSelection } from "./FlowchartCanvas";
import { FlowchartInspector } from "./FlowchartInspector";
import { applyAutoLayout, normalizePositions } from "./layout";
import { cloneModel, nextNodeId, measureNode, type FlowchartModel } from "./model";
import { parseFlowchart } from "./parse";
import { serializeFlowchart } from "./serialize";

export type FlowchartEditorProps = {
  source: string;
  onSourceChange: (source: string) => void;
};

type Mode = "canvas" | "source";

export function FlowchartEditor({ source, onSourceChange }: FlowchartEditorProps) {
  const [mode, setMode] = useState<Mode>("canvas");
  const [model, setModel] = useState<FlowchartModel | null>(null);
  const [parseError, setParseError] = useState<string | null>(null);
  const [warnings, setWarnings] = useState<string[]>([]);
  const [selection, setSelection] = useState<CanvasSelection>(null);
  const [layoutBusy, setLayoutBusy] = useState(false);

  const loadFromSource = useCallback(async (src: string) => {
    const parsed = parseFlowchart(src);
    if (!parsed.ok) {
      setModel(null);
      setParseError(parsed.reason);
      setWarnings([]);
      return;
    }
    setParseError(null);
    setWarnings(parsed.warnings);
    setLayoutBusy(true);
    try {
      const laid = await applyAutoLayout(cloneModel(parsed.model));
      normalizePositions(laid);
      setModel(laid);
    } finally {
      setLayoutBusy(false);
    }
  }, []);

  useEffect(() => {
    void loadFromSource(source);
    // Only re-parse when switching into editor with new initial source — not on every keystroke from ourselves.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const pushModel = useCallback(
    (next: FlowchartModel) => {
      setModel(next);
      onSourceChange(serializeFlowchart(next, { layout: true }));
    },
    [onSourceChange],
  );

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (mode !== "canvas" || !model || !selection) return;
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
      if (e.key !== "Delete" && e.key !== "Backspace") return;
      e.preventDefault();
      const next = cloneModel(model);
      if (selection.kind === "node") {
        next.nodes = next.nodes.filter((n) => n.id !== selection.id);
        next.edges = next.edges.filter((ed) => ed.source !== selection.id && ed.target !== selection.id);
        next.subgraphs = next.subgraphs.map((sg) => ({
          ...sg,
          nodeIds: sg.nodeIds.filter((id) => id !== selection.id),
        }));
      } else {
        next.edges = next.edges.filter((ed) => ed.id !== selection.id);
      }
      setSelection(null);
      pushModel(next);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [mode, model, selection, pushModel]);

  const addNode = () => {
    if (!model) return;
    const next = cloneModel(model);
    const id = nextNodeId(next);
    const size = measureNode(id, "rect");
    const boundsY = next.nodes.length ? Math.max(...next.nodes.map((n) => n.y)) + 80 : 80;
    next.nodes.push({
      id,
      label: id,
      shape: "rect",
      classes: [],
      x: 120 + (next.nodes.length % 4) * 40,
      y: boundsY,
      w: size.w,
      h: size.h,
    });
    pushModel(next);
    setSelection({ kind: "node", id });
  };

  const relayout = async () => {
    if (!model) return;
    setLayoutBusy(true);
    try {
      const laid = await applyAutoLayout(cloneModel(model), { force: true });
      normalizePositions(laid);
      pushModel(laid);
    } finally {
      setLayoutBusy(false);
    }
  };

  if (layoutBusy && !model) {
    return (
      <p className="mb-3 text-xs text-muted-foreground" aria-busy="true">
        Opening canvas…
      </p>
    );
  }

  if (parseError || !model) {
    return (
      <div className="space-y-2">
        <p className="text-xs text-amber-200/90">
          {parseError || "Could not open graphical editor."} Editing as Mermaid source instead.
        </p>
        <textarea
          value={source}
          onChange={(e) => onSourceChange(e.target.value)}
          spellCheck={false}
          rows={Math.min(16, Math.max(5, source.split("\n").length + 1))}
          className="study-note-editor-textarea w-full resize-y rounded-md border border-border/40 bg-black/20 px-3 py-2 font-mono text-[12px] leading-relaxed text-emerald-50/95 outline-none focus-visible:ring-1 focus-visible:ring-emerald-500/40"
          aria-label="Edit Mermaid source"
        />
      </div>
    );
  }

  return (
    <div className="mb-3 space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <div className="inline-flex rounded-md border border-border/50 overflow-hidden text-xs">
          <button
            type="button"
            className={`px-2.5 py-1 ${mode === "canvas" ? "bg-emerald-600/30 text-emerald-100" : "bg-muted/20 text-muted-foreground"}`}
            onClick={() => setMode("canvas")}
          >
            Canvas
          </button>
          <button
            type="button"
            className={`px-2.5 py-1 ${mode === "source" ? "bg-emerald-600/30 text-emerald-100" : "bg-muted/20 text-muted-foreground"}`}
            onClick={() => {
              setMode("source");
              if (model) onSourceChange(serializeFlowchart(model, { layout: true }));
            }}
          >
            Source
          </button>
        </div>
        {mode === "canvas" && (
          <>
            <button
              type="button"
              className="rounded border border-border/50 px-2 py-1 text-xs text-muted-foreground hover:text-foreground"
              onClick={addNode}
            >
              + Node
            </button>
            <button
              type="button"
              disabled={layoutBusy}
              className="rounded border border-border/50 px-2 py-1 text-xs text-muted-foreground hover:text-foreground disabled:opacity-40"
              onClick={() => void relayout()}
            >
              {layoutBusy ? "Layout…" : "Auto-layout"}
            </button>
          </>
        )}
      </div>

      {warnings.length > 0 && (
        <p className="text-[11px] text-amber-200/80">{warnings.join(" ")}</p>
      )}

      {mode === "source" ? (
        <textarea
          value={source}
          onChange={(e) => {
            onSourceChange(e.target.value);
          }}
          onBlur={() => void loadFromSource(source)}
          spellCheck={false}
          rows={Math.min(16, Math.max(5, source.split("\n").length + 1))}
          className="study-note-editor-textarea w-full resize-y rounded-md border border-border/40 bg-black/20 px-3 py-2 font-mono text-[12px] leading-relaxed text-emerald-50/95 outline-none focus-visible:ring-1 focus-visible:ring-emerald-500/40"
          aria-label="Edit Mermaid source"
        />
      ) : (
        <div className="grid gap-2 lg:grid-cols-[1fr_220px]">
          <FlowchartCanvas
            model={model}
            selection={selection}
            onSelectionChange={setSelection}
            onModelChange={pushModel}
          />
          <FlowchartInspector model={model} selection={selection} onModelChange={pushModel} />
        </div>
      )}
    </div>
  );
}

/** True when source looks like a flowchart the canvas can edit. */
export function isFlowchartEditable(source: string): boolean {
  return /^(flowchart|graph)\b/im.test(source.trim());
}
