const STEP_HEADING_RE = /^Step\s+\d+:/i;

function looksLikeCodeLine(line: string): boolean {
  const t = line.trim();
  if (!t) return false;
  if (/^(import|from|def |class |print\(|return |#|@|if |for |while |with )/.test(t)) return true;
  if (/^[A-Za-z_]\w*\s*=/.test(t)) return true;
  if (/^\w+\(/.test(t)) return true;
  if (/^\w+\.\w+/.test(t)) return true;
  return false;
}

/** Wrap bare code lines after "Step N:" headings into ```python fences. */
export function repairStepCodeBlocks(text: string): string {
  const lines = text.split("\n");
  const out: string[] = [];
  let i = 0;
  let inFence = false;

  while (i < lines.length) {
    const line = lines[i];
    const trimmed = line.trim();

    if (trimmed.startsWith("```")) {
      inFence = !inFence;
      out.push(line);
      i += 1;
      continue;
    }

    if (inFence) {
      out.push(line);
      i += 1;
      continue;
    }

    if (STEP_HEADING_RE.test(trimmed)) {
      out.push(line);
      i += 1;
      while (i < lines.length && !lines[i].trim()) {
        out.push(lines[i]);
        i += 1;
      }
      const codeLines: string[] = [];
      while (i < lines.length) {
        const trimmed = lines[i].trim();
        if (!trimmed) break;
        if (STEP_HEADING_RE.test(trimmed) || /^#{1,6}\s/.test(trimmed) || trimmed.startsWith("```")) {
          break;
        }
        if (looksLikeCodeLine(lines[i])) {
          codeLines.push(lines[i]);
          i += 1;
        } else {
          break;
        }
      }
      if (codeLines.length > 0) {
        out.push("");
        out.push("```python");
        out.push(...codeLines);
        out.push("```");
      }
      continue;
    }
    out.push(line);
    i += 1;
  }

  return out.join("\n");
}

/** Fix ```python\\n```\\n code patterns from LLM output. */
export function repairSplitCodeFences(text: string): string {
  return text
    .replace(/```(\w+)\s*\n```\s*\n/g, "```$1\n")
    .replace(/```(\w+)\s*\n```\n/g, "```$1\n");
}

/** Close orphaned ``` fences before headings or new fences (any language). */
export function repairAllFences(text: string): string {
  const lines = text.split("\n");
  const out: string[] = [];
  let inFence = false;

  for (const line of lines) {
    const stripped = line.trim();

    if (!inFence && stripped.startsWith("```")) {
      inFence = true;
      out.push(line);
      continue;
    }

    if (inFence && stripped === "```") {
      inFence = false;
      out.push(line);
      continue;
    }

    if (inFence && (stripped.startsWith("```") || /^#{1,6}\s/.test(line))) {
      out.push("```");
      inFence = false;
    }

    out.push(line);
  }

  if (inFence) out.push("```");
  return out.join("\n");
}

/** Full note repair pipeline for the viewer. */
export function repairNoteMarkdown(text: string): string {
  let out = text;
  out = repairSplitCodeFences(out);
  out = repairAllFences(out);
  out = repairStepCodeBlocks(out);
  out = repairMermaidFences(out);
  return out;
}

/** Close ```mermaid blocks that LLM output left open before the next heading or fence. */
export function repairMermaidFences(text: string): string {
  const lines = text.split("\n");
  const out: string[] = [];
  let inMermaid = false;

  for (const line of lines) {
    const trimmed = line.trim();
    if (!inMermaid && trimmed.toLowerCase().startsWith("```mermaid")) {
      inMermaid = true;
      out.push(line);
      continue;
    }

    if (inMermaid) {
      if (trimmed === "```") {
        inMermaid = false;
        out.push(line);
        continue;
      }
      if (/^#{1,6}\s/.test(line)) {
        out.push("```");
        inMermaid = false;
        out.push(line);
        continue;
      }
      if (/^```\w/.test(trimmed) && !trimmed.toLowerCase().startsWith("```mermaid")) {
        out.push("```");
        inMermaid = false;
        out.push(line);
        continue;
      }
    }

    out.push(line);
  }

  if (inMermaid) out.push("```");
  return out.join("\n");
}
