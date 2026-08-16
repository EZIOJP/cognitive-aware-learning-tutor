import { useEffect, useState } from "react";
import { useLocation } from "react-router";
import { postStudyPresence } from "../api/behaviorClient";
import {
  getLectureNotesPresence,
  subscribeLectureNotesPresence,
} from "../utils/lectureNotesPresence";

function isLectureNotesPath(pathname: string): boolean {
  const p = pathname || "/";
  return p === "/lecture-notes" || p.startsWith("/lecture-notes/");
}

function isQuizPath(pathname: string): boolean {
  const p = pathname || "/";
  return p === "/review" || p.startsWith("/review/");
}

function isVocabPath(pathname: string): boolean {
  const p = pathname || "/";
  return p === "/gre-vocab" || p.startsWith("/gre-vocab/");
}

function isMathPath(pathname: string): boolean {
  const p = pathname || "/";
  return p === "/math-tutor" || p.startsWith("/math-tutor/");
}

/** Productive CALT lanes only (Bible / Plan / rest = no SPA productive credit). */
function isProductiveCaltPath(pathname: string): boolean {
  return (
    isLectureNotesPath(pathname) ||
    isQuizPath(pathname) ||
    isVocabPath(pathname) ||
    isMathPath(pathname)
  );
}

function detectClient(): string {
  if (typeof navigator === "undefined") return "web";
  const ua = navigator.userAgent || "";
  if (/iPad/i.test(ua) || (/Macintosh/i.test(ua) && navigator.maxTouchPoints > 1)) return "ipad";
  if (/iPhone|iPod/i.test(ua)) return "ios";
  if (/Android/i.test(ua)) return "android";
  return "web";
}

/**
 * Credit CALT SPA study minutes only on productive lanes while the tab is
 * visible + focused (active tab). Internet sites stay on SelfTracker.
 *
 * Lanes: Lecture Notes (doc open + reading), /review, /gre-vocab, /math-tutor.
 * Bible is spiritual — not credited here.
 */
export function useStudyPresenceHeartbeat(intervalMs = 55_000): void {
  const { pathname } = useLocation();
  const [presenceTick, setPresenceTick] = useState(0);

  useEffect(() => subscribeLectureNotesPresence(() => setPresenceTick((n) => n + 1)), []);

  useEffect(() => {
    if (!isProductiveCaltPath(pathname)) return;

    let cancelled = false;
    const client = detectClient();
    const lecture = isLectureNotesPath(pathname);

    const tick = async () => {
      if (cancelled) return;
      if (typeof document !== "undefined" && document.visibilityState === "hidden") return;
      const focused = typeof document !== "undefined" ? document.hasFocus() : true;
      if (!focused) return;

      let notes_loaded = true;
      let reading = true;
      let document_id: string | undefined;
      let title =
        typeof document !== "undefined" ? document.title : pathname;

      if (lecture) {
        const presence = getLectureNotesPresence();
        if (!presence.notesLoaded || !presence.reading) return;
        notes_loaded = true;
        reading = true;
        document_id = presence.documentId || undefined;
        title = presence.title || title;
      }

      try {
        await postStudyPresence({
          path: pathname,
          focused: true,
          client,
          title,
          notes_loaded,
          reading,
          document_id,
        });
      } catch {
        /* offline / API down */
      }
    };

    void tick();
    const id = window.setInterval(() => void tick(), intervalMs);
    const onVis = () => {
      if (document.visibilityState === "visible") void tick();
    };
    const onFocus = () => void tick();
    document.addEventListener("visibilitychange", onVis);
    window.addEventListener("focus", onFocus);
    return () => {
      cancelled = true;
      window.clearInterval(id);
      document.removeEventListener("visibilitychange", onVis);
      window.removeEventListener("focus", onFocus);
    };
  }, [pathname, intervalMs, presenceTick]);
}
