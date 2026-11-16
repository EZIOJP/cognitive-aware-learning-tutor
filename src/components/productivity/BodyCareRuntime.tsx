/**
 * Always-on sit/stand + eye-rest + posture timers for Focus (panel only edits prefs).
 * When attention reader is live: pause sit clock while away; warn on sustained slouch.
 */
import { useEffect, useRef } from "react";
import { loadBodyCarePrefs } from "../../lib/bodyCarePrefs";
import {
  readBodyCareVision,
  visionIsLive,
  type BodyCareVisionSample,
} from "../../lib/bodyCareVisionBus";

function notify(title: string, body: string) {
  if (typeof Notification === "undefined") return;
  if (Notification.permission !== "granted") return;
  try {
    new Notification(title, { body });
  } catch {
    /* ignore */
  }
}

export function BodyCareRuntime() {
  const lastInputRef = useRef(Date.now());
  const lastSitNotifyRef = useRef(0);
  const lastEyeNotifyRef = useRef(Date.now());
  const lastPostureNotifyRef = useRef(0);

  /** Accumulated seated ms while present (camera) or while input-active (no camera). */
  const sitAccumMsRef = useRef(0);
  const sitSegmentStartRef = useRef<number | null>(Date.now());
  const awaySinceRef = useRef<number | null>(null);
  const slouchSinceRef = useRef<number | null>(null);

  useEffect(() => {
    const bump = () => {
      lastInputRef.current = Date.now();
    };
    const evs = ["mousemove", "keydown", "pointerdown", "wheel", "touchstart"] as const;
    for (const e of evs) window.addEventListener(e, bump, { passive: true });
    return () => {
      for (const e of evs) window.removeEventListener(e, bump);
    };
  }, []);

  useEffect(() => {
    const id = window.setInterval(() => {
      const p = loadBodyCarePrefs();
      const now = Date.now();
      const vision = readBodyCareVision();
      const camLive = visionIsLive() && vision.tracking;

      // --- Sit accumulator ---
      if (p.sitStandEnabled) {
        if (camLive && p.presencePauseSit) {
          applyPresenceSit(vision, p.presenceAwaySec, now);
        } else {
          // Input-idle heuristic (no camera / pause off).
          awaySinceRef.current = null;
          const idleMs = now - lastInputRef.current;
          if (idleMs < 90_000) {
            if (sitSegmentStartRef.current == null) sitSegmentStartRef.current = now;
          } else if (sitSegmentStartRef.current != null) {
            sitAccumMsRef.current += now - sitSegmentStartRef.current;
            sitSegmentStartRef.current = null;
          }
        }

        const seatedMs =
          sitAccumMsRef.current +
          (sitSegmentStartRef.current != null ? now - sitSegmentStartRef.current : 0);
        const limit = p.sitMinutes * 60_000;
        if (seatedMs >= limit && now - lastSitNotifyRef.current > 5 * 60_000) {
          lastSitNotifyRef.current = now;
          notify(
            "CALT — stand up",
            `Still ~${p.sitMinutes} min. Stand ${p.standMinutes} min, then sit.`,
          );
          sitAccumMsRef.current = 0;
          sitSegmentStartRef.current = camLive && vision.faceDetected ? now : null;
          lastInputRef.current = now;
        }
      }

      // --- Posture coach (camera only) ---
      if (p.postureCoachEnabled && camLive && vision.faceDetected) {
        if (vision.slouching) {
          if (slouchSinceRef.current == null) slouchSinceRef.current = now;
          const holdMs = now - slouchSinceRef.current;
          if (
            holdMs >= p.postureWarnMinutes * 60_000 &&
            now - lastPostureNotifyRef.current > 5 * 60_000
          ) {
            lastPostureNotifyRef.current = now;
            slouchSinceRef.current = now;
            notify(
              "CALT — posture",
              `Neck/lean score ~${vision.postureScore}. Sit tall for a minute.`,
            );
          }
        } else {
          slouchSinceRef.current = null;
        }
      } else {
        slouchSinceRef.current = null;
      }

      if (p.eyeRestEnabled) {
        const elapsed = now - lastEyeNotifyRef.current;
        if (elapsed >= p.eyeRestMinutes * 60_000) {
          lastEyeNotifyRef.current = now;
          notify("CALT — eye rest", `Look away ${p.eyeRestSeconds}s (20–20–20).`);
        }
      }
    }, 5_000);
    return () => window.clearInterval(id);
  }, []);

  function applyPresenceSit(vision: BodyCareVisionSample, awaySec: number, now: number) {
    if (vision.faceDetected) {
      awaySinceRef.current = null;
      if (sitSegmentStartRef.current == null) sitSegmentStartRef.current = now;
      return;
    }
    if (awaySinceRef.current == null) awaySinceRef.current = now;
    const awayMs = now - awaySinceRef.current;
    if (awayMs < awaySec * 1000) {
      // Grace: still count as present.
      if (sitSegmentStartRef.current == null) sitSegmentStartRef.current = now;
      return;
    }
    // Stepped away — freeze sit clock (keep accum, close segment).
    if (sitSegmentStartRef.current != null) {
      sitAccumMsRef.current += now - sitSegmentStartRef.current;
      sitSegmentStartRef.current = null;
    }
  }

  return null;
}

export default BodyCareRuntime;
