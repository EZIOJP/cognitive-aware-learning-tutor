/**
 * Lightweight vision samples from Focus attention reader → Body care timers.
 * No SoftLand/Arm coupling; camera stays client-side.
 */

export type BodyCareVisionSample = {
  /** Wall clock of last publish. */
  at: number;
  tracking: boolean;
  faceDetected: boolean;
  /** 0..100 neck/lean proxy from head pitch vs calibrated neutral. */
  postureScore: number;
  /** True when score is below coach threshold for a sustained hold. */
  slouching: boolean;
  attention: number;
};

const EVT = "calt:bodycare:vision";

let latest: BodyCareVisionSample = {
  at: 0,
  tracking: false,
  faceDetected: false,
  postureScore: 100,
  slouching: false,
  attention: 0,
};

export function publishBodyCareVision(sample: Omit<BodyCareVisionSample, "at">): void {
  latest = { ...sample, at: Date.now() };
  try {
    window.dispatchEvent(new CustomEvent(EVT, { detail: latest }));
  } catch {
    /* ignore */
  }
}

export function clearBodyCareVision(): void {
  publishBodyCareVision({
    tracking: false,
    faceDetected: false,
    postureScore: 100,
    slouching: false,
    attention: 0,
  });
}

export function readBodyCareVision(): BodyCareVisionSample {
  return latest;
}

/** True if a fresh sample arrived within `maxAgeMs` while tracking. */
export function visionIsLive(maxAgeMs = 2500): boolean {
  return latest.tracking && Date.now() - latest.at <= maxAgeMs;
}

export function subscribeBodyCareVision(cb: (s: BodyCareVisionSample) => void): () => void {
  const handler = (e: Event) => {
    const detail = (e as CustomEvent<BodyCareVisionSample>).detail;
    if (detail) cb(detail);
  };
  window.addEventListener(EVT, handler);
  return () => window.removeEventListener(EVT, handler);
}
