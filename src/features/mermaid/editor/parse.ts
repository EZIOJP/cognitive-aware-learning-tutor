import {
  DEFAULT_NODE_HEIGHT,
  DEFAULT_NODE_WIDTH,
  FLOW_DIRECTIONS,
  SHAPE_DELIMITERS,
  measureNode,
  type ClassDef,
  type EdgeHead,
  type EdgeLine,
  type FlowDirection,
  type FlowEdge,
  type FlowNode,
  type FlowSubgraph,
  type FlowchartModel,
  type NodeShape,
  type NodeStyle,
} from "./model";

export type ParseResult =
  | { ok: true; model: FlowchartModel; warnings: string[] }
  | { ok: false; reason: string };

const HEADER_RE = /^(flowchart|graph)\b[ \t]*([A-Za-z]{2})?[ \t]*;?$/i;
const LAYOUT_COMMENT_RE = /^%%\s*layout:\s*(.*)$/i;
const CLASSDEF_RE = /^classDef\s+([A-Za-z0-9_,-]+)\s+(.+?);?$/i;
const CLASS_RE = /^class\s+([A-Za-z0-9_,.-]+)\s+([A-Za-z0-9_-]+)\s*;?$/i;
const STYLE_RE = /^style\s+([A-Za-z0-9_.-]+)\s+(.+?);?$/i;
const SUBGRAPH_RE = /^subgraph\s+(.*)$/i;
const DIRECTION_RE = /^direction\s+([A-Za-z]{2})\s*;?$/i;

/** Longest delimiters first, then most specific — `[[` must win over `[`. */
const SHAPE_MATCH_ORDER: readonly NodeShape[] = [
  "doublecircle",
  "circle",
  "stadium",
  "subroutine",
  "cylinder",
  "hexagon",
  "trapezoid",
  "trapezoidAlt",
  "parallelogram",
  "parallelogramAlt",
  "rect",
  "round",
  "diamond",
  "asymmetric",
];

const SHAPE_PAIRS: [NodeShape, string, string][] = SHAPE_MATCH_ORDER.map((shape) => [
  shape,
  SHAPE_DELIMITERS[shape][0],
  SHAPE_DELIMITERS[shape][1],
]);

function normalizeDirection(raw: string | undefined, fallback: FlowDirection): FlowDirection {
  const up = (raw || "").toUpperCase() as FlowDirection;
  return FLOW_DIRECTIONS.includes(up) ? up : fallback;
}

function stripTrailingComment(line: string): string {
  let depth = 0;
  let quote = false;
  for (let i = 0; i < line.length; i += 1) {
    const ch = line[i];
    if (ch === '"') quote = !quote;
    if (quote) continue;
    if ("[({".includes(ch)) depth += 1;
    else if ("])}".includes(ch)) depth = Math.max(0, depth - 1);
    else if (ch === "%" && line[i + 1] === "%" && depth === 0) return line.slice(0, i);
  }
  return line;
}

/** Blank out bracketed / quoted spans so top-level scans cannot see label text. */
function maskNested(statement: string): string {
  const out = statement.split("");
  let depth = 0;
  let quote = false;
  for (let i = 0; i < statement.length; i += 1) {
    const ch = statement[i];
    if (ch === '"') {
      quote = !quote;
      out[i] = "\u0001";
      continue;
    }
    if (quote) {
      out[i] = "\u0001";
      continue;
    }
    if ("[({".includes(ch)) {
      depth += 1;
      out[i] = "\u0001";
      continue;
    }
    if ("])}".includes(ch)) {
      depth = Math.max(0, depth - 1);
      out[i] = "\u0001";
      continue;
    }
    if (depth > 0) out[i] = "\u0001";
  }
  return out.join("");
}

const INLINE_LABEL_RE =
  /(?<![-=.])(-{2}|={2}|-\.)[ \t]+([^-=<>|\u0001]+?)[ \t]+(-{2,}[>ox]?|={2,}[>ox]?|\.-{1,}[>ox]?)/g;

/** `A -- text --> B` → `A -->|text| B` so one link grammar covers both spellings. */
function normalizeInlineLinkLabels(statement: string): string {
  const masked = maskNested(statement);
  const edits: { start: number; end: number; text: string }[] = [];
  INLINE_LABEL_RE.lastIndex = 0;
  let m: RegExpExecArray | null;
  while ((m = INLINE_LABEL_RE.exec(masked)) !== null) {
    const open = m[1];
    const close = m[3];
    const text = statement.slice(m.index + open.length, m.index + m[0].length - close.length).trim();
    const head: EdgeHead = close.endsWith(">")
      ? "arrow"
      : close.endsWith("o")
        ? "circle"
        : close.endsWith("x")
          ? "cross"
          : "none";
    const stem = open === "-." ? "-.-" : open === "==" ? (head === "none" ? "===" : "==") : head === "none" ? "---" : "--";
    edits.push({
      start: m.index,
      end: m.index + m[0].length,
      text: `${stem}${headChar(head)}|${text}|`,
    });
  }
  if (!edits.length) return statement;
  let out = "";
  let cursor = 0;
  for (const edit of edits) {
    out += statement.slice(cursor, edit.start) + edit.text;
    cursor = edit.end;
  }
  return out + statement.slice(cursor);
}

