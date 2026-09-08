import type { FlowNode, NodeShape } from "./model";

export type Point = { x: number; y: number };

export type ShapeGeometry =
  | { kind: "rect"; x: number; y: number; w: number; h: number; rx: number }
  | { kind: "ellipse"; cx: number; cy: number; rx: number; ry: number }
  | { kind: "polygon"; points: string }
  | { kind: "cylinder"; x: number; y: number; w: number; h: number; ry: number };

const ELLIPTIC: ReadonlySet<NodeShape> = new Set(["circle", "doublecircle", "round"]);

export function shapeGeometry(node: FlowNode): ShapeGeometry {
  const { x, y, w, h, shape } = node;
  const left = x - w / 2;
  const top = y - h / 2;

  switch (shape) {
    case "circle":
    case "doublecircle":
      return { kind: "ellipse", cx: x, cy: y, rx: w / 2, ry: h / 2 };
    case "round":
      return { kind: "rect", x: left, y: top, w, h, rx: Math.min(18, h / 2) };
    case "stadium":
      return { kind: "rect", x: left, y: top, w, h, rx: h / 2 };
    case "subroutine":
      return { kind: "rect", x: left, y: top, w, h, rx: 0 };
    case "cylinder":
      return { kind: "cylinder", x: left, y: top, w, h, ry: Math.min(12, h / 5) };
    case "diamond":
      return {
        kind: "polygon",
        points: `${x},${top} ${x + w / 2},${y} ${x},${top + h} ${left},${y}`,
      };
    case "hexagon": {
      const inset = Math.min(22, w / 5);
      return {
        kind: "polygon",
        points: `${left + inset},${top} ${left + w - inset},${top} ${left + w},${y} ${left + w - inset},${top + h} ${left + inset},${top + h} ${left},${y}`,
      };
    }
    case "parallelogram": {
      const skew = Math.min(22, w / 6);
      return {
        kind: "polygon",
        points: `${left + skew},${top} ${left + w},${top} ${left + w - skew},${top + h} ${left},${top + h}`,
      };
    }
    case "parallelogramAlt": {
      const skew = Math.min(22, w / 6);
      return {
        kind: "polygon",
        points: `${left},${top} ${left + w - skew},${top} ${left + w},${top + h} ${left + skew},${top + h}`,
      };
    }
    case "trapezoid": {
      const skew = Math.min(26, w / 5);
      return {
        kind: "polygon",
        points: `${left + skew},${top} ${left + w - skew},${top} ${left + w},${top + h} ${left},${top + h}`,
      };
    }
    case "trapezoidAlt": {
      const skew = Math.min(26, w / 5);
      return {
        kind: "polygon",
        points: `${left},${top} ${left + w},${top} ${left + w - skew},${top + h} ${left + skew},${top + h}`,
      };
    }
    case "asymmetric": {
      const notch = Math.min(20, w / 6);
      return {
        kind: "polygon",
        points: `${left},${top} ${left + w},${top} ${left + w},${top + h} ${left},${top + h} ${left + notch},${y}`,
      };
    }
    default:
      return { kind: "rect", x: left, y: top, w, h, rx: 4 };
  }
}

/** Where a ray from the node center toward `to` leaves the node outline. */
export function boundaryPoint(node: FlowNode, to: Point, pad = 2): Point {
  const dx = to.x - node.x;
  const dy = to.y - node.y;
  if (dx === 0 && dy === 0) return { x: node.x, y: node.y };

  const rx = node.w / 2 + pad;
  const ry = node.h / 2 + pad;

  if (ELLIPTIC.has(node.shape)) {
    const denom = Math.sqrt((dx * dx) / (rx * rx) + (dy * dy) / (ry * ry));
    if (!denom) return { x: node.x, y: node.y };
    return { x: node.x + dx / denom, y: node.y + dy / denom };
  }

  if (node.shape === "diamond") {
    const t = 1 / (Math.abs(dx) / rx + Math.abs(dy) / ry);
    return { x: node.x + dx * t, y: node.y + dy * t };
  }

  const scale = Math.min(rx / Math.abs(dx || 1e-6), ry / Math.abs(dy || 1e-6));
  return { x: node.x + dx * scale, y: node.y + dy * scale };
}

