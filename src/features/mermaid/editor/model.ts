/**
 * Editable model for Mermaid flowchart/graph diagrams.
 * Positions live only in the model + a `%% layout:` comment, so the source stays
 * valid Mermaid for any other renderer.
 */

export type FlowDirection = "TD" | "TB" | "BT" | "LR" | "RL";

export type NodeShape =
  | "rect"
  | "round"
  | "stadium"
  | "subroutine"
  | "cylinder"
  | "circle"
  | "doublecircle"
  | "diamond"
  | "hexagon"
  | "parallelogram"
  | "parallelogramAlt"
  | "trapezoid"
  | "trapezoidAlt"
  | "asymmetric";

export type EdgeLine = "solid" | "dotted" | "thick";
export type EdgeHead = "arrow" | "none" | "circle" | "cross";

export type FlowNode = {
  id: string;
  label: string;
  shape: NodeShape;
  classes: string[];
  x: number;
  y: number;
  w: number;
  h: number;
};

export type FlowEdge = {
  id: string;
  source: string;
  target: string;
  label: string;
  line: EdgeLine;
  head: EdgeHead;
  bidirectional: boolean;
  /** Extra dashes/equals beyond the minimum — Mermaid uses this as a rank hint. */
  length: number;
};

export type FlowSubgraph = {
  id: string;
  title: string;
  direction: FlowDirection | null;
  nodeIds: string[];
};

export type ClassDef = { name: string; styles: string };
export type NodeStyle = { nodeId: string; styles: string };

export type FlowchartModel = {
  keyword: "flowchart" | "graph";
  direction: FlowDirection;
  nodes: FlowNode[];
  edges: FlowEdge[];
  subgraphs: FlowSubgraph[];
  classDefs: ClassDef[];
  nodeStyles: NodeStyle[];
  /** Verbatim `linkStyle …` / `click …` / `%%{init}` lines, replayed on serialize. */
  extras: string[];
};

export const FLOW_DIRECTIONS: readonly FlowDirection[] = ["TD", "TB", "BT", "LR", "RL"];

export const SHAPE_DELIMITERS: Record<NodeShape, [string, string]> = {
  rect: ["[", "]"],
  round: ["(", ")"],
  stadium: ["([", "])"],
  subroutine: ["[[", "]]"],
  cylinder: ["[(", ")]"],
  circle: ["((", "))"],
  doublecircle: ["(((", ")))"],
  diamond: ["{", "}"],
  hexagon: ["{{", "}}"],
  parallelogram: ["[/", "/]"],
  parallelogramAlt: ["[\\", "\\]"],
  trapezoid: ["[/", "\\]"],
  trapezoidAlt: ["[\\", "/]"],
  asymmetric: [">", "]"],
};

export const SHAPE_OPTIONS: readonly { value: NodeShape; label: string }[] = [
  { value: "rect", label: "Rectangle" },
  { value: "round", label: "Rounded" },
  { value: "stadium", label: "Stadium" },
  { value: "circle", label: "Circle" },
  { value: "diamond", label: "Decision" },
  { value: "hexagon", label: "Hexagon" },
  { value: "subroutine", label: "Subroutine" },
  { value: "cylinder", label: "Database" },
  { value: "parallelogram", label: "Input/Output" },
  { value: "trapezoid", label: "Trapezoid" },
  { value: "asymmetric", label: "Flag" },
];

export const EDGE_LINE_OPTIONS: readonly { value: EdgeLine; label: string }[] = [
  { value: "solid", label: "Solid" },
  { value: "dotted", label: "Dotted" },
  { value: "thick", label: "Thick" },
];

export const EDGE_HEAD_OPTIONS: readonly { value: EdgeHead; label: string }[] = [
  { value: "arrow", label: "Arrow" },
  { value: "none", label: "Open" },
  { value: "circle", label: "Circle" },
  { value: "cross", label: "Cross" },
];

