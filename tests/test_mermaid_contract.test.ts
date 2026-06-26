import { describe, expect, it } from "vitest";
import cases from "./fixtures/mermaid_cases.json";
import { layoutSafeMermaidSource, sanitizeMermaidSource } from "../src/features/mermaid/pipeline";

type MermaidCase = {
  id: string;
  input: string;
  layout_safe?: boolean;
  expect_contains?: string[];
  expect_not_contains?: string[];
  max_header_count?: number;
};

describe("mermaid contract fixtures", () => {
  for (const c of cases as MermaidCase[]) {
    it(c.id, () => {
      const fn = c.layout_safe ? layoutSafeMermaidSource : sanitizeMermaidSource;
      const out = fn(c.input);
      for (const fragment of c.expect_contains ?? []) {
        expect(out).toContain(fragment);
      }
      for (const fragment of c.expect_not_contains ?? []) {
        expect(out).not.toContain(fragment);
      }
      if (c.max_header_count != null) {
        const count = out.toLowerCase().split("flowchart td").length - 1;
        expect(count).toBeLessThanOrEqual(c.max_header_count);
      }
    });
  }
});
