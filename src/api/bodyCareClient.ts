/**
 * Focus body-care mirrors — written by scripts/run/bodycare_sidecar (MediaPipe).
 * SoftLand/Arm untouched.
 */
import { focusDataUrl } from "../utils/focusDataUrl";

export type BodyCareSample = {
  ts?: string;
  present?: boolean;
  attention_pct?: number;
  gaze_strength?: number;
  blink_rate?: number;
  blink_just_now?: boolean;
  yaw?: number;
  pitch?: number;
  roll?: number;
  neck_angle?: number | null;
  torso_angle?: number | null;
  posture_score?: number;
  distance_proxy?: number | null;
  sit_stand_hint?: string;
  sit_stand_score?: number | null;
  sit_stand_ready?: boolean;
  face_width?: number | null;
  nose_y?: number | null;
  shoulder_y?: number | null;
  ipd?: number | null;
  calibrating?: string | null;
};

export type BodyCareDay = {
  date?: string;
  samples?: number;
  present_minutes?: number;
  slouch_minutes?: number;
  attention_pct_avg?: number | null;
  posture_score_avg?: number | null;
  blink_rate_avg?: number | null;
  distance_proxy_avg?: number | null;
  sit_hint_sec?: number;
  stand_hint_sec?: number;
  present_sec?: number;
  away_sec?: number;
  slouch_sec?: number;
  updated_at?: string | null;
};

export type BodyCareControl = {
  port?: number;
  started?: boolean;
  calibrating?: string | null;
  remain_sec?: number;
  last_ok?: string | null;
  last_error?: string | null;
  sit_stand_ready?: boolean;
  sit_samples?: number;
  stand_samples?: number;
  gaze_ready?: boolean;
  gaze_samples?: number;
};

export type BodyCareMirror = {
  schema?: number;
  source?: string;
  updated_at?: string;
  sample?: BodyCareSample;
  day?: BodyCareDay;
  calibration?: {
    samples?: number;
    ready?: boolean;
    yaw0?: number;
    pitch0?: number;
    sit_samples?: number;
    stand_samples?: number;
    sit_stand_ready?: boolean;
    sit_nose_y?: number | null;
    stand_nose_y?: number | null;
  };
  control?: BodyCareControl;
};

export type BodyCareCalibrateMode = "neutral" | "sit" | "stand";

const DEFAULT_CONTROL_PORT = 8766;

export function bodyCareControlBase(port?: number): string {
  const p = typeof port === "number" && port > 0 ? port : DEFAULT_CONTROL_PORT;
  return `http://127.0.0.1:${p}`;
}

async function fetchJson<T>(file: string): Promise<T | null> {
  try {
    const res = await fetch(`${focusDataUrl(file)}?t=${Date.now()}`, { cache: "no-store" });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

export async function fetchBodyCareMirror(): Promise<BodyCareMirror | null> {
  return fetchJson<BodyCareMirror>("body_care.json");
}

export async function fetchBodyCareDay(day?: string): Promise<BodyCareDay | null> {
  const d =
    day ||
    (() => {
      const n = new Date();
      const p = (x: number) => String(x).padStart(2, "0");
      return `${n.getFullYear()}-${p(n.getMonth() + 1)}-${p(n.getDate())}`;
    })();
  return fetchJson<BodyCareDay>(`body_care_days/${d}.json`);
}

/** Fresh if updated within the last 15s. */
export function bodyCareMirrorIsLive(m: BodyCareMirror | null | undefined): boolean {
  if (!m?.updated_at) return false;
  const t = Date.parse(m.updated_at);
  if (!Number.isFinite(t)) return false;
  return Date.now() - t < 15_000;
}

function withTimeout(ms: number): { signal: AbortSignal; cancel: () => void } {
  const c = new AbortController();
  const t = window.setTimeout(() => c.abort(), ms);
  return {
    signal: c.signal,
    cancel: () => window.clearTimeout(t),
  };
}

export async function fetchBodyCareControlHealth(
  port?: number,
): Promise<(BodyCareControl & { ok?: boolean }) | null> {
  const { signal, cancel } = withTimeout(2500);
  try {
    const res = await fetch(`${bodyCareControlBase(port)}/health`, {
      cache: "no-store",
      signal,
    });
    if (!res.ok) return null;
    return (await res.json()) as BodyCareControl & { ok?: boolean };
  } catch {
    return null;
  } finally {
    cancel();
  }
}

/** Ask the running sidecar to recalibrate (neutral ~12s, sit/stand ~4s). */
export async function requestBodyCareCalibrate(
  mode: BodyCareCalibrateMode,
  port?: number,
): Promise<{ ok: boolean; detail?: string; control?: BodyCareControl }> {
  const { signal, cancel } = withTimeout(4000);
  try {
    const res = await fetch(`${bodyCareControlBase(port)}/calibrate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mode }),
      signal,
    });
    const j = (await res.json()) as BodyCareControl & { ok?: boolean; detail?: string };
    return { ok: Boolean(j.ok), detail: j.detail, control: j };
  } catch {
    return {
      ok: false,
      detail: "unreachable — start scripts\\run\\run_bodycare_sidecar.bat",
    };
  } finally {
    cancel();
  }
}
