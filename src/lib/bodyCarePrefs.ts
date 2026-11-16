/** Sit/stand + eye rest + posture prefs for Focus Body care (local only). */

export type BodyCarePrefs = {
  sitStandEnabled: boolean;
  /** Minutes of continuous presence before "stand" nudge. */
  sitMinutes: number;
  /** Minutes to suggest standing (informational). */
  standMinutes: number;
  eyeRestEnabled: boolean;
  /** Minutes between eye-rest nudges (classic ~20). */
  eyeRestMinutes: number;
  /** Seconds to look away. */
  eyeRestSeconds: number;
  attentionEnabled: boolean;
  /**
   * When attention reader is live: pause sit clock while no face (stepped away).
   * Without camera, sit clock still uses input-idle.
   */
  presencePauseSit: boolean;
  /** Seconds without a face before sit clock freezes. */
  presenceAwaySec: number;
  /** Neck/lean coach from head pitch (same webcam as attention). */
  postureCoachEnabled: boolean;
  /** Minutes of sustained poor posture before nudge. */
  postureWarnMinutes: number;
  /** Posture score below this counts as slouching (0–100). */
  postureScoreThreshold: number;
};

const KEY = "calt:bodycare:prefs";

export const DEFAULT_BODY_CARE: BodyCarePrefs = {
  sitStandEnabled: true,
  sitMinutes: 30,
  standMinutes: 2,
  eyeRestEnabled: true,
  eyeRestMinutes: 20,
  eyeRestSeconds: 20,
  attentionEnabled: false,
  presencePauseSit: true,
  presenceAwaySec: 8,
  postureCoachEnabled: true,
  postureWarnMinutes: 3,
  postureScoreThreshold: 55,
};

export function loadBodyCarePrefs(): BodyCarePrefs {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return { ...DEFAULT_BODY_CARE };
    const j = JSON.parse(raw) as Partial<BodyCarePrefs>;
    return {
      sitStandEnabled: j.sitStandEnabled !== false,
      sitMinutes: clamp(Number(j.sitMinutes) || 30, 10, 120),
      standMinutes: clamp(Number(j.standMinutes) || 2, 1, 15),
      eyeRestEnabled: j.eyeRestEnabled !== false,
      eyeRestMinutes: clamp(Number(j.eyeRestMinutes) || 20, 10, 60),
      eyeRestSeconds: clamp(Number(j.eyeRestSeconds) || 20, 10, 60),
      attentionEnabled: j.attentionEnabled === true,
      presencePauseSit: j.presencePauseSit !== false,
      presenceAwaySec: clamp(Number(j.presenceAwaySec) || 8, 3, 60),
      postureCoachEnabled: j.postureCoachEnabled !== false,
      postureWarnMinutes: clamp(Number(j.postureWarnMinutes) || 3, 1, 15),
      postureScoreThreshold: clamp(Number(j.postureScoreThreshold) || 55, 25, 80),
    };
  } catch {
    return { ...DEFAULT_BODY_CARE };
  }
}

export function saveBodyCarePrefs(p: BodyCarePrefs): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(p));
    window.dispatchEvent(new CustomEvent("calt:bodycare:prefs-changed", { detail: p }));
  } catch {
    /* ignore */
  }
}

export function subscribeBodyCarePrefs(cb: (p: BodyCarePrefs) => void): () => void {
  const onStorage = (e: StorageEvent) => {
    if (e.key === KEY) cb(loadBodyCarePrefs());
  };
  const onCustom = () => cb(loadBodyCarePrefs());
  window.addEventListener("storage", onStorage);
  window.addEventListener("calt:bodycare:prefs-changed", onCustom);
  return () => {
    window.removeEventListener("storage", onStorage);
    window.removeEventListener("calt:bodycare:prefs-changed", onCustom);
  };
}

function clamp(n: number, lo: number, hi: number): number {
  if (!Number.isFinite(n)) return lo;
  return Math.max(lo, Math.min(hi, Math.round(n)));
}
