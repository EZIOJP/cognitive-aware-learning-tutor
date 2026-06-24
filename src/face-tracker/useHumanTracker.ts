import { useEffect, useRef, useState, type RefObject } from "react";
import { getHuman } from "./human";

export type FrameReading = {
  faceDetected: boolean;
  /** Head yaw in degrees (negative = looking left). */
  yaw: number;
  /** Head pitch in degrees (negative = looking down). */
  pitch: number;
  roll: number;
  /** Iris gaze offset strength 0..1 (0 = looking straight at camera). */
  gazeStrength: number;
  /** Eye aspect ratio (vertical/horizontal). ~0.25-0.35 open, <0.12 closed. */
  eyeOpenness: number;
  /** Human library detected an open-hand wave gesture. */
  waveGesture: boolean;
  timestamp: number;
};

export type TrackerStatus = "idle" | "loading" | "running" | "error";

const DETECT_INTERVAL_MS = 100;
const RAD2DEG = 180 / Math.PI;

function computeEyeOpenness(mesh: number[][]): number {
  // MediaPipe FaceMesh indices: vertical lid gap / horizontal eye width.
  if (!mesh || mesh.length < 400) return 0;
  const dist = (a: number[], b: number[]) => Math.hypot(a[0] - b[0], a[1] - b[1]);
  const left = dist(mesh[159], mesh[145]) / Math.max(1e-6, dist(mesh[33], mesh[133]));
  const right = dist(mesh[386], mesh[374]) / Math.max(1e-6, dist(mesh[362], mesh[263]));
  return (left + right) / 2;
}

/**
 * Webcam + Human detection loop. Mount a <video> element and pass its ref.
 * While `active`, emits ~10 readings/sec via `reading` state and `latestRef`.
 */
export function useHumanTracker(active: boolean, videoRef: RefObject<HTMLVideoElement | null>) {
  const [reading, setReading] = useState<FrameReading | null>(null);
  const [status, setStatus] = useState<TrackerStatus>("idle");
  const [error, setError] = useState<string | null>(null);
  const latestRef = useRef<FrameReading | null>(null);

  useEffect(() => {
    if (!active) {
      setStatus("idle");
      setReading(null);
      latestRef.current = null;
      return;
    }

    let cancelled = false;
    let stream: MediaStream | null = null;
    let timer: ReturnType<typeof setTimeout> | null = null;

    const stop = () => {
      if (timer) clearTimeout(timer);
      stream?.getTracks().forEach((t) => t.stop());
      const video = videoRef.current;
      if (video) video.srcObject = null;
    };

    const run = async () => {
      setStatus("loading");
      setError(null);
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          video: { width: 640, height: 480, facingMode: "user" },
          audio: false,
        });
        const video = videoRef.current;
        if (!video) throw new Error("Video element not mounted");
        video.srcObject = stream;
        await video.play();

        const human = await getHuman();
        if (cancelled) return;
        setStatus("running");

        const tick = async () => {
          if (cancelled) return;
          const v = videoRef.current;
          if (v && v.readyState >= 2) {
            try {
              const result = await human.detect(v);
              const face = result.face?.[0];
              const angle = face?.rotation?.angle;
              const gaze = face?.rotation?.gaze;
              const gestures = (result as { gesture?: { gesture?: string }[] }).gesture ?? [];
              const waveGesture = gestures.some(
                (g) => (g.gesture ?? "").toLowerCase().includes("wave"),
              );
              const next: FrameReading = face
                ? {
                    faceDetected: true,
                    yaw: (angle?.yaw ?? 0) * RAD2DEG,
                    pitch: (angle?.pitch ?? 0) * RAD2DEG,
                    roll: (angle?.roll ?? 0) * RAD2DEG,
                    gazeStrength: gaze?.strength ?? 0,
                    eyeOpenness: computeEyeOpenness(face.mesh as unknown as number[][]),
                    waveGesture,
                    timestamp: Date.now(),
                  }
                : {
                    faceDetected: false,
                    yaw: 0,
                    pitch: 0,
                    roll: 0,
                    gazeStrength: 0,
                    eyeOpenness: 0,
                    waveGesture,
                    timestamp: Date.now(),
                  };
              latestRef.current = next;
              if (!cancelled) setReading(next);
            } catch {
              // transient detect failure — keep looping
            }
          }
          timer = setTimeout(() => void tick(), DETECT_INTERVAL_MS);
        };
        void tick();
      } catch (e) {
        if (!cancelled) {
          setStatus("error");
          setError(e instanceof Error ? e.message : "Camera or model init failed");
        }
        stop();
      }
    };

    void run();
    return () => {
      cancelled = true;
      stop();
    };
  }, [active, videoRef]);

  return { reading, latestRef, status, error };
}