export type EdgeGeometry = { path: string; label: Point; start: Point; end: Point };

const SELF_LOOP_R = 34;

/** Curved connector clipped to both node outlines, with a parallel-edge offset. */
export function edgeGeometry(
  source: FlowNode,
  target: FlowNode,
  offsetIndex = 0,
): EdgeGeometry {
  if (source.id === target.id) {
    const cx = source.x + source.w / 2;
    const cy = source.y - source.h / 2;
    const r = SELF_LOOP_R + offsetIndex * 12;
    const start = { x: source.x + source.w / 2 - 6, y: source.y - source.h / 2 + 4 };
    const end = { x: source.x + 6, y: source.y - source.h / 2 - 1 };
    return {
      path: `M ${start.x} ${start.y} C ${cx + r} ${cy - r * 0.4}, ${cx - r * 0.1} ${cy - r * 1.5}, ${end.x} ${end.y}`,
      label: { x: cx + r * 0.4, y: cy - r },
      start,
      end,
    };
  }

  const dx = target.x - source.x;
  const dy = target.y - source.y;
  const len = Math.hypot(dx, dy) || 1;
  const nx = -dy / len;
  const ny = dx / len;
  const bow = offsetIndex === 0 ? 0 : (offsetIndex % 2 === 1 ? 1 : -1) * Math.ceil(offsetIndex / 2) * 26;

  const midX = (source.x + target.x) / 2 + nx * bow;
  const midY = (source.y + target.y) / 2 + ny * bow;

  const start = boundaryPoint(source, { x: midX, y: midY });
  const end = boundaryPoint(target, { x: midX, y: midY });

  const path = `M ${round(start.x)} ${round(start.y)} Q ${round(midX)} ${round(midY)} ${round(end.x)} ${round(end.y)}`;
  return {
    path,
    label: { x: (start.x + 2 * midX + end.x) / 4, y: (start.y + 2 * midY + end.y) / 4 },
    start,
    end,
  };
}

function round(n: number): number {
  return Math.round(n * 10) / 10;
}

export type Bounds = { minX: number; minY: number; maxX: number; maxY: number };

export function nodeBounds(nodes: FlowNode[], pad = 0): Bounds {
  if (!nodes.length) return { minX: 0, minY: 0, maxX: 320, maxY: 200 };
  return {
    minX: Math.min(...nodes.map((n) => n.x - n.w / 2)) - pad,
    minY: Math.min(...nodes.map((n) => n.y - n.h / 2)) - pad,
    maxX: Math.max(...nodes.map((n) => n.x + n.w / 2)) + pad,
    maxY: Math.max(...nodes.map((n) => n.y + n.h / 2)) + pad,
  };
}

export function pointInBounds(p: Point, b: Bounds): boolean {
  return p.x >= b.minX && p.x <= b.maxX && p.y >= b.minY && p.y <= b.maxY;
}

export function rectsIntersect(a: Bounds, b: Bounds): boolean {
  return !(a.maxX < b.minX || a.minX > b.maxX || a.maxY < b.minY || a.minY > b.maxY);
}

export function distanceToSegment(p: Point, a: Point, b: Point): number {
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const lenSq = dx * dx + dy * dy;
  if (!lenSq) return Math.hypot(p.x - a.x, p.y - a.y);
  let t = ((p.x - a.x) * dx + (p.y - a.y) * dy) / lenSq;
  t = Math.max(0, Math.min(1, t));
  return Math.hypot(p.x - (a.x + t * dx), p.y - (a.y + t * dy));
}
