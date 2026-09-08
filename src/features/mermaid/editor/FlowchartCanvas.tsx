import { useCallback, useMemo, useRef, useState, type PointerEvent as ReactPointerEvent } from "react";
import {
  edgeGeometry,
  nodeBounds,
  shapeGeometry,
  type Point,
} from "./geometry";
import {
  cloneModel,
  findNode,
  labelLines,
  nextEdgeId,
  NODE_PALETTE,
  type FlowchartModel,
  type FlowEdge,
  type FlowNode,
} from "./model";

export type CanvasSelection =
  | { kind: "node"; id: string }
  | { kind: "edge"; id: string }
  | null;

type DragMode =
  | { type: "move"; id: string; ox: number; oy: number; startX: number; startY: number }
  | { type: "resize"; id: string; corner: "se" | "sw" | "ne" | "nw"; startW: number; startH: number; startX: number; startY: number; ox: number; oy: number }
  | { type: "link"; fromId: string; x: number; y: number }
  | null;

export type FlowchartCanvasProps = {
  model: FlowchartModel;
  selection: CanvasSelection;
  onSelectionChange: (sel: CanvasSelection) => void;
  onModelChange: (model: FlowchartModel) => void;
};

function nodeFill(node: FlowNode, classDefs: FlowchartModel["classDefs"]): string {
  for (const cls of node.classes) {
    const pal = NODE_PALETTE.find((p) => p.name === cls);
    if (pal) return pal.swatch;
    const def = classDefs.find((c) => c.name === cls);
    if (def) {
      const m = /fill:([^,]+)/.exec(def.styles);
      if (m) return m[1].trim();
    }
  }
  return "#1e293b";
}

function nodeStroke(selected: boolean): string {
  return selected ? "#34d399" : "#64748b";
}

function strokeForEdge(edge: FlowEdge, selected: boolean): {
  stroke: string;
  strokeWidth: number;
  dash?: string;
} {
  const stroke = selected ? "#34d399" : "#94a3b8";
  if (edge.line === "dotted") return { stroke, strokeWidth: 1.5, dash: "4 4" };
  if (edge.line === "thick") return { stroke, strokeWidth: 3.5 };
  return { stroke, strokeWidth: 1.75 };
}

function edgeOffsetMap(edges: FlowEdge[]): Map<string, number> {
  const counts = new Map<string, number>();
  const out = new Map<string, number>();
  for (const e of edges) {
    const key = [e.source, e.target].sort().join("|");
    const i = counts.get(key) ?? 0;
    counts.set(key, i + 1);
    out.set(e.id, i);
  }
  return out;
}

function RenderShape({
  node,
  selected,
  fill,
}: {
  node: FlowNode;
  selected: boolean;
  fill: string;
}) {
  const g = shapeGeometry(node);
  const stroke = nodeStroke(selected);
  const strokeWidth = selected ? 2.25 : 1.25;
  if (g.kind === "ellipse") {
    return (
      <>
        <ellipse cx={g.cx} cy={g.cy} rx={g.rx} ry={g.ry} fill={fill} stroke={stroke} strokeWidth={strokeWidth} />
        {node.shape === "doublecircle" && (
          <ellipse
            cx={g.cx}
            cy={g.cy}
            rx={Math.max(4, g.rx - 5)}
            ry={Math.max(4, g.ry - 5)}
            fill="none"
            stroke={stroke}
            strokeWidth={1}
          />
        )}
      </>
    );
  }
  if (g.kind === "polygon") {
    return <polygon points={g.points} fill={fill} stroke={stroke} strokeWidth={strokeWidth} />;
  }
  if (g.kind === "cylinder") {
    const { x, y, w, h, ry } = g;
    return (
      <g>
        <path
          d={`M ${x} ${y + ry} L ${x} ${y + h - ry} A ${w / 2} ${ry} 0 0 0 ${x + w} ${y + h - ry} L ${x + w} ${y + ry} A ${w / 2} ${ry} 0 0 0 ${x} ${y + ry}`}
          fill={fill}
          stroke={stroke}
          strokeWidth={strokeWidth}
        />
        <ellipse cx={x + w / 2} cy={y + ry} rx={w / 2} ry={ry} fill={fill} stroke={stroke} strokeWidth={strokeWidth} />
      </g>
    );
  }
  return (
    <rect x={g.x} y={g.y} width={g.w} height={g.h} rx={g.rx} fill={fill} stroke={stroke} strokeWidth={strokeWidth} />
  );
}