function headChar(head: EdgeHead): string {
  if (head === "arrow") return ">";
  if (head === "circle") return "o";
  if (head === "cross") return "x";
  return "";
}

const LINK_AT_RE = /^(<?)(-\.{1,}-[>ox]?|={2,}[>ox]?|-{2,}[>ox]?)(?:\|([^|]*)\|)?/;

type LinkToken = { line: EdgeLine; head: EdgeHead; bidirectional: boolean; label: string; length: number };

function readLink(text: string, at: number): { token: LinkToken; length: number } | null {
  const m = LINK_AT_RE.exec(text.slice(at));
  if (!m) return null;
  const bidirectional = m[1] === "<";
  const body = m[2];
  const label = (m[3] ?? "").trim();

  let line: EdgeLine;
  let head: EdgeHead = "none";
  let length = 0;

  const last = body[body.length - 1];
  if (last === ">") head = "arrow";
  else if (last === "o") head = "circle";
  else if (last === "x") head = "cross";

  const stem = head === "none" ? body : body.slice(0, -1);

  if (stem.startsWith("-.")) {
    line = "dotted";
    length = Math.max(0, (stem.match(/\./g)?.length ?? 1) - 1);
  } else if (stem.startsWith("=")) {
    line = "thick";
    length = Math.max(0, stem.length - (head === "none" ? 3 : 2));
  } else {
    line = "solid";
    length = Math.max(0, stem.length - (head === "none" ? 3 : 2));
  }

  return { token: { line, head, bidirectional, label, length }, length: m[0].length };
}

type Segment = { text: string; link: LinkToken | null };

/** Split `A[x] --> B & C -.-> D` into node chunks separated by link tokens. */
function splitChain(statement: string): Segment[] | null {
  const segments: Segment[] = [];
  let buffer = "";
  let depth = 0;
  let quote = false;
  let i = 0;

  while (i < statement.length) {
    const ch = statement[i];
    if (ch === '"') {
      quote = !quote;
      buffer += ch;
      i += 1;
      continue;
    }
    if (!quote) {
      if ("[({".includes(ch)) depth += 1;
      else if ("])}".includes(ch)) depth = Math.max(0, depth - 1);

      if (depth === 0 && (ch === "-" || ch === "=" || ch === "<")) {
        const read = readLink(statement, i);
        if (read) {
          segments.push({ text: buffer, link: read.token });
          buffer = "";
          i += read.length;
          continue;
        }
      }
    }
    buffer += ch;
    i += 1;
  }
  if (quote || depth !== 0) return null;
  segments.push({ text: buffer, link: null });
  return segments;
}

const NODE_TOKEN_RE = /^([A-Za-z0-9_.\-\u00c0-\uffff]+)([\s\S]*?)?(?::::([A-Za-z0-9_-]+))?$/;

type NodeToken = { id: string; label: string | null; shape: NodeShape | null; cls: string | null };

function parseNodeToken(raw: string): NodeToken | null {
  let text = raw.trim();
  if (!text) return null;

  let cls: string | null = null;
  const clsMatch = /:::([A-Za-z0-9_-]+)\s*$/.exec(text);
  if (clsMatch) {
    cls = clsMatch[1];
    text = text.slice(0, clsMatch.index).trim();
  }

  for (const [shape, open, close] of SHAPE_PAIRS) {
    const openAt = text.indexOf(open);
    if (openAt <= 0) continue;
    if (!text.endsWith(close)) continue;
    const id = text.slice(0, openAt).trim();
    if (!/^[A-Za-z0-9_.\-\u00c0-\uffff]+$/.test(id)) continue;
    const inner = text.slice(openAt + open.length, text.length - close.length);
    return { id, label: unquoteLabel(inner), shape, cls };
  }

  const bare = NODE_TOKEN_RE.exec(text);
  if (!bare || bare[2]) return null;
  if (!/^[A-Za-z0-9_.\-\u00c0-\uffff]+$/.test(bare[1])) return null;
  return { id: bare[1], label: null, shape: null, cls };
}

