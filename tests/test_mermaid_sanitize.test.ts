import { describe, expect, it } from "vitest";
import {
  dedupeRepeatedMermaidDiagram,
  extractMermaidFromLlmOutput,
  sanitizeMermaidSource,
} from "../src/features/mermaid/pipeline";

describe("sanitizeMermaidSource (no rewrite)", () => {
  it("preserves valid mermaid source as-is", () => {
    const raw = `flowchart TD
    A[Start] --> B{Decision}
    B -->|Yes| C[Do thing]
    B -->|No| D[Skip]`;
    expect(sanitizeMermaidSource(raw)).toBe(raw);
  });

  it("strips fence wrappers from LLM output", () => {
    const raw = "```mermaid\nflowchart LR\n  A --> B\n```";
    expect(sanitizeMermaidSource(raw)).toBe("flowchart LR\n  A --> B");
  });

  it("does not replace Direction/Index diagrams with a hardcoded template", () => {
    const raw = `flowchart TD
    A[Start] --> B{Direction}
    B --> C[Index -1]`;
    const out = sanitizeMermaidSource(raw);
    expect(out).toContain("Index -1");
    expect(out).not.toContain("Positive indices");
  });
});

describe("extractMermaidFromLlmOutput", () => {
  it("finds flowchart after preamble", () => {
    const raw = "Sure, here is a diagram:\n\nflowchart TD\n  A --> B";
    expect(extractMermaidFromLlmOutput(raw)).toContain("flowchart TD");
  });
});

describe("dedupeRepeatedMermaidDiagram", () => {
  it("keeps first diagram when headers repeat", () => {
    const raw = "flowchart TD\n  A --> B\nflowchart TD\n  C --> D";
    const out = dedupeRepeatedMermaidDiagram(raw);
    expect(out).toContain("A --> B");
    expect(out).not.toContain("C --> D");
  });
});
