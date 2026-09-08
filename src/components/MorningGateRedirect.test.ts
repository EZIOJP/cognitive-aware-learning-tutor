import { spaNavigateTarget } from "./MorningGateRedirect";

describe("spaNavigateTarget", () => {
  it("keeps app paths", () => {
    expect(spaNavigateTarget("/bible")).toBe("/bible");
    expect(spaNavigateTarget("/productivity?tab=plan")).toBe("/productivity?tab=plan");
  });

  it("strips absolute SPA origins for React Router", () => {
    expect(spaNavigateTarget("http://localhost:5173/bible")).toBe("/bible");
    expect(spaNavigateTarget("http://127.0.0.1:5173/productivity?tab=plan")).toBe(
      "/productivity?tab=plan"
    );
  });

  it("falls back when empty or opaque", () => {
    expect(spaNavigateTarget("", "/bible")).toBe("/bible");
    expect(spaNavigateTarget("ftp://x", "/bible")).toBe("/bible");
  });
});
