import type { CalibrationProfile } from "./calibration";
import type { FrameReading } from "./useHumanTracker";

export type FocusEventType = "head_turned_away" | "long_eye_closure" | "no_face";

export type FocusPayload = {
  not_focused: boolean;
  head_turned_away: boolean;
  long_eye_closure: boolean;
  no_face: boolean;
  active_event_type: FocusEventType | null;
};

const LONG_CLOSURE_SEC = 1.5;
const UNFOCUSED_SEC = 5.0;
const FALLBACK_YAW = 25;
const FALLBACK_PITCH = 20;

export class FocusState {
  private unfocusedSince: number | null = null;
  private eyesClosedSince: number | null = null;

  reset(): void {
    this.unfocusedSince = null;
    this.eyesClosedSince = null;
  }

  update(reading: FrameReading, profile: CalibrationProfile, eyelidBaseline: number): FocusPayload {
    const now = Date.now() / 1000;
    const closedThreshold = Math.max(0.08, eyelidBaseline * 0.45);
    const eyesClosed =
      reading.faceDetected && reading.eyeOpenness > 0 && reading.eyeOpenness < closedThreshold;

    if (eyesClosed) {
      if (this.eyesClosedSince === null) this.eyesClosedSince = now;
    } else {
      this.eyesClosedSince = null;
    }

    const longEyeClosure =
      this.eyesClosedSince !== null && now - this.eyesClosedSince > LONG_CLOSURE_SEC;

    let headTurnedAway = false;
    if (reading.faceDetected) {
      if (profile.createdAt) {
        const { range } = profile;
        headTurnedAway =
          reading.yaw < range.yawMin ||
          reading.yaw > range.yawMax ||
          reading.pitch < range.pitchMin ||
          reading.pitch > range.pitchMax;
      } else {
        headTurnedAway =
          Math.abs(reading.yaw) > FALLBACK_YAW || Math.abs(reading.pitch) > FALLBACK_PITCH;
      }
    }

    const noFace = !reading.faceDetected;
    const isUnfocusedNow = noFace || headTurnedAway || longEyeClosure;

    if (isUnfocusedNow) {
      if (this.unfocusedSince === null) this.unfocusedSince = now;
    } else {
      this.unfocusedSince = null;
    }

    const sustained = this.unfocusedSince !== null && now - this.unfocusedSince > UNFOCUSED_SEC;

    let activeEventType: FocusEventType | null = null;
    if (isUnfocusedNow) {
      if (noFace) activeEventType = "no_face";
      else if (longEyeClosure) activeEventType = "long_eye_closure";
      else if (headTurnedAway) activeEventType = "head_turned_away";
    }

    return {
      not_focused: sustained,
      head_turned_away: headTurnedAway,
      long_eye_closure: longEyeClosure,
      no_face: noFace,
      active_event_type: activeEventType,
    };
  }
}
