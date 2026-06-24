/**
 * Fix Mermaid sources that break the parser before render/regenerate.
 */

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

/** Stadium nodes id(label) → id["label"] with balanced-paren parsing (handles range(), etc.). */
function fixStadiumNodes(line: string): string {
  const stadiumRe = /\b([A-Za-z0-9_]+)\s*\(/g;
  let out = "";
  let pos = 0;
  let match: RegExpExecArray | null;

  while ((match = stadiumRe.exec(line)) !== null) {
    if (match.index < pos) continue;
    if (isInsideBracketRegion(line, match.index) || isInsidePipeRegion(line, match.index)) {
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
    if (/[\[\]&()]/.test(label)) {
      return quoteLabel(id, label);
    }
    return _match;
  });

  return out;
}

function splitMergedNodes(line: string): string {
  return line.replace(/\](\s+)(?=[A-Za-z0-9_]+\s*[\[({])/g, "]\n    ");
}

/** `A -- label (parens) --> B` → `A -->|label (parens)| B` (must run before stadium fix). */
function fixEdgeLabels(line: string): string {
  return line.replace(/\s--\s+(.+?)\s+-->/g, (_match, label: string) => {
    const trimmed = label.trim();
    if (!trimmed) return " -->";
    return ` -->|${trimmed.replace(/\|/g, "/")}|`;
  });
}

/** `F & G --> H` → two edges (invalid mermaid syntax). */
function fixAmpersandLinks(line: string): string {
  return line.replace(
    /\b([A-Za-z0-9_]+)\s*&\s*([A-Za-z0-9_]+)\s*(-->|---)\s*(\S+)/g,
    (_m, a: string, b: string, arrow: string, target: string) =>
      `${a} ${arrow} ${target}\n    ${b} ${arrow} ${target}`,
  );
}

export function sanitizeMermaidSource(source: string): string {
  return source
    .split("\n")
    .map((line) => {
      let out = fixEdgeLabels(line);
      out = fixAmpersandLinks(out);
      out = fixSquareBracketNodes(out);
      out = splitMergedNodes(out);
      out = fixStadiumNodes(out);

      out = out.replace(/\b([A-Za-z0-9_]+)\s*\[([^\]"]+)\]/g, (_match, id: string, inner: string) => {
        const label = inner.trim();
        if (/[&()]/.test(label)) {
          return quoteLabel(id, label);
        }
        return _match;
      });

      return out;
    })
    .join("\n");
}
