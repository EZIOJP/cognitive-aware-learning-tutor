/**
 * Always-on sit/stand + eye-rest timers for Focus (panel only edits prefs).
 */
import { useEffect, useRef } from "react";
import { loadBodyCarePrefs } from "../../lib/bodyCarePrefs";

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
      const seatedMs = now - lastInputRef.current;

      if (p.sitStandEnabled) {
        const limit = p.sitMinutes * 60_000;
        if (seatedMs >= limit && now - lastSitNotifyRef.current > 5 * 60_000) {
          lastSitNotifyRef.current = now;
          notify(
            "CALT — stand up",
            `Still ~${p.sitMinutes} min. Stand ${p.standMinutes} min, then sit.`,
          );
          lastInputRef.current = now;
        }
      }

      if (p.eyeRestEnabled) {
        const elapsed = now - lastEyeNotifyRef.current;
        if (elapsed >= p.eyeRestMinutes * 60_000) {
          lastEyeNotifyRef.current = now;
          notify(
            "CALT — eye rest",
            `Look away ${p.eyeRestSeconds}s (20–20–20).`,
          );
        }
      }
    }, 20_000);
    return () => window.clearInterval(id);
  }, []);

  return null;
}

export default BodyCareRuntime;
