import {
  SHAPE_DELIMITERS,
  type EdgeHead,
  type FlowEdge,
  type FlowNode,
  type FlowchartModel,
} from "./model";

const INDENT = "    ";

const SAFE_LABEL_RE = /^[A-Za-z0-9 _.\-]+$/;

function needsQuotes(label: string): boolean {
  return !SAFE_LABEL_RE.test(label) || label !== label.trim();
}

export function formatLabel(label: string): string {
  const text = label.replace(/"/g, "#quot;");
  return needsQuotes(text) ? `"${text}"` : text;
}

export function formatNodeToken(node: FlowNode): string {
  const [open, close] = SHAPE_DELIMITERS[node.shape];
  if (node.label === node.id && node.shape === "rect") return node.id;
  return `${node.id}${open}${formatLabel(node.label)}${close}`;
}

function headChar(head: EdgeHead): string {
  if (head === "arrow") return ">";
  if (head === "circle") return "o";
  if (head === "cross") return "x";
  return "";
}

export function formatLink(edge: FlowEdge): string {
  const extra = Math.max(0, Math.min(6, Math.round(edge.length)));
  const head = headChar(edge.head);
  let stem: string;
  if (edge.line === "dotted") {
    stem = `-${".".repeat(1 + extra)}-`;
  } else if (edge.line === "thick") {
    stem = "=".repeat((head ? 2 : 3) + extra);
  } else {
    stem = "-".repeat((head ? 2 : 3) + extra);
  }
  const arrow = `${edge.bidirectional ? "<" : ""}${stem}${head}`;
  const label = edge.label.trim();
  return label ? `${arrow}|${formatLabel(label)}|` : arrow;
}

function layoutComment(nodes: FlowNode[]): string {
  const parts = nodes.map(
    (n) => `${n.id}=${Math.round(n.x)},${Math.round(n.y)},${Math.round(n.w)}x${Math.round(n.h)}`,
  );
  return `%% layout: ${parts.join("; ")}`;
}

/** Model → Mermaid source. Positions ride along in a `%% layout:` comment. */
export function serializeFlowchart(model: FlowchartModel, opts?: { layout?: boolean }): string {
  const includeLayout = opts?.layout ?? true;
  const lines: string[] = [];

  for (const extra of model.extras) {
    if (extra.startsWith("%%{")) lines.push(extra);
  }

  lines.push(`${model.keyword} ${model.direction}`);

  const grouped = new Set<string>();
  for (const sg of model.subgraphs) {
    for (const id of sg.nodeIds) grouped.add(id);
  }

  const emittedNodes = new Set<string>();
  const emitNode = (node: FlowNode, indent: string) => {
    if (emittedNodes.has(node.id)) return;
    emittedNodes.add(node.id);
    lines.push(`${indent}${formatNodeToken(node)}`);
  };

  for (const sg of model.subgraphs) {
    const title = sg.title && sg.title !== sg.id ? `${sg.id}[${formatLabel(sg.title)}]` : sg.id;
    lines.push(`${INDENT}subgraph ${title}`);
    if (sg.direction) lines.push(`${INDENT}${INDENT}direction ${sg.direction}`);
    for (const id of sg.nodeIds) {
      const node = model.nodes.find((n) => n.id === id);
      if (node) emitNode(node, `${INDENT}${INDENT}`);
    }
    lines.push(`${INDENT}end`);
  }

  for (const node of model.nodes) {
    if (grouped.has(node.id)) continue;
    const isolated = !model.edges.some((e) => e.source === node.id || e.target === node.id);
    if (isolated) emitNode(node, INDENT);
  }

  for (const edge of model.edges) {
    const source = model.nodes.find((n) => n.id === edge.source);
    const target = model.nodes.find((n) => n.id === edge.target);
    if (!source || !target) continue;
    const left = emittedNodes.has(source.id) ? source.id : formatNodeToken(source);
    emittedNodes.add(source.id);
    const right = emittedNodes.has(target.id) ? target.id : formatNodeToken(target);
    emittedNodes.add(target.id);
    lines.push(`${INDENT}${left} ${formatLink(edge)} ${right}`);
  }

  for (const node of model.nodes) {
    if (!emittedNodes.has(node.id)) emitNode(node, INDENT);
  }

  const usedClasses = new Set<string>();
  for (const node of model.nodes) {
    for (const cls of node.classes) usedClasses.add(cls);
  }
  for (const def of model.classDefs) {
    if (!usedClasses.has(def.name)) continue;
    lines.push(`${INDENT}classDef ${def.name} ${def.styles}`);
  }
  for (const cls of usedClasses) {
    const members = model.nodes.filter((n) => n.classes.includes(cls)).map((n) => n.id);
    if (members.length) lines.push(`${INDENT}class ${members.join(",")} ${cls}`);
  }
  for (const style of model.nodeStyles) {
    if (!model.nodes.some((n) => n.id === style.nodeId)) continue;
    lines.push(`${INDENT}style ${style.nodeId} ${style.styles}`);
  }
  for (const extra of model.extras) {
    if (extra.startsWith("%%{")) continue;
    lines.push(extra.startsWith("%%") ? extra : `${INDENT}${extra}`);
  }

  if (includeLayout && model.nodes.length) lines.push(layoutComment(model.nodes));

  return lines.join("\n");
}

/** Build a standalone diagram from a subset of nodes (used by Split / Extract). */
export function subsetModel(model: FlowchartModel, nodeIds: string[]): FlowchartModel {
  const keep = new Set(nodeIds);
  const nodes = model.nodes.filter((n) => keep.has(n.id));
  const edges = model.edges.filter((e) => keep.has(e.source) && keep.has(e.target));
  const subgraphs = model.subgraphs
    .map((sg) => ({ ...sg, nodeIds: sg.nodeIds.filter((id) => keep.has(id)) }))
    .filter((sg) => sg.nodeIds.length > 0);
  const classNames = new Set(nodes.flatMap((n) => n.classes));
  return {
    keyword: model.keyword,
    direction: model.direction,
    nodes: nodes.map((n) => ({ ...n, classes: [...n.classes] })),
    edges: edges.map((e) => ({ ...e })),
    subgraphs,
    classDefs: model.classDefs.filter((c) => classNames.has(c.name)),
    nodeStyles: model.nodeStyles.filter((s) => keep.has(s.nodeId)),
    extras: model.extras.filter((x) => x.startsWith("%%{")),
  };
}
