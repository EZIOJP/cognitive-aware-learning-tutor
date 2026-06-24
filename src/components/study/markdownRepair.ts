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
