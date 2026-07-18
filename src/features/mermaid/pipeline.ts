/**
 * Light Mermaid helpers — no syntax rewriting.
 * Diagrams are standard ```mermaid fences; Mermaid.js parses them as-is.
 */

const MERMAID_HEADER_RE =
  /^(flowchart|graph|sequenceDiagram|classDiagram|stateDiagram|erDiagram|gantt|pie)\b/i;

const MERMAID_REPEAT_HEADER_RE = /(?:flowchart|graph)\s+(?:TD|TB|BT|RL|LR)\b/gi;

const EXTRACT_DIAGRAM_RE = /((?:flowchart|graph)\s+(?:TD|TB|BT|RL|LR)\b[\s\S]*)/i;

/** Keep first diagram when small LLMs glue or repeat flowchart headers. */
export function dedupeRepeatedMermaidDiagram(source: string): string {
  const s = source.trim();
  if (!s) return s;
  const starts: number[] = [];
  MERMAID_REPEAT_HEADER_RE.lastIndex = 0;
  let m: RegExpExecArray | null;
  while ((m = MERMAID_REPEAT_HEADER_RE.exec(s)) !== null) {
    starts.push(m.index);
  }
  if (starts.length <= 1) return s;
  return s.slice(starts[0], starts[1]).trim();
}

/** Strip fence wrappers / reasoning preamble from LLM output. */
export function extractMermaidFromLlmOutput(raw: string): string {
  let text = raw.trim();
  if (!text) return text;
  text = text.replace(/^```(?:mermaid)?\s*\n?/i, "").replace(/\n?```\s*$/i, "").trim();
  const firstLine = text.split("\n").find((ln) => ln.trim())?.trim() ?? "";
  if (firstLine && MERMAID_HEADER_RE.test(firstLine)) return text;
  const match = EXTRACT_DIAGRAM_RE.exec(text);
  if (match) return match[1].trim();
  return text;
}

/** Normalize source for render/save: extract + dedupe only (no label rewrites). */
export function sanitizeMermaidSource(source: string): string {
  return dedupeRepeatedMermaidDiagram(extractMermaidFromLlmOutput(source)).trim();
}

/** @deprecated Alias kept for call-site compatibility — same as sanitizeMermaidSource. */
export function aggressiveSanitizeMermaidSource(source: string): string {
  return sanitizeMermaidSource(source);
}

/** @deprecated Alias kept for call-site compatibility — same as sanitizeMermaidSource. */
export function layoutSafeMermaidSource(source: string): string {
  return sanitizeMermaidSource(source);
}

export function mermaidLintIssues(source: string): string[] {
  const s = source.trim();
  if (!s) return ["empty diagram"];
  const first = s.split("\n").find((ln) => ln.trim())?.trim() ?? "";
  if (!MERMAID_HEADER_RE.test(first)) return ["missing flowchart/graph header"];
  return [];
}

export function isMermaidLikelyBroken(source: string): boolean {
  return mermaidLintIssues(source).length > 0;
}