/** Named palette entries become `classDef` rules so colors survive as plain Mermaid. */
export const NODE_PALETTE: readonly { name: string; label: string; swatch: string; styles: string }[] =
  [
    {
      name: "mmgEmerald",
      label: "Emerald",
      swatch: "#1c3f35",
      styles: "fill:#1c3f35,stroke:#3d7a64,color:#e7f5ef",
    },
    {
      name: "mmgSky",
      label: "Sky",
      swatch: "#16324a",
      styles: "fill:#16324a,stroke:#4a8fc0,color:#e6f2fb",
    },
    {
      name: "mmgAmber",
      label: "Amber",
      swatch: "#453116",
      styles: "fill:#453116,stroke:#c39a4a,color:#fdf3e0",
    },
    {
      name: "mmgRose",
      label: "Rose",
      swatch: "#45191f",
      styles: "fill:#45191f,stroke:#c06070,color:#fde9ec",
    },
    {
      name: "mmgViolet",
      label: "Violet",
      swatch: "#301a45",
      styles: "fill:#301a45,stroke:#8a63c0,color:#f1e8fd",
    },
    {
      name: "mmgSlate",
      label: "Slate",
      swatch: "#232a31",
      styles: "fill:#232a31,stroke:#6b7a88,color:#e8edf2",
    },
  ];

export const DEFAULT_NODE_WIDTH = 132;
export const DEFAULT_NODE_HEIGHT = 46;

export function emptyModel(direction: FlowDirection = "TD"): FlowchartModel {
  return {
    keyword: "flowchart",
    direction,
    nodes: [],
    edges: [],
    subgraphs: [],
    classDefs: [],
    nodeStyles: [],
    extras: [],
  };
}

export function cloneModel(model: FlowchartModel): FlowchartModel {
  return {
    keyword: model.keyword,
    direction: model.direction,
    nodes: model.nodes.map((n) => ({ ...n, classes: [...n.classes] })),
    edges: model.edges.map((e) => ({ ...e })),
    subgraphs: model.subgraphs.map((s) => ({ ...s, nodeIds: [...s.nodeIds] })),
    classDefs: model.classDefs.map((c) => ({ ...c })),
    nodeStyles: model.nodeStyles.map((s) => ({ ...s })),
    extras: [...model.extras],
  };
}

export function findNode(model: FlowchartModel, id: string): FlowNode | undefined {
  return model.nodes.find((n) => n.id === id);
}

export function findEdge(model: FlowchartModel, id: string): FlowEdge | undefined {
  return model.edges.find((e) => e.id === id);
}

const ID_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ";

export function nextNodeId(model: FlowchartModel): string {
  const taken = new Set(model.nodes.map((n) => n.id));
  for (const ch of ID_ALPHABET) {
    if (!taken.has(ch)) return ch;
  }
  let i = 1;
  while (taken.has(`N${i}`)) i += 1;
  return `N${i}`;
}

export function nextSubgraphId(model: FlowchartModel): string {
  const taken = new Set(model.subgraphs.map((s) => s.id));
  let i = 1;
  while (taken.has(`group${i}`)) i += 1;
  return `group${i}`;
}

export function nextEdgeId(model: FlowchartModel): string {
  const taken = new Set(model.edges.map((e) => e.id));
  let i = 1;
  while (taken.has(`e${i}`)) i += 1;
  return `e${i}`;
}

/** Rough label metrics — keeps hand-placed nodes close to Mermaid's own sizing. */
export function measureNode(label: string, shape: NodeShape): { w: number; h: number } {
  const lines = labelLines(label);
  const longest = lines.reduce((max, ln) => Math.max(max, ln.length), 0);
  let w = Math.max(72, Math.min(340, longest * 7.4 + 34));
  let h = Math.max(DEFAULT_NODE_HEIGHT, lines.length * 18 + 22);
  if (shape === "diamond") {
    w = Math.max(w * 1.35, 110);
    h = Math.max(h * 1.5, 70);
  } else if (shape === "circle" || shape === "doublecircle") {
    const d = Math.max(w * 0.9, h, 62);
    w = d;
    h = d;
  } else if (shape === "hexagon") {
    w += 26;
  }
  return { w: Math.round(w), h: Math.round(h) };
}

export function labelLines(label: string): string[] {
  return label
    .replace(/<br\s*\/?>/gi, "\n")
    .split("\n")
    .map((s) => s.trim());
}