export function FlowchartCanvas({
  model,
  selection,
  onSelectionChange,
  onModelChange,
}: FlowchartCanvasProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [drag, setDrag] = useState<DragMode>(null);

  const bounds = useMemo(() => nodeBounds(model.nodes, 80), [model.nodes]);
  const width = Math.max(420, bounds.maxX - bounds.minX);
  const height = Math.max(280, bounds.maxY - bounds.minY);
  const offsets = useMemo(() => edgeOffsetMap(model.edges), [model.edges]);

  const clientToSvg = useCallback(
    (clientX: number, clientY: number): Point => {
      const svg = svgRef.current;
      if (!svg) return { x: 0, y: 0 };
      const pt = svg.createSVGPoint();
      pt.x = clientX;
      pt.y = clientY;
      const ctm = svg.getScreenCTM();
      if (!ctm) return { x: 0, y: 0 };
      const p = pt.matrixTransform(ctm.inverse());
      return { x: p.x, y: p.y };
    },
    [],
  );

  const updateNode = useCallback(
    (id: string, patch: Partial<FlowNode>) => {
      const next = cloneModel(model);
      const n = findNode(next, id);
      if (!n) return;
      Object.assign(n, patch);
      onModelChange(next);
    },
    [model, onModelChange],
  );

  const onPointerDownNode = (e: ReactPointerEvent, id: string) => {
    e.stopPropagation();
    e.preventDefault();
    (e.currentTarget as Element).setPointerCapture?.(e.pointerId);
    const p = clientToSvg(e.clientX, e.clientY);
    const n = findNode(model, id);
    if (!n) return;
    onSelectionChange({ kind: "node", id });
    setDrag({ type: "move", id, ox: p.x - n.x, oy: p.y - n.y, startX: n.x, startY: n.y });
  };

  const onPointerDownResize = (
    e: ReactPointerEvent,
    id: string,
    corner: "se" | "sw" | "ne" | "nw",
  ) => {
    e.stopPropagation();
    e.preventDefault();
    (e.currentTarget as Element).setPointerCapture?.(e.pointerId);
    const n = findNode(model, id);
    if (!n) return;
    const p = clientToSvg(e.clientX, e.clientY);
    setDrag({
      type: "resize",
      id,
      corner,
      startW: n.w,
      startH: n.h,
      startX: n.x,
      startY: n.y,
      ox: p.x,
      oy: p.y,
    });
  };

  const onPointerDownPort = (e: ReactPointerEvent, id: string) => {
    e.stopPropagation();
    e.preventDefault();
    (e.currentTarget as Element).setPointerCapture?.(e.pointerId);
    const p = clientToSvg(e.clientX, e.clientY);
    onSelectionChange({ kind: "node", id });
    setDrag({ type: "link", fromId: id, x: p.x, y: p.y });
  };

  const onPointerMove = (e: ReactPointerEvent) => {
    if (!drag) return;
    const p = clientToSvg(e.clientX, e.clientY);
    if (drag.type === "move") {
      updateNode(drag.id, { x: Math.round(p.x - drag.ox), y: Math.round(p.y - drag.oy) });
    } else if (drag.type === "resize") {
      const dx = p.x - drag.ox;
      const dy = p.y - drag.oy;
      let w = drag.startW;
      let h = drag.startH;
      let x = drag.startX;
      let y = drag.startY;
      if (drag.corner.includes("e")) w = drag.startW + dx;
      if (drag.corner.includes("w")) {
        w = drag.startW - dx;
        x = drag.startX + dx / 2;
      }
      if (drag.corner.includes("s")) h = drag.startH + dy;
      if (drag.corner.includes("n")) {
        h = drag.startH - dy;
        y = drag.startY + dy / 2;
      }
      w = Math.max(48, Math.round(w));
      h = Math.max(32, Math.round(h));
      // Keep center stable when resizing from one side
      if (drag.corner === "se") {
        x = drag.startX + (w - drag.startW) / 2;
        y = drag.startY + (h - drag.startH) / 2;
      } else if (drag.corner === "sw") {
        x = drag.startX - (w - drag.startW) / 2;
        y = drag.startY + (h - drag.startH) / 2;
      } else if (drag.corner === "ne") {
        x = drag.startX + (w - drag.startW) / 2;
        y = drag.startY - (h - drag.startH) / 2;
      } else {
        x = drag.startX - (w - drag.startW) / 2;
        y = drag.startY - (h - drag.startH) / 2;
      }
      updateNode(drag.id, { w, h, x: Math.round(x), y: Math.round(y) });
    } else if (drag.type === "link") {
      setDrag({ ...drag, x: p.x, y: p.y });
    }
  };

  const hitNodeAt = (p: Point): string | null => {
    for (let i = model.nodes.length - 1; i >= 0; i -= 1) {
      const n = model.nodes[i];
      if (p.x >= n.x - n.w / 2 && p.x <= n.x + n.w / 2 && p.y >= n.y - n.h / 2 && p.y <= n.y + n.h / 2) {
        return n.id;
      }
    }
    return null;
  };

  const onPointerUp = (e: ReactPointerEvent) => {
    if (!drag) return;
    if (drag.type === "link") {
      const p = clientToSvg(e.clientX, e.clientY);
      const targetId = hitNodeAt(p);
      if (targetId && targetId !== drag.fromId) {
        const next = cloneModel(model);
        const edge: FlowEdge = {
          id: nextEdgeId(next),
          source: drag.fromId,
          target: targetId,
          label: "",
          line: "solid",
          head: "arrow",
          bidirectional: false,
          length: 0,
        };
        next.edges.push(edge);
        onModelChange(next);
        onSelectionChange({ kind: "edge", id: edge.id });
      }
    }
    setDrag(null);
  };

  const onBgPointerDown = (e: ReactPointerEvent) => {
    if (e.target !== e.currentTarget && (e.target as Element).tagName !== "svg") return;
    onSelectionChange(null);
  };

  const selectedNodeId = selection?.kind === "node" ? selection.id : null;
  const selectedEdgeId = selection?.kind === "edge" ? selection.id : null;

  return (
    <div className="relative w-full overflow-auto rounded-md border border-border/50 bg-slate-950/80">
      <svg
        ref={svgRef}
        width="100%"
        height={Math.min(520, Math.max(300, height))}
        viewBox={`${bounds.minX} ${bounds.minY} ${width} ${height}`}
        className="block touch-none select-none"
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
        onPointerDown={onBgPointerDown}
        role="img"
        aria-label="Flowchart canvas"
      >
        <defs>
          <marker
            id="mm-arrow"
            markerWidth="8"
            markerHeight="8"
            refX="6"
            refY="3"
            orient="auto"
            markerUnits="strokeWidth"
          >
            <path d="M0,0 L6,3 L0,6 Z" fill="#94a3b8" />
          </marker>
          <marker
            id="mm-arrow-sel"
            markerWidth="8"
            markerHeight="8"
            refX="6"
            refY="3"
            orient="auto"
            markerUnits="strokeWidth"
          >
            <path d="M0,0 L6,3 L0,6 Z" fill="#34d399" />
          </marker>
        </defs>

        {model.edges.map((edge) => {
          const src = findNode(model, edge.source);
          const tgt = findNode(model, edge.target);
          if (!src || !tgt) return null;
          const geo = edgeGeometry(src, tgt, offsets.get(edge.id) ?? 0);
          const selected = edge.id === selectedEdgeId;
          const st = strokeForEdge(edge, selected);
          const marker =
            edge.head === "arrow" ? (selected ? "url(#mm-arrow-sel)" : "url(#mm-arrow)") : undefined;
          return (
            <g key={edge.id}>
              <path
                d={geo.path}
                fill="none"
                stroke="transparent"
                strokeWidth={14}
                className="cursor-pointer"
                onPointerDown={(e) => {
                  e.stopPropagation();
                  onSelectionChange({ kind: "edge", id: edge.id });
                }}
              />
              <path
                d={geo.path}
                fill="none"
                stroke={st.stroke}
                strokeWidth={st.strokeWidth}
                strokeDasharray={st.dash}
                markerEnd={marker}
                className="pointer-events-none"
              />
              {edge.label.trim() ? (
                <text
                  x={geo.label.x}
                  y={geo.label.y}
                  textAnchor="middle"
                  className="fill-slate-300 text-[11px] pointer-events-none"
                >
                  {edge.label}
                </text>
              ) : null}
            </g>
          );
        })}

        {drag?.type === "link" && (() => {
          const from = findNode(model, drag.fromId);
          if (!from) return null;
          return (
            <line
              x1={from.x}
              y1={from.y}
              x2={drag.x}
              y2={drag.y}
              stroke="#34d399"
              strokeWidth={1.5}
              strokeDasharray="4 3"
              className="pointer-events-none"
            />
          );
        })()}

        {model.nodes.map((node) => {
          const selected = node.id === selectedNodeId;
          const fill = nodeFill(node, model.classDefs);
          const lines = labelLines(node.label);
          const left = node.x - node.w / 2;
          const top = node.y - node.h / 2;
          return (
            <g
              key={node.id}
              className="cursor-grab active:cursor-grabbing"
              onPointerDown={(e) => onPointerDownNode(e, node.id)}
            >
              <RenderShape node={node} selected={selected} fill={fill} />
              <text
                x={node.x}
                y={node.y - ((lines.length - 1) * 7)}
                textAnchor="middle"
                dominantBaseline="middle"
                className="fill-slate-100 text-[12px] pointer-events-none"
              >
                {lines.map((ln, i) => (
                  <tspan key={i} x={node.x} dy={i === 0 ? 0 : 14}>
                    {ln || " "}
                  </tspan>
                ))}
              </text>
              {selected && (
                <>
                  {(
                    [
                      ["nw", left, top],
                      ["ne", left + node.w, top],
                      ["sw", left, top + node.h],
                      ["se", left + node.w, top + node.h],
                    ] as const
                  ).map(([corner, hx, hy]) => (
                    <rect
                      key={corner}
                      x={hx - 4}
                      y={hy - 4}
                      width={8}
                      height={8}
                      fill="#34d399"
                      stroke="#0f172a"
                      strokeWidth={1}
                      className="cursor-nwse-resize"
                      onPointerDown={(e) => onPointerDownResize(e, node.id, corner)}
                    />
                  ))}
                  <circle
                    cx={left + node.w + 10}
                    cy={node.y}
                    r={6}
                    fill="#0ea5e9"
                    stroke="#e0f2fe"
                    strokeWidth={1.5}
                    className="cursor-crosshair"
                    onPointerDown={(e) => onPointerDownPort(e, node.id)}
                  >
                    <title>Drag to connect</title>
                  </circle>
                </>
              )}
            </g>
          );
        })}
      </svg>
      <p className="px-2 py-1 text-[10px] text-muted-foreground border-t border-border/40">
        Drag nodes · corner handles resize · blue port draws connectors · click edge to select
      </p>
    </div>
  );
}
