import { describe, expect, it } from "vitest";
import { resolveProposedOverlaps } from "./resolveProposedOverlaps";
import type { ProposedPlannerBlock } from "../../api/plannerClient";

function block(
  title: string,
  startLocal: string,
  endLocal: string,
  source: ProposedPlannerBlock["source"] = "study",
): ProposedPlannerBlock {
  // startLocal like "2026-07-20T06:00:00" interpreted as local via Date
  const start = new Date(startLocal);
  const end = new Date(endLocal);
  return {
    title,
    category: source === "break" ? "break" : "study",
    start_at: start.toISOString(),
    end_at: end.toISOString(),
    source,
  };
}

describe("resolveProposedOverlaps", () => {
  it("shifts later block after earlier when they overlap", () => {
    const a = block("A", "2026-07-20T08:00:00", "2026-07-20T09:00:00", "study");
    const b = block("B", "2026-07-20T08:30:00", "2026-07-20T09:30:00", "break");
    const out = resolveProposedOverlaps([a, b]);
    expect(out).toHaveLength(2);
    const t0 = new Date(out[0].end_at).getTime();
    const t1 = new Date(out[1].start_at).getTime();
    expect(t1).toBeGreaterThanOrEqual(t0);
  });

  it("dedupes near-identical routine copies", () => {
    const a = block("Bible / devotion", "2026-07-20T06:00:00", "2026-07-20T06:30:00", "routine");
    const b = block("Bible / devotion", "2026-07-20T06:00:00", "2026-07-20T06:30:00", "routine");
    const out = resolveProposedOverlaps([a, b]);
    expect(out).toHaveLength(1);
  });

  it("keeps routine before study when same start", () => {
    const study = block("Study", "2026-07-20T10:00:00", "2026-07-20T11:00:00", "study");
    const gym = block("Gym", "2026-07-20T10:00:00", "2026-07-20T11:00:00", "routine");
    const out = resolveProposedOverlaps([study, gym]);
    expect(out[0].title).toBe("Gym");
    expect(new Date(out[1].start_at).getTime()).toBeGreaterThanOrEqual(
      new Date(out[0].end_at).getTime(),
    );
  });
});
