import { describe, expect, it } from "vitest";
import { sanitizeMermaidSource } from "../src/components/study/mermaidSanitize";

const SAMPLE = `flowchart TD
    A[Start with Data] --> B{Goal: Understand Hidden Patterns?}
    B -- Yes, Unknown Goal --> C[Perform Exploratory Data Analysis (EDA)]
    C --> D(Identify Key Features & Relationships)
    D --> E{Need to Transform Data?}
    E -- Yes --> F[Data Manipulation/Cleaning]
    F --> G[Visualize Results using Libraries (Seaborn, Matplotlib)]
    G --> H[Understand Patterns & Formulate Hypothesis]`;

const INDEXING_FLOW = `graph TD
    A[Single Index Retrieval] --> B{Goal: Get one value}
    B --> C[Process: arr[i]]
    D[Conceptual Need: Get multiple values] --> E{Issue: Slow/Cumbersome loops?}
    E --> F[Solution: Slicing]
    F --> G["Output: A collection of elements - subset"]`;

describe("sanitizeMermaidSource", () => {
  it("quotes square bracket labels with array indexing arr[i]", () => {
    const fixed = sanitizeMermaidSource("B --> C[Process: arr[i]]");
    expect(fixed).toContain('C["Process: arr[i]"]');
    expect(fixed).not.toMatch(/C\[Process: arr\[i\]\]/);
  });

  it("fixes full indexing flowchart without parse-breaking labels", () => {
    const fixed = sanitizeMermaidSource(INDEXING_FLOW);
    expect(fixed).toContain('C["Process: arr[i]"]');
    expect(fixed.split("\n").length).toBeGreaterThanOrEqual(6);
  });

  it("converts edge labels with parentheses to pipe form", () => {
    const raw = "B -- No (Blank) --> D(Default to Array Index 0)";
    const fixed = sanitizeMermaidSource(raw);
    expect(fixed).toContain("-->|No (Blank)|");
    expect(fixed).toContain('D["Default to Array Index 0"]');
    expect(fixed).not.toContain('No["Blank"]');
  });

  it("fixes numpy slicing flowchart edge and stadium nodes", () => {
    const raw = `flowchart TD
    A[Start Defining Range] --> B{Is Start Parameter Provided?}
    B -- Yes --> C(Set Beginning Index)
    B -- No (Blank) --> D(Default to Array Index 0)
    F & G --> H[Slice is defined]`;
    const fixed = sanitizeMermaidSource(raw);
    expect(fixed).toContain("-->|Yes|");
    expect(fixed).toContain("-->|No (Blank)|");
    expect(fixed).toContain('C["Set Beginning Index"]');
    expect(fixed).not.toContain("F & G");
  });

  it("converts stadium nodes with nested parens like range()", () => {
    const raw =
      "A[Need Sequence/Index Positions] --> B(Use Python range() / np.arange())";
    const fixed = sanitizeMermaidSource(raw);
    expect(fixed).toContain('B["Use Python range() / np.arange()"]');
    expect(fixed).not.toContain("B(Use Python");
  });

  it("converts stadium nodes with ampersand to quoted brackets", () => {
    const fixed = sanitizeMermaidSource("C --> D(Identify Key Features & Relationships)");
    expect(fixed).toContain('D["Identify Key Features & Relationships"]');
  });

  it("quotes square bracket labels with parentheses", () => {
    const fixed = sanitizeMermaidSource(SAMPLE);
    expect(fixed).toContain('C["Perform Exploratory Data Analysis (EDA)"]');
    expect(fixed).toContain('D["Identify Key Features & Relationships"]');
    expect(fixed).toContain('G["Visualize Results using Libraries (Seaborn, Matplotlib)"]');
  });
});
