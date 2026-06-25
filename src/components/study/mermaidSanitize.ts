/**
 * Strict Mermaid sanitization — mirrors backend/transcripts/mermaid_strict.py
 */

const MERMAID_HEADER_RE =
  /^(flowchart|graph|sequenceDiagram|classDiagram|stateDiagram|erDiagram|gantt|pie)\b/i;

function quoteLabel(id: string, label: string): string {
  return `${id.trim()}["${label.trim().replace(/"/g, "'")}"]`;
}

function findBalancedParen(s: string, openPos: number): number {
  if (openPos < 0 || openPos >= s.length || s[openPos] !== "(") return -1;
  let depth = 0;
  for (let i = openPos; i < s.length; i++) {
    if (s[i] === "(") depth++;
    else if (s[i] === ")") {
      depth--;
      if (depth === 0) return i;
    }
  }
  return -1;
}

function isInsideBracketRegion(line: string, index: number): boolean {
  let inSquare = false;
  let inDiamond = false;
  let inQuote = false;
  for (let i = 0; i < index; i++) {
    const c = line[i];
    if (c === '"' && (i === 0 || line[i - 1] !== "\\")) inQuote = !inQuote;
    if (inQuote) continue;
    if (c === "[") inSquare = true;
    else if (c === "]" && inSquare) inSquare = false;
    else if (c === "{") inDiamond = true;
    else if (c === "}" && inDiamond) inDiamond = false;
  }
  return inSquare || inDiamond;
}

function isInsidePipeRegion(line: string, index: number): boolean {
  let inPipe = false;
  for (let i = 0; i < index; i++) {
    if (line[i] === "|") inPipe = !inPipe;
  }
  return inPipe;
}

function braceIdSuffix(raw: string): string {
  const cleaned = raw.trim().replace(/[^\w]+/g, "_").replace(/^_+|_+$/g, "");
  return cleaned || "x";
}

function fixBraceNodeIds(line: string): string {
  return line.replace(
    /\b([A-Za-z0-9_]+)_\{([^}]+)\}\s*\(([^)]+)\)/g,
    (_m, prefix: string, inner: string, label: string) =>
      quoteLabel(`${prefix}_${braceIdSuffix(inner)}`, label),
  );
}

