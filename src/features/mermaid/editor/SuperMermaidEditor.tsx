/**
 * Visual Mermaid editor via react-super-mermaid (Excalidraw-style).
 * Edits nodes/edges on canvas; source panel is optional/advanced.
 */
import { useCallback, useMemo, useState } from "react";
import mermaid from "mermaid";
import { MermaidEditor, detectDiagramType } from "react-super-mermaid";

export type SuperMermaidEditorProps = {
  source: string;
  onSourceChange: (source: string) => void;
};

/** Diagram types with a full visual canvas in react-super-mermaid. */
const CANVAS_TYPES = new Set([
  "flowchart",
  "sequence",
  "class",
  "er",
  "state",
  "mindmap",
]);

export function isSuperMermaidEditable(source: string): boolean {
  const trimmed = source.trim();
  if (!trimmed) return true;
  const kind = detectDiagramType(trimmed);
  return kind != null && CANVAS_TYPES.has(kind);
}

export function SuperMermaidEditor({ source, onSourceChange }: SuperMermaidEditorProps) {
  const [showSource, setShowSource] = useState(false);
  const [editorError, setEditorError] = useState<string | null>(null);
  const kind = useMemo(() => detectDiagramType(source.trim()) ?? undefined, [source]);
  const canCanvas = !source.trim() || (kind != null && CANVAS_TYPES.has(kind));

  const onMermaidChange = useCallback(
    (text: string) => {
      setEditorError(null);
      if (text !== source) onSourceChange(text);
    },
    [onSourceChange, source],
  );

  if (!canCanvas || editorError) {
    return (
      <div className="mb-3 space-y-2">
        <p className="text-xs text-amber-200/90">
          {editorError
            ? `Canvas editor: ${editorError}`
            : kind
              ? `Diagram type “${kind}” has no visual canvas yet — edit Mermaid source.`
              : "Could not detect diagram type — edit Mermaid source."}{" "}
          Flowchart, sequence, class, ER, state, and mindmap open on the canvas.
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
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className="rounded bg-emerald-600/20 px-2 py-0.5 text-emerald-100/90">
          Visual edit · {kind || "new"}
        </span>
        <span className="text-muted-foreground">
          Drag nodes · connect from edge · double-click rename · right-click for shape/colour
        </span>
        <button
          type="button"
          className={`ml-auto rounded border px-2 py-0.5 ${
            showSource
              ? "border-emerald-500/40 bg-emerald-600/25 text-emerald-100"
              : "border-border/50 bg-muted/20 text-muted-foreground"
          }`}
          onClick={() => setShowSource((v) => !v)}
        >
          {showSource ? "Hide source" : "Source"}
        </button>
      </div>

      <div className="study-super-mermaid-host overflow-hidden rounded-md border border-border/50 bg-[#1a1b1e]">
        <MermaidEditor
          source={source.trim() || undefined}
          mermaid={mermaid}
          dark
          look="clean"
          toolbar
          defaultSource={false}
          className="min-h-[320px] w-full"
          style={{ minHeight: 320, height: 420 }}
          onMermaidChange={onMermaidChange}
          onError={(err) => {
            const msg = err instanceof Error ? err.message : String(err);
            setEditorError(msg.slice(0, 200));
          }}
        />
      </div>

      {showSource ? (
        <textarea
          value={source}
          onChange={(e) => onSourceChange(e.target.value)}
          spellCheck={false}
          rows={Math.min(12, Math.max(4, source.split("\n").length + 1))}
          className="study-note-editor-textarea w-full resize-y rounded-md border border-border/40 bg-black/20 px-3 py-2 font-mono text-[12px] leading-relaxed text-emerald-50/95 outline-none focus-visible:ring-1 focus-visible:ring-emerald-500/40"
          aria-label="Edit Mermaid source"
        />
      ) : null}
    </div>
  );
}
