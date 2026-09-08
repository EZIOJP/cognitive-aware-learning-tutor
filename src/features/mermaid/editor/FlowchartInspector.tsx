import {
  EDGE_HEAD_OPTIONS,
  EDGE_LINE_OPTIONS,
  NODE_PALETTE,
  SHAPE_OPTIONS,
  findEdge,
  findNode,
  measureNode,
  type EdgeHead,
  type EdgeLine,
  type FlowchartModel,
  type NodeShape,
} from "./model";
import type { CanvasSelection } from "./FlowchartCanvas";

export type FlowchartInspectorProps = {
  model: FlowchartModel;
  selection: CanvasSelection;
  onModelChange: (model: FlowchartModel) => void;
};

function patchNode(
  model: FlowchartModel,
  id: string,
  patch: Partial<FlowchartModel["nodes"][0]>,
): FlowchartModel {
  return {
    ...model,
    nodes: model.nodes.map((n) => (n.id === id ? { ...n, ...patch } : n)),
  };
}

function patchEdge(
  model: FlowchartModel,
  id: string,
  patch: Partial<FlowchartModel["edges"][0]>,
): FlowchartModel {
  return {
    ...model,
    edges: model.edges.map((e) => (e.id === id ? { ...e, ...patch } : e)),
  };
}

export function FlowchartInspector({ model, selection, onModelChange }: FlowchartInspectorProps) {
  if (!selection) {
    return (
      <div className="rounded-md border border-border/40 bg-muted/10 p-3 text-[11px] text-muted-foreground">
        Select a shape or connector to edit size, shape type, and line style.
      </div>
    );
  }

  if (selection.kind === "node") {
    const node = findNode(model, selection.id);
    if (!node) return null;
    const activeClass = node.classes[0] ?? "";

    return (
      <div className="space-y-2 rounded-md border border-border/40 bg-muted/10 p-3">
        <p className="text-[10px] uppercase tracking-wider text-muted-foreground">Shape · {node.id}</p>
        <label className="block space-y-1 text-[11px] text-muted-foreground">
          <span>Label</span>
          <input
            value={node.label}
            onChange={(e) => {
              const label = e.target.value;
              const size = measureNode(label, node.shape);
              onModelChange(patchNode(model, node.id, { label, w: size.w, h: Math.max(node.h, size.h) }));
            }}
            className="w-full rounded border border-border/50 bg-background px-2 py-1 text-xs text-foreground"
          />
        </label>
        <label className="block space-y-1 text-[11px] text-muted-foreground">
          <span>Shape</span>
          <select
            value={node.shape}
            onChange={(e) => {
              const shape = e.target.value as NodeShape;
              const size = measureNode(node.label, shape);
              onModelChange(
                patchNode(model, node.id, {
                  shape,
                  w: Math.max(node.w, size.w),
                  h: Math.max(node.h, size.h),
                }),
              );
            }}
            className="w-full rounded border border-border/50 bg-background px-2 py-1 text-xs text-foreground"
          >
            {SHAPE_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </label>
        <div className="grid grid-cols-2 gap-2">
          <label className="block space-y-1 text-[11px] text-muted-foreground">
            <span>Width</span>
            <input
              type="number"
              min={48}
              max={480}
              value={Math.round(node.w)}
              onChange={(e) =>
                onModelChange(patchNode(model, node.id, { w: Math.max(48, Number(e.target.value) || 48) }))
              }
              className="w-full rounded border border-border/50 bg-background px-2 py-1 text-xs text-foreground"
            />
          </label>
          <label className="block space-y-1 text-[11px] text-muted-foreground">
            <span>Height</span>
            <input
              type="number"
              min={32}
              max={320}
              value={Math.round(node.h)}
              onChange={(e) =>
                onModelChange(patchNode(model, node.id, { h: Math.max(32, Number(e.target.value) || 32) }))
              }
              className="w-full rounded border border-border/50 bg-background px-2 py-1 text-xs text-foreground"
            />
          </label>
        </div>
        <div className="space-y-1">
          <p className="text-[11px] text-muted-foreground">Color</p>
          <div className="flex flex-wrap gap-1.5">
            <button
              type="button"
              title="Clear"
              className={`h-6 w-6 rounded border ${!activeClass ? "border-emerald-400" : "border-border/50"} bg-slate-700`}
              onClick={() => onModelChange(patchNode(model, node.id, { classes: [] }))}
            />
            {NODE_PALETTE.map((p) => (
              <button
                key={p.name}
                type="button"
                title={p.label}
                className={`h-6 w-6 rounded border ${activeClass === p.name ? "border-emerald-400" : "border-border/50"}`}
                style={{ background: p.swatch }}
                onClick={() => {
                  const defs = model.classDefs.some((c) => c.name === p.name)
                    ? model.classDefs
                    : [...model.classDefs, { name: p.name, styles: p.styles }];
                  onModelChange({
                    ...patchNode(model, node.id, { classes: [p.name] }),
                    classDefs: defs,
                  });
                }}
              />
            ))}
          </div>
        </div>
      </div>
    );
  }

  const edge = findEdge(model, selection.id);
  if (!edge) return null;

  return (
    <div className="space-y-2 rounded-md border border-border/40 bg-muted/10 p-3">
      <p className="text-[10px] uppercase tracking-wider text-muted-foreground">
        Connector · {edge.source} → {edge.target}
      </p>
      <label className="block space-y-1 text-[11px] text-muted-foreground">
        <span>Label</span>
        <input
          value={edge.label}
          onChange={(e) => onModelChange(patchEdge(model, edge.id, { label: e.target.value }))}
          className="w-full rounded border border-border/50 bg-background px-2 py-1 text-xs text-foreground"
        />
      </label>
      <label className="block space-y-1 text-[11px] text-muted-foreground">
        <span>Line</span>
        <select
          value={edge.line}
          onChange={(e) => onModelChange(patchEdge(model, edge.id, { line: e.target.value as EdgeLine }))}
          className="w-full rounded border border-border/50 bg-background px-2 py-1 text-xs text-foreground"
        >
          {EDGE_LINE_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </label>
      <label className="block space-y-1 text-[11px] text-muted-foreground">
        <span>Arrow head</span>
        <select
          value={edge.head}
          onChange={(e) => onModelChange(patchEdge(model, edge.id, { head: e.target.value as EdgeHead }))}
          className="w-full rounded border border-border/50 bg-background px-2 py-1 text-xs text-foreground"
        >
          {EDGE_HEAD_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </label>
      <label className="flex items-center gap-2 text-[11px] text-muted-foreground">
        <input
          type="checkbox"
          checked={edge.bidirectional}
          onChange={(e) => onModelChange(patchEdge(model, edge.id, { bidirectional: e.target.checked }))}
        />
        Bidirectional
      </label>
      <label className="block space-y-1 text-[11px] text-muted-foreground">
        <span>Length hint (0–6)</span>
        <input
          type="number"
          min={0}
          max={6}
          value={edge.length}
          onChange={(e) =>
            onModelChange(
              patchEdge(model, edge.id, { length: Math.max(0, Math.min(6, Number(e.target.value) || 0)) }),
            )
          }
          className="w-full rounded border border-border/50 bg-background px-2 py-1 text-xs text-foreground"
        />
      </label>
    </div>
  );
}
