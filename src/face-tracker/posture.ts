/**
 * Desk posture proxy from head pitch (Human.js face mesh) — no separate Pose model.
 * Chin-down / lean-in vs calibrated neutral → lower score (PosturePro-style hold warn).
 */
import type { CalibrationProfile } from "./calibration";
import type { FrameReading } from "./useHumanTracker";

export type PostureReading = {
  score: number;
  slouching: boolean;
  pitchDelta: number;
};

const SLOUCH_PITCH_DEG = 12;
const HARD_SLOUCH_DEG = 22;

/**
 * Score 0..100. Uses profile.neutral.pitch when calibrated; else absolute pitch.
 * Positive delta = looking more down than neutral (typical desk slouch / lean-in).
 */
export function scorePosture(
  reading: FrameReading,
  profile: CalibrationProfile,
  slouchThreshold = 55,
): PostureReading {
  if (!reading.faceDetected) {
    return { score: 100, slouching: false, pitchDelta: 0 };
  }

  const neutral = profile.createdAt ? profile.neutral.pitch : 0;
  const pitchDelta = reading.pitch - neutral;

  // Only punish downward lean; looking slightly up is fine at a laptop.
  const down = Math.max(0, pitchDelta);
  let score = 100;
  if (down > SLOUCH_PITCH_DEG) {
    score -= Math.min(55, ((down - SLOUCH_PITCH_DEG) / (HARD_SLOUCH_DEG - SLOUCH_PITCH_DEG)) * 55);
  }
  // Mild roll asymmetry as secondary lean signal.
  const rollAbs = Math.abs(reading.roll);
  if (rollAbs > 15) {
    score -= Math.min(20, (rollAbs - 15) * 1.2);
  }
  score = Math.max(0, Math.min(100, Math.round(score)));

  return {
    score,
    slouching: score < slouchThreshold,
    pitchDelta: Math.round(pitchDelta * 10) / 10,
  };
}
