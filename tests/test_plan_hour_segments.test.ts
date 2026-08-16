import { describe, expect, it } from "vitest";
import { planBlockToHourSegs } from "../src/components/productivity/planHourSegments";

describe("planBlockToHourSegs", () => {
  it("maps a block onto the minute X-axis within and across hours", () => {
    const day = new Date(2026, 7, 9); // Aug 9 local
    // 6:50–7:29
    const segs = planBlockToHourSegs(
      {
        id: 1,
        title: "Scaler practice",
        category: "Coding Practice",
        start_at: new Date(2026, 7, 9, 6, 50, 0).toISOString(),
        end_at: new Date(2026, 7, 9, 7, 29, 0).toISOString(),
      },
      day,
    );
    expect(segs).toHaveLength(2);
    expect(segs[0]).toMatchObject({
      hour: 6,
      start_min: 50,
      end_min: 60,
      seamLeft: false,
      seamRight: true,
    });
    expect(segs[1]).toMatchObject({
      hour: 7,
      start_min: 0,
      end_min: 29,
      seamLeft: true,
      seamRight: false,
    });
  });

  it("places a short break by start/end minutes (not full width)", () => {
    const day = new Date(2026, 7, 9);
    const segs = planBlockToHourSegs(
      {
        id: 2,
        title: "Break",
        category: "break",
        start_at: new Date(2026, 7, 9, 8, 44, 0).toISOString(),
        end_at: new Date(2026, 7, 9, 8, 54, 0).toISOString(),
      },
      day,
    );
    expect(segs).toHaveLength(1);
    expect(segs[0].start_min).toBe(44);
    expect(segs[0].end_min).toBe(54);
    expect(segs[0].end_min - segs[0].start_min).toBe(10);
  });
});
