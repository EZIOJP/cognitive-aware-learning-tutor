/** Sit/stand + eye rest prefs for Focus Body care (local only). */

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
    };
  } catch {
    return { ...DEFAULT_BODY_CARE };
  }
}

export function saveBodyCarePrefs(p: BodyCarePrefs): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(p));
  } catch {
    /* ignore */
  }
}

function clamp(n: number, lo: number, hi: number): number {
  if (!Number.isFinite(n)) return lo;
  return Math.max(lo, Math.min(hi, Math.round(n)));
}
