import { describe, expect, it } from "vitest";
import { FocusState } from "../src/face-tracker/focusState";
import { DEFAULT_PROFILE } from "../src/face-tracker/calibration";
import type { FrameReading } from "../src/face-tracker/useHumanTracker";

function reading(over: Partial<FrameReading>): FrameReading {
  return {
    faceDetected: true,
    yaw: 0,
    pitch: 0,
    roll: 0,
    gazeStrength: 0,
    eyeOpenness: 0.3,
    timestamp: Date.now(),
    ...over,
  };
}

describe("FocusState", () => {
  it("flags head turned away with fallback thresholds", () => {
    const fs = new FocusState();
    const r = reading({ yaw: 30, pitch: 0 });
    const f = fs.update(r, DEFAULT_PROFILE, DEFAULT_PROFILE.eyelidBaseline);
    expect(f.head_turned_away).toBe(true);
    expect(f.not_focused).toBe(false);
  });

  it("does not flag not_focused immediately", () => {
    const fs = new FocusState();
    const r = reading({ faceDetected: false });
    const f = fs.update(r, DEFAULT_PROFILE, DEFAULT_PROFILE.eyelidBaseline);
    expect(f.no_face).toBe(true);
    expect(f.not_focused).toBe(false);
  });
});