function unquoteLabel(raw: string): string {
  const t = raw.trim();
  if (t.length >= 2 && t.startsWith('"') && t.endsWith('"')) return t.slice(1, -1);
  if (t.length >= 2 && t.startsWith("'") && t.endsWith("'")) return t.slice(1, -1);
  return t;
}

function parseSubgraphHeader(rest: string): { id: string; title: string } {
  const text = rest.trim().replace(/;$/, "");
  const bracket = /^([A-Za-z0-9_.-]+)\s*\[([\s\S]*)\]$/.exec(text);
  if (bracket) return { id: bracket[1], title: unquoteLabel(bracket[2]) };
  const quoted = /^"([\s\S]*)"$/.exec(text);
  if (quoted) return { id: quoted[1], title: quoted[1] };
  return { id: text, title: text };
}

function parseLayoutComment(raw: string): Record<string, { x: number; y: number; w?: number; h?: number }> {
  const out: Record<string, { x: number; y: number; w?: number; h?: number }> = {};
  for (const chunk of raw.split(";")) {
    const m = /^\s*([A-Za-z0-9_.-]+)\s*=\s*(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)(?:,(\d+(?:\.\d+)?)x(\d+(?:\.\d+)?))?\s*$/.exec(
      chunk,
    );
    if (!m) continue;
    out[m[1]] = {
      x: Number(m[2]),
      y: Number(m[3]),
      ...(m[4] ? { w: Number(m[4]), h: Number(m[5]) } : {}),
    };
  }
  return out;
}

/**
 * Parse a Mermaid flowchart into the editable model.
 * Returns `ok: false` for other diagram types or syntax the editor cannot round-trip.
 */
