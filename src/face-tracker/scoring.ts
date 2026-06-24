import type { CalibrationProfile } from "./calibration";
import type { FrameReading } from "./useHumanTracker";

export type FaceStatusPayload = {
  attention: number;
  attitude: string;
  blink_rate: number;
  face_detected: boolean;
  details: Record<string, number>;
};

/** Rising-edge blink counter over a rolling 60 s window (ported from face_tracker.py). */
export class BlinkRateTracker {
  private events = 0;
  private wasClosed = false;
  private windowStart = Date.now();

  update(eyeOpenness: number, eyelidBaseline: number): number {
    const closedThreshold = Math.max(0.08, eyelidBaseline * 0.45);
    const reopenThreshold = Math.max(0.12, eyelidBaseline * 0.7);

    if (eyeOpenness > 0 && eyeOpenness < closedThreshold && !this.wasClosed) {
      this.events += 1;
      this.wasClosed = true;
    } else if (eyeOpenness > reopenThreshold) {
      this.wasClosed = false;
    }

    const elapsedSec = Math.max(1, (Date.now() - this.windowStart) / 1000);
    const rate = (this.events / elapsedSec) * 60;

    if (elapsedSec >= 60) {
      this.events = 0;
      this.windowStart = Date.now();
    }
    return rate;
  }

  reset(): void {
    this.events = 0;
    this.wasClosed = false;
    this.windowStart = Date.now();
  }
}

/**
 * Attention from deviation relative to the calibrated profile — not absolute
 * angles — so off-axis camera setups score correctly.
 */
export function scoreAttention(
  reading: FrameReading,
  profile: CalibrationProfile,
  blinkRate: number,
): FaceStatusPayload {
  if (!reading.faceDetected) {
    return {
      attention: 0,
      attitude: "away",
      blink_rate: Math.round(blinkRate * 10) / 10,
      face_detected: false,
      details: {},
    };
  }

  const { range, gazeMax } = profile;
  const yawExcess = Math.max(0, range.yawMin - reading.yaw, reading.yaw - range.yawMax);
  const pitchExcess = Math.max(0, range.pitchMin - reading.pitch, reading.pitch - range.pitchMax);
  const poseExcess = yawExcess + pitchExcess;
  const gazeExcess = Math.max(0, reading.gazeStrength - gazeMax);

  let attention = 100;
  attention -= Math.min(55, poseExcess * 3);
  attention -= Math.min(20, gazeExcess * 100);
  attention -= Math.min(20, Math.max(0, blinkRate - 25) * 1.5);
  attention = Math.max(0, Math.min(100, attention));

  let attitude: string;
  if (blinkRate > 32) {
    attitude = "tired";
  } else if (attention < 45) {
    attitude = "distracted";
  } else {
    attitude = "focused";
  }

  return {
    attention: Math.round(attention * 10) / 10,
    attitude,
    blink_rate: Math.round(blinkRate * 10) / 10,
    face_detected: true,
    details: {
      yaw: Math.round(reading.yaw * 10) / 10,
      pitch: Math.round(reading.pitch * 10) / 10,
      gaze_strength: Math.round(reading.gazeStrength * 1000) / 1000,
      eye_openness: Math.round(reading.eyeOpenness * 1000) / 1000,
      pose_excess: Math.round(poseExcess * 10) / 10,
    },
  };
}
