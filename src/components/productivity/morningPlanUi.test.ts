import { beforeEach, describe, expect, it } from "vitest";
import {
  browserModeHint,
  formatBlockClock,
  planConfirmUi,
} from "./morningPlanUi";
import {
  DEFAULT_PLANNING_PREFS,
  loadPlanningPrefs,
  savePlanningPrefs,
  setAutoApplyRoutinesOnLogin,
} from "./planningPrefs";

describe("planConfirmUi", () => {
  it("marks window open during plan phase", () => {
    const ui = planConfirmUi({
      next: "plan",
      phase: "open",
      confirmAvailable: true,
      endLabel: "midnight",
      blocksToday: 3,
      planPoints: 10,
    });
    expect(ui.windowOpen).toBe(true);
    expect(ui.windowLabel).toContain("Open");
    expect(ui.ctaDisabled).toBe(false);
    expect(ui.ctaLabel).toContain("+10");
  });

  it("soft-opens before usual start when confirm allowed", () => {
    const ui = planConfirmUi({
      next: "plan",
      phase: "before_start",
      confirmAvailable: true,
      startClock: "06:30",
      planPoints: 10,
    });
    expect(ui.windowOpen).toBe(true);
    expect(ui.windowLabel).toContain("Open");
    expect(ui.ctaDisabled).toBe(false);
    expect(ui.ctaLabel).toContain("+10");
  });

  it("never locks confirm on clock even if API says unavailable", () => {
    const ui = planConfirmUi({
      next: "plan",
      phase: "before_start",
      confirmAvailable: false,
      startClock: "05:00",
      planPoints: 10,
    });
    expect(ui.windowOpen).toBe(true);
    expect(ui.ctaDisabled).toBe(false);
    expect(ui.windowLabel).not.toMatch(/Closed/i);
    expect(ui.ctaLabel).not.toMatch(/Opens at/i);
  });

  it("handles confirmed + soft after_eod", () => {
    expect(planConfirmUi({ planDone: true }).windowLabel).toBe("Confirmed");
    const soft = planConfirmUi({
      next: "open",
      planDone: false,
      phase: "after_eod",
      confirmAvailable: false,
      eodHhmm: "22:00",
      planPoints: 10,
    });
    expect(soft.windowOpen).toBe(true);
    expect(soft.windowLabel).toContain("22:00");
    expect(soft.ctaDisabled).toBe(false);
  });
});

describe("browserModeHint", () => {
  it("labels study as strict", () => {
    const h = browserModeHint({ mode: "study", modeLabel: "STUDY", freeAfter: "21:00" });
    expect(h?.tone).toBe("strict");
    expect(h?.detail).toContain("21:00");
  });

  it("labels free as free", () => {
    const h = browserModeHint({ mode: "free", modeLabel: "FREE" });
    expect(h?.tone).toBe("free");
  });

  it("returns null without mode", () => {
    expect(browserModeHint({})).toBeNull();
  });
});

describe("formatBlockClock", () => {
  it("formats valid iso", () => {
    const s = formatBlockClock("2026-08-05T09:30:00");
    expect(s).not.toBe("—");
    expect(s.length).toBeGreaterThan(3);
  });

  it("falls back on bad input", () => {
    expect(formatBlockClock("not-a-date")).toBe("—");
  });
});

describe("planningPrefs", () => {
  const store: Record<string, string> = {};

  beforeEach(() => {
    for (const k of Object.keys(store)) delete store[k];
    Object.defineProperty(globalThis, "localStorage", {
      configurable: true,
      value: {
        getItem: (k: string) => (k in store ? store[k] : null),
        setItem: (k: string, v: string) => {
          store[k] = String(v);
        },
        removeItem: (k: string) => {
          delete store[k];
        },
      },
    });
  });

  it("defaults and round-trips auto-apply flag", () => {
    expect(loadPlanningPrefs()).toEqual(DEFAULT_PLANNING_PREFS);
    setAutoApplyRoutinesOnLogin(false);
    expect(loadPlanningPrefs().autoApplyRoutinesOnLogin).toBe(false);
    savePlanningPrefs({ autoApplyRoutinesOnLogin: true });
    expect(loadPlanningPrefs().autoApplyRoutinesOnLogin).toBe(true);
  });
});
