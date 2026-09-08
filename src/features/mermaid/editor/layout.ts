import { renderMermaidInto } from "../render";
import { serializeFlowchart } from "./serialize";
import { measureNode, type FlowchartModel } from "./model";

export type NodeBox = { x: number; y: number; w: number; h: number };

const NODE_ID_RE = /^flowchart-(.+?)-\d+$/;

function nodeIdOf(el: Element): string | null {
  const dataId = el.getAttribute("data-id");
  if (dataId) return dataId;
  const raw = el.getAttribute("id") || "";
  const m = NODE_ID_RE.exec(raw);
  if (m) return m[1];
  return raw || null;
}

/**
 * Run Mermaid's own dagre layout offscreen and read back node centers.
 * Gives the editor a starting arrangement identical to the rendered diagram.
 */
export async function layoutFromMermaid(source: string): Promise<Record<string, NodeBox> | null> {
  if (typeof document === "undefined") return null;
  const host = document.createElement("div");
  host.style.cssText =
    "position:fixed;left:-100000px;top:0;width:1400px;opacity:0;pointer-events:none;z-index:-1;";
  document.body.appendChild(host);
  try {
    await renderMermaidInto(host, source);
    const svg = host.querySelector("svg");
    if (!svg) return null;

    const viewBox = (svg.getAttribute("viewBox") || "").split(/[\s,]+/).map(Number);
    const svgRect = svg.getBoundingClientRect();
    if (!svgRect.width || !svgRect.height) return null;
    const scaleX = viewBox.length === 4 && viewBox[2] ? viewBox[2] / svgRect.width : 1;
    const scaleY = viewBox.length === 4 && viewBox[3] ? viewBox[3] / svgRect.height : 1;

    const boxes: Record<string, NodeBox> = {};
    svg.querySelectorAll("g.node").forEach((el) => {
      const id = nodeIdOf(el);
      if (!id) return;
      const r = el.getBoundingClientRect();
      if (!r.width || !r.height) return;
      boxes[id] = {
        x: Math.round((r.left - svgRect.left + r.width / 2) * scaleX),
        y: Math.round((r.top - svgRect.top + r.height / 2) * scaleY),
        w: Math.round(r.width * scaleX),
        h: Math.round(r.height * scaleY),
      };
    });
    return Object.keys(boxes).length ? boxes : null;
  } catch {
    return null;
  } finally {
    host.remove();
  }
}

const RANK_GAP = 130;
const SIBLING_GAP = 40;

/** Deterministic layered fallback when Mermaid layout is unavailable. */
export function layeredLayout(model: FlowchartModel): Record<string, NodeBox> {
  const ids = model.nodes.map((n) => n.id);
  const incoming = new Map<string, string[]>();
  const outgoing = new Map<string, string[]>();
  for (const id of ids) {
    incoming.set(id, []);
    outgoing.set(id, []);
  }
  for (const e of model.edges) {
    if (!incoming.has(e.target) || !outgoing.has(e.source)) continue;
    incoming.get(e.target)?.push(e.source);
    outgoing.get(e.source)?.push(e.target);
  }

  const rank = new Map<string, number>();
  const visiting = new Set<string>();
  const rankOf = (id: string): number => {
    const cached = rank.get(id);
    if (cached != null) return cached;
    if (visiting.has(id)) return 0;
    visiting.add(id);
    const parents = incoming.get(id) ?? [];
    const value = parents.length ? Math.max(...parents.map((p) => rankOf(p) + 1)) : 0;
    visiting.delete(id);
    rank.set(id, value);
    return value;
  };
  for (const id of ids) rankOf(id);

  const layers = new Map<number, string[]>();
  for (const id of ids) {
    const r = rank.get(id) ?? 0;
    const bucket = layers.get(r) ?? [];
    bucket.push(id);
    layers.set(r, bucket);
  }

  const horizontal = model.direction === "LR" || model.direction === "RL";
  const boxes: Record<string, NodeBox> = {};
  const sortedRanks = [...layers.keys()].sort((a, b) => a - b);

  let along = 120;
  for (const r of sortedRanks) {
    const bucket = layers.get(r) ?? [];
    const sizes = bucket.map((id) => {
      const node = model.nodes.find((n) => n.id === id);
      if (node && node.w && node.h) return { w: node.w, h: node.h };
      return measureNode(node?.label ?? id, node?.shape ?? "rect");
    });
    const cross = sizes.reduce(
      (sum, s, i) => sum + (horizontal ? s.h : s.w) + (i ? SIBLING_GAP : 0),
      0,
    );
    let cursor = -cross / 2;
    bucket.forEach((id, i) => {
      const size = sizes[i];
      const half = (horizontal ? size.h : size.w) / 2;
      cursor += half;
      boxes[id] = horizontal
        ? { x: along, y: 320 + cursor, w: size.w, h: size.h }
        : { x: 460 + cursor, y: along, w: size.w, h: size.h };
      cursor += half + SIBLING_GAP;
    });
    const depth = Math.max(...sizes.map((s) => (horizontal ? s.w : s.h)), 60);
    along += depth + RANK_GAP;
  }

  return boxes;
}

/** Normalize so the top-left of the content sits at a small fixed margin. */
export function normalizePositions(model: FlowchartModel, margin = 60): void {
  if (!model.nodes.length) return;
  const minX = Math.min(...model.nodes.map((n) => n.x - n.w / 2));
  const minY = Math.min(...model.nodes.map((n) => n.y - n.h / 2));
  const dx = margin - minX;
  const dy = margin - minY;
  if (Math.abs(dx) < 0.5 && Math.abs(dy) < 0.5) return;
  for (const node of model.nodes) {
    node.x += dx;
    node.y += dy;
  }
}

/** Fill in positions: saved layout wins, then Mermaid's dagre, then the fallback. */
export async function applyAutoLayout(
  model: FlowchartModel,
  opts?: { force?: boolean },
): Promise<FlowchartModel> {
  const force = opts?.force ?? false;
  const missing = model.nodes.filter((n) => force || (!n.x && !n.y));
  if (!missing.length) return model;

  const boxes =
    (await layoutFromMermaid(serializeFlowchart(model, { layout: false }))) ?? layeredLayout(model);

  for (const node of model.nodes) {
    if (!force && (node.x || node.y)) continue;
    const box = boxes[node.id];
    if (!box) continue;
    node.x = box.x;
    node.y = box.y;
    if (box.w > 8 && box.h > 8) {
      node.w = box.w;
      node.h = box.h;
    }
  }

  const stillMissing = model.nodes.filter((n) => !n.x && !n.y);
  if (stillMissing.length) {
    const fallback = layeredLayout(model);
    for (const node of stillMissing) {
      const box = fallback[node.id];
      if (!box) continue;
      node.x = box.x;
      node.y = box.y;
    }
  }

  normalizePositions(model);
  return model;
}
