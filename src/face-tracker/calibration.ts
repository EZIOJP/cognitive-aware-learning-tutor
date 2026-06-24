/** Per-setup calibration profiles stored in localStorage. */

export type CalibrationProfile = {
  name: string;
  /** Head pose when looking at screen center. */
  neutral: { yaw: number; pitch: number };
  /** Head-pose range covering "eyes on screen" for this camera angle (degrees). */
  range: { yawMin: number; yawMax: number; pitchMin: number; pitchMax: number };
  /** Max iris gaze strength observed while looking at screen edges. */
  gazeMax: number;
  /** Mean eye aspect ratio with eyes open at this angle. */
  eyelidBaseline: number;
  createdAt: string;
};

export type DotSample = {
  yaw: number;
  pitch: number;
  gazeStrength: number;
  eyeOpenness: number;
};

const PREFIX = "focus_mirror:calibration_v2:";
const ACTIVE_KEY = "focus_mirror:active_profile";
const POSE_MARGIN_DEG = 5;
const GAZE_MARGIN = 0.15;

export const DEFAULT_PROFILE: CalibrationProfile = {
  name: "default",
  neutral: { yaw: 0, pitch: 0 },
  range: { yawMin: -20, yawMax: 20, pitchMin: -15, pitchMax: 15 },
  gazeMax: 0.6,
  eyelidBaseline: 0.28,
  createdAt: "",
};

export function saveProfile(profile: CalibrationProfile): void {
  localStorage.setItem(PREFIX + profile.name, JSON.stringify(profile));
}

export function loadProfile(name: string): CalibrationProfile | null {
  const raw = localStorage.getItem(PREFIX + name);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as CalibrationProfile;
  } catch {
    return null;
  }
}

export function listProfiles(): CalibrationProfile[] {
  const out: CalibrationProfile[] = [];
  for (let i = 0; i < localStorage.length; i++) {
    const key = localStorage.key(i);
    if (key?.startsWith(PREFIX)) {
      const p = loadProfile(key.slice(PREFIX.length));
      if (p) out.push(p);
    }
  }
  return out.sort((a, b) => a.name.localeCompare(b.name));
}

export function deleteProfile(name: string): void {
  localStorage.removeItem(PREFIX + name);
  if (getActiveProfileName() === name) localStorage.removeItem(ACTIVE_KEY);
}

export function getActiveProfileName(): string | null {
  return localStorage.getItem(ACTIVE_KEY);
}

export function setActiveProfileName(name: string): void {
  localStorage.setItem(ACTIVE_KEY, name);
}

/** Active profile, or the uncalibrated default. */
export function getActiveProfile(): CalibrationProfile {
  const name = getActiveProfileName();
  if (name) {
    const p = loadProfile(name);
    if (p) return p;
  }
  return DEFAULT_PROFILE;
}

/** Build a profile from averaged per-dot samples ("center" dot = neutral). */
export function buildProfile(name: string, dotSamples: Record<string, DotSample>): CalibrationProfile {
  const samples = Object.values(dotSamples);
  if (samples.length === 0) throw new Error("No calibration samples collected");

  const center = dotSamples["center"] ?? samples[0];
  const yaws = samples.map((s) => s.yaw);
  const pitches = samples.map((s) => s.pitch);
  const gazes = samples.map((s) => s.gazeStrength);
  const lids = samples.map((s) => s.eyeOpenness).filter((v) => v > 0);

  return {
    name,
    neutral: { yaw: center.yaw, pitch: center.pitch },
    range: {
      yawMin: Math.min(...yaws) - POSE_MARGIN_DEG,
      yawMax: Math.max(...yaws) + POSE_MARGIN_DEG,
      pitchMin: Math.min(...pitches) - POSE_MARGIN_DEG,
      pitchMax: Math.max(...pitches) + POSE_MARGIN_DEG,
    },
    gazeMax: Math.max(...gazes, 0.2) + GAZE_MARGIN,
    eyelidBaseline:
      lids.length > 0 ? lids.reduce((a, b) => a + b, 0) / lids.length : DEFAULT_PROFILE.eyelidBaseline,
    createdAt: new Date().toISOString(),
  };
}