export function parseFlowchart(source: string): ParseResult {
  const rawLines = source.replace(/\r\n/g, "\n").split("\n");
  const warnings: string[] = [];

  let headerIdx = -1;
  let keyword: "flowchart" | "graph" = "flowchart";
  let direction: FlowDirection = "TD";
  const preHeaderExtras: string[] = [];

  for (let i = 0; i < rawLines.length; i += 1) {
    const line = rawLines[i].trim();
    if (!line) continue;
    if (line.startsWith("%%")) {
      preHeaderExtras.push(line);
      continue;
    }
    const m = HEADER_RE.exec(line);
    if (!m) {
      return { ok: false, reason: "Only flowchart / graph diagrams can be edited graphically." };
    }
    keyword = m[1].toLowerCase() === "graph" ? "graph" : "flowchart";
    direction = normalizeDirection(m[2], "TD");
    headerIdx = i;
    break;
  }

  if (headerIdx < 0) return { ok: false, reason: "No flowchart header found." };

  const nodes = new Map<string, FlowNode>();
  const edges: FlowEdge[] = [];
  const subgraphs: FlowSubgraph[] = [];
  const classDefs: ClassDef[] = [];
  const nodeStyles: NodeStyle[] = [];
  const extras: string[] = [];
  let layoutHints: Record<string, { x: number; y: number; w?: number; h?: number }> = {};
  const stack: FlowSubgraph[] = [];
  let edgeSeq = 0;

  const ensureNode = (token: NodeToken): FlowNode => {
    const existing = nodes.get(token.id);
    if (existing) {
      if (token.label != null) {
        existing.label = token.label;
        const size = measureNode(existing.label, existing.shape);
        existing.w = size.w;
        existing.h = size.h;
      }
      if (token.shape) {
        existing.shape = token.shape;
        const size = measureNode(existing.label, existing.shape);
        existing.w = size.w;
        existing.h = size.h;
      }
      if (token.cls && !existing.classes.includes(token.cls)) existing.classes.push(token.cls);
      return existing;
    }
    const label = token.label ?? token.id;
    const shape = token.shape ?? "rect";
    const size = measureNode(label, shape);
    const node: FlowNode = {
      id: token.id,
      label,
      shape,
      classes: token.cls ? [token.cls] : [],
      x: 0,
      y: 0,
      w: size.w || DEFAULT_NODE_WIDTH,
      h: size.h || DEFAULT_NODE_HEIGHT,
    };
    nodes.set(node.id, node);
    if (stack.length) {
      const parent = stack[stack.length - 1];
      if (!parent.nodeIds.includes(node.id)) parent.nodeIds.push(node.id);
    }
    return node;
  };

  const claimForSubgraph = (id: string) => {
    if (!stack.length) return;
    const parent = stack[stack.length - 1];
    if (!parent.nodeIds.includes(id)) parent.nodeIds.push(id);
  };

  for (let i = headerIdx + 1; i < rawLines.length; i += 1) {
    const original = rawLines[i];
    const trimmed = original.trim();
    if (!trimmed) continue;

    if (trimmed.startsWith("%%")) {
      const layout = LAYOUT_COMMENT_RE.exec(trimmed);
      if (layout) {
        layoutHints = { ...layoutHints, ...parseLayoutComment(layout[1]) };
      } else {
        extras.push(trimmed);
      }
      continue;
    }

    const line = stripTrailingComment(trimmed).trim();
    if (!line) continue;

    if (/^end\b;?$/i.test(line)) {
      if (stack.length) subgraphs.push(stack.pop() as FlowSubgraph);
      continue;
    }

    const sub = SUBGRAPH_RE.exec(line);
    if (sub) {
      const { id, title } = parseSubgraphHeader(sub[1]);
      stack.push({ id, title, direction: null, nodeIds: [] });
      continue;
    }

    const dir = DIRECTION_RE.exec(line);
    if (dir) {
      if (stack.length) stack[stack.length - 1].direction = normalizeDirection(dir[1], "TD");
      else direction = normalizeDirection(dir[1], direction);
      continue;
    }

    const cd = CLASSDEF_RE.exec(line);
    if (cd) {
      for (const name of cd[1].split(",")) {
        classDefs.push({ name: name.trim(), styles: cd[2].trim() });
      }
      continue;
    }

    const cls = CLASS_RE.exec(line);
    if (cls) {
      for (const id of cls[1].split(",")) {
        const node = nodes.get(id.trim());
        if (node) {
          if (!node.classes.includes(cls[2])) node.classes.push(cls[2]);
        } else {
          extras.push(line);
          break;
        }
      }
      continue;
    }

    const st = STYLE_RE.exec(line);
    if (st) {
      nodeStyles.push({ nodeId: st[1], styles: st[2].trim() });
      continue;
    }

    if (/^(linkStyle|click|accTitle|accDescr)\b/i.test(line)) {
      extras.push(line);
      continue;
    }

    const segments = splitChain(normalizeInlineLinkLabels(line.replace(/;\s*$/, "")));
    if (!segments) {
      return { ok: false, reason: `Unbalanced brackets on line ${i + 1}.` };
    }

    if (segments.length === 1) {
      const groups = segments[0].text.split("&");
      let handled = true;
      for (const g of groups) {
        const token = parseNodeToken(g);
        if (!token) {
          handled = false;
          break;
        }
        ensureNode(token);
        claimForSubgraph(token.id);
      }
      if (!handled) {
        return { ok: false, reason: `Unsupported statement on line ${i + 1}: "${line.slice(0, 60)}"` };
      }
      continue;
    }

    let previous: string[] = [];
    for (let s = 0; s < segments.length; s += 1) {
      const seg = segments[s];
      const ids: string[] = [];
      for (const chunk of seg.text.split("&")) {
        const token = parseNodeToken(chunk);
        if (!token) {
          return { ok: false, reason: `Unsupported node on line ${i + 1}: "${chunk.trim().slice(0, 40)}"` };
        }
        ensureNode(token);
        claimForSubgraph(token.id);
        ids.push(token.id);
      }
      if (s > 0) {
        const link = segments[s - 1].link;
        if (link) {
          for (const from of previous) {
            for (const to of ids) {
              edgeSeq += 1;
              edges.push({
                id: `e${edgeSeq}`,
                source: from,
                target: to,
                label: link.label,
                line: link.line,
                head: link.head,
                bidirectional: link.bidirectional,
                length: link.length,
              });
            }
          }
        }
      }
      previous = ids;
    }
  }

  while (stack.length) subgraphs.push(stack.pop() as FlowSubgraph);

  if (nodes.size === 0) return { ok: false, reason: "No nodes found in this diagram." };

  const model: FlowchartModel = {
    keyword,
    direction,
    nodes: [...nodes.values()],
    edges,
    subgraphs,
    classDefs,
    nodeStyles,
    extras: [...preHeaderExtras, ...extras],
  };

  for (const node of model.nodes) {
    const hint = layoutHints[node.id];
    if (hint) {
      node.x = hint.x;
      node.y = hint.y;
      if (hint.w && hint.h) {
        node.w = hint.w;
        node.h = hint.h;
      }
    }
  }

  const hasLayout = model.nodes.every((n) => layoutHints[n.id] != null);
  if (!hasLayout && Object.keys(layoutHints).length > 0) {
    warnings.push("Some nodes had no saved position — they were laid out automatically.");
  }

  return { ok: true, model, warnings };
}

export function hasSavedLayout(source: string): boolean {
  return /^%%\s*layout:/im.test(source);
}