function fixColonAfterSquareLabel(line: string): string {
  return line.replace(
    /\b([A-Za-z0-9_]+)\s*\[([^\]"]+)\]\s*:\s*(.+)$/,
    (_m, id: string, inner: string, rest: string) =>
      quoteLabel(id, `${inner.trim()}: ${rest.trim()}`),
  );
}

function fixMalformedPipeEdges(line: string): string {
  return line
    .replace(/-->\s*\|:\s*([^:|]+?)\s*:\s*\|/g, (_m, label: string) => `-->|${label.trim()}|`)
    .replace(/-->\s*\|\s*:\s*([^:|]+?)\s*:\s*\|/g, (_m, label: string) => `-->|${label.trim()}|`);
}

function fixEdgeLabels(line: string): string {
  return line.replace(/\s--\s+(.+?)\s+-->/g, (_match, label: string) => {
    const trimmed = label.trim();
    if (!trimmed) return " -->";
    return ` -->|${trimmed.replace(/\|/g, "/")}|`;
  });
}

function fixAmpersandLinks(line: string): string {
  return line.replace(
    /\b([A-Za-z0-9_]+)\s*&\s*([A-Za-z0-9_]+)\s*(-->|---)\s*(.+)$/,
    (_m, a: string, b: string, arrow: string, target: string) =>
      `${a} ${arrow} ${target.trim()}\n    ${b} ${arrow} ${target.trim()}`,
  );
}

function isInsideQuotedString(line: string, index: number): boolean {
  let inQuote = false;
  for (let i = 0; i < index; i++) {
    if (line[i] === '"' && (i === 0 || line[i - 1] !== "\\")) inQuote = !inQuote;
  }
  return inQuote;
}

function fixQuotedDiamondNodes(line: string): string {
  return line.replace(/(\b[A-Za-z0-9_]+)\{"([^"]+)"\}/g, "$1{$2}");
}

function fixStadiumNodes(line: string): string {
  const stadiumRe = /\b([A-Za-z0-9_]+)\s*\(/g;
  let out = "";
  let pos = 0;
  let match: RegExpExecArray | null;

  while ((match = stadiumRe.exec(line)) !== null) {
    if (match.index < pos) continue;
    if (
      isInsideBracketRegion(line, match.index) ||
      isInsidePipeRegion(line, match.index) ||
      isInsideQuotedString(line, match.index)
    ) {
      out += line.slice(pos, match.index + match[0].length);
      pos = match.index + match[0].length;
      stadiumRe.lastIndex = pos;
      continue;
    }
    out += line.slice(pos, match.index);
    const id = match[1];
    const openParen = match.index + match[0].length - 1;
    const closeIdx = findBalancedParen(line, openParen);
    if (closeIdx < 0) {
      out += line.slice(match.index, match.index + match[0].length);
      pos = match.index + match[0].length;
      stadiumRe.lastIndex = pos;
      continue;
    }
    const inner = line.slice(openParen + 1, closeIdx);
    out += quoteLabel(id, inner);
    pos = closeIdx + 1;
    stadiumRe.lastIndex = pos;
  }
  out += line.slice(pos);
  return out;
}

function fixSquareBracketNodes(line: string): string {
  let out = line.replace(
    /\b([A-Za-z0-9_]+)\s*\[([^\]]*\[[^\]]+\][^\]]*)\]/g,
    (_match, id: string, inner: string) => quoteLabel(id, inner),
  );

  out = out.replace(/\b([A-Za-z0-9_]+)\s*\[([^\]"]+)\]/g, (_match, id: string, inner: string) => {
    const label = inner.trim();
    if (/[\[\]&():]/.test(label)) {
      return quoteLabel(id, label);
    }
    return _match;
  });

  return out;
}

function splitMergedNodes(line: string): string {
  return line.replace(/\](\s+)(?=[A-Za-z0-9_]+\s*[\[({])/g, "]\n    ");
}

function fixDiamondNodes(line: string): string {
  return line.replace(/\b([A-Za-z0-9_]+)\s*\{([^{}]+)\}/g, (match, id: string, inner: string) => {
    if (!/[()]/.test(inner)) return match;
    const label = inner
      .replace(/\s*\(([^)]*)\)/g, " - $1")
      .replace(/[{}]/g, "")
      .trim();
    return quoteLabel(id, label);
  });
}

const MAX_NODE_LABEL_LEN = 42;
const MAX_EDGE_LABEL_LEN = 14;
const EDGE_LABEL_SHORT: Record<string, string> = {
  "Left to Right": "L to R",
  "Right to Left": "R to L",
};

function softenLayoutLabel(text: string, maxLen = MAX_NODE_LABEL_LEN): string {
  let t = text.trim();
  t = EDGE_LABEL_SHORT[t] ?? t;
  t = t.replace(/\.{2,}/g, " etc");
  t = t.replace(/W\[-1\]/g, "index -1").replace(/W\[len-1\]/g, "len-1 index");
  t = t.replace(/\(W\[-1\]\)/g, "index -1").replace(/\(index -1\)/g, "at index -1");
  t = t.replace(/(\w+)\[([^\]]+)\]/g, "$1($2)");
  if (t.length > maxLen) {
    t = `${t.slice(0, maxLen - 4).replace(/,\s*$/, "")} etc`;
  }
  return t;
}

function fixLayoutLabels(line: string): string {
  let out = line.replace(/\["([^"]+)"\]/g, (_m, label: string) => `["${softenLayoutLabel(label)}"]`);
  out = out.replace(
    /-->\|([^|]+)\|/g,
    (_m, label: string) => `-->|${softenLayoutLabel(label, MAX_EDGE_LABEL_LEN)}|`,
  );
  return out;
}

function fixMermaidLine(line: string): string[] {
  let stripped = line.replace(/;+\s*$/, "");
  if (!stripped.trim()) return [stripped];
  if (stripped.trim().startsWith("subgraph ") || stripped.trim() === "end") return [stripped];

  stripped = fixLayoutLabels(stripped);
  stripped = fixQuotedDiamondNodes(stripped);
  stripped = fixMalformedPipeEdges(stripped);
  stripped = fixEdgeLabels(stripped);
  stripped = fixAmpersandLinks(stripped);
  stripped = fixBraceNodeIds(stripped);
  stripped = fixColonAfterSquareLabel(stripped);
  stripped = fixSquareBracketNodes(stripped);
  stripped = splitMergedNodes(stripped);
  stripped = fixStadiumNodes(stripped);

  stripped = stripped.replace(
    /\b([A-Za-z0-9_]+)\s*\[([^\]"]+)\]/g,
    (_match, id: string, inner: string) => {
      const label = inner.trim();
      if (/[\[\]&():]/.test(label)) {
        return quoteLabel(id, label);
      }
      return _match;
    },
  );

  stripped = fixDiamondNodes(stripped);
  return stripped.split("\n");
}

function ensureDiagramHeader(lines: string[]): string[] {
  for (const line of lines) {
    if (line.trim()) {
      if (MERMAID_HEADER_RE.test(line.trim())) return lines;
      break;
    }
  }
  return ["flowchart TD", ...lines];
}

function withoutPipeEdgeLabels(source: string): string {
  return source.replace(/-->\|[^|]*\|/g, "-->|");
}

export function mermaidLintIssues(source: string): string[] {
  const issues: string[] = [];
  const s = source.trim();
  if (!s) return ["empty diagram"];
  const first = s.split("\n").find((l) => l.trim())?.trim() ?? "";
  if (!MERMAID_HEADER_RE.test(first)) issues.push("missing flowchart/graph header");
  const lintBody = withoutPipeEdgeLabels(s);
  if (/\s--\s+[^|>\n][^>]*\s+-->/.test(lintBody)) issues.push("legacy edge label syntax (-- text -->)");
  if (/\b[A-Za-z0-9_]+\s*\(/.test(lintBody)) issues.push("stadium node id(label)");
  if (/\s&\s*[A-Za-z0-9_]+\s*(-->|---)/.test(s)) issues.push("ampersand-merged edges");
  if (/-->\s*\|:/.test(s)) issues.push("malformed pipe edge (-->|:)");
  if (/\[[^\]"]+\]\s*:/.test(s)) issues.push("colon after unquoted ] label");
  if (/_\{[^}]+\}/.test(s)) issues.push("brace characters in node id");
  return issues;
}

export function isMermaidLikelyBroken(source: string): boolean {
  return mermaidLintIssues(source).length > 0;
}

export function sanitizeMermaidSource(source: string): string {
  const lines = ensureDiagramHeader(source.split("\n"));
  const fixed: string[] = [];
  for (const line of lines) {
    fixed.push(...fixMermaidLine(line));
  }
  return fixed.join("\n");
}

/** Layout-safe second pass — mirrors backend aggressive_sanitize_mermaid_source. */
export function aggressiveSanitizeMermaidSource(source: string): string {
  let out = sanitizeMermaidSource(source);
  out = out.replace(/\bW\s*\[[^\]]*\]/g, "index -1");
  out = out.replace(
    /\b([A-Za-z0-9_]+)\[([^"\]\{}]+)\]/g,
    (_m, id: string, label: string) => `["${softenLayoutLabel(label, 34)}"]`,
  );
  out = out.replace(/\["([^"]+)"\]/g, (_m, label: string) => `["${softenLayoutLabel(label, 34)}"]`);
  if (/\bDirection\b/.test(out) && /Index|index/.test(out)) {
    return [
      "flowchart TD",
      "    A[Start] --> B{Direction}",
      "    B -->|L to R| C[Positive indices]",
      "    B -->|R to L| D[Negative indices]",
      "    D --> E[Last at index -1]",
      "    C --> F[Length minus one]",
    ].join("\n");
  }
  return out;
}
