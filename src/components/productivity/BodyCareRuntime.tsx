/**
 * Always-on sit/stand + eye-rest + posture timers for Focus (panel only edits prefs).
 * Prefers Python sidecar mirrors when fresh; else Human.js vision bus.
 * When sidecar reports sit_stand_hint=stand, the sit clock freezes.
 */
import { useEffect, useRef, useState } from "react";
import {
  bodyCareMirrorIsLive,
  fetchBodyCareMirror,
} from "../../api/bodyCareClient";
import { loadBodyCarePrefs } from "../../lib/bodyCarePrefs";
import {
  readBodyCareVision,
  visionIsLive,
  type BodyCareVisionSample,
} from "../../lib/bodyCareVisionBus";
import { isFocusSleeperActive, subscribeFocusSleeper } from "../../lib/focusSleeper";

function notify(title: string, body: string) {
  if (typeof Notification === "undefined") return;
  if (Notification.permission !== "granted") return;
  try {
    new Notification(title, { body });
  } catch {
    /* ignore */
  }
}

function normalizeHint(raw: string | undefined | null): "sit" | "stand" | "unknown" {
  if (raw === "sit" || raw === "stand") return raw;
  return "unknown";
}

export function BodyCareRuntime() {
  const [sleeper, setSleeper] = useState(() => isFocusSleeperActive());
  const lastInputRef = useRef(Date.now());
  const lastSitNotifyRef = useRef(0);
  const lastEyeNotifyRef = useRef(Date.now());
  const lastPostureNotifyRef = useRef(0);
  const sidecarRef = useRef<BodyCareVisionSample | null>(null);
  const sidecarLiveRef = useRef(false);

  /** Accumulated seated ms while present (camera) or while input-active (no camera). */
  const sitAccumMsRef = useRef(0);
  const sitSegmentStartRef = useRef<number | null>(Date.now());
  const awaySinceRef = useRef<number | null>(null);
  const slouchSinceRef = useRef<number | null>(null);

  useEffect(() => subscribeFocusSleeper((s) => setSleeper(s.active)), []);

  useEffect(() => {
    if (sleeper) return;
    const bump = () => {
      lastInputRef.current = Date.now();
    };
    const evs = ["mousemove", "keydown", "pointerdown", "wheel", "touchstart"] as const;
    for (const e of evs) window.addEventListener(e, bump, { passive: true });
    return () => {
      for (const e of evs) window.removeEventListener(e, bump);
    };
  }, [sleeper]);

  useEffect(() => {
    if (sleeper) {
      sidecarRef.current = null;
      sidecarLiveRef.current = false;
      return;
    }
    const pull = async () => {
      const m = await fetchBodyCareMirror();
      const live = bodyCareMirrorIsLive(m);
      sidecarLiveRef.current = live;
      if (!live || !m?.sample) {
        sidecarRef.current = null;
        return;
      }
      const s = m.sample;
      const thr = loadBodyCarePrefs().postureScoreThreshold;
      sidecarRef.current = {
        at: Date.now(),
        tracking: true,
        faceDetected: Boolean(s.present),
        postureScore: typeof s.posture_score === "number" ? s.posture_score : 50,
        slouching: typeof s.posture_score === "number" ? s.posture_score < thr : false,
        attention: typeof s.attention_pct === "number" ? s.attention_pct : 0,
        sitStandHint: normalizeHint(s.sit_stand_hint),
      };
    };
    void pull();
    const id = window.setInterval(() => void pull(), 4_000);
    return () => window.clearInterval(id);
  }, [sleeper]);

  useEffect(() => {
    if (sleeper) return;
    const id = window.setInterval(() => {
      const p = loadBodyCarePrefs();
      const now = Date.now();
      const human = readBodyCareVision();
      const sidecar = sidecarRef.current;
      const vision = sidecarLiveRef.current && sidecar ? sidecar : human;
      const camLive =
        (sidecarLiveRef.current && Boolean(sidecar?.tracking)) ||
        (visionIsLive() && human.tracking);

      // --- Sit accumulator ---
      if (p.sitStandEnabled) {
        if (camLive && vision.sitStandHint === "stand") {
          // Calibrated upper-body stand → freeze sit clock.
          awaySinceRef.current = null;
          if (sitSegmentStartRef.current != null) {
            sitAccumMsRef.current += now - sitSegmentStartRef.current;
            sitSegmentStartRef.current = null;
          }
        } else if (camLive && p.presencePauseSit) {
          applyPresenceSit(vision, p.presenceAwaySec, now);
        } else {
          // Input-idle heuristic (no camera / pause off / unknown posture).
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
          sitSegmentStartRef.current =
            camLive && vision.faceDetected && vision.sitStandHint !== "stand" ? now : null;
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
  }, [sleeper]);

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
