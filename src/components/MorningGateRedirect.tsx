import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router";
import { useAuth } from "../context/AuthContext";
import { fetchDistractionGate, type MorningGate } from "../api/behaviorClient";
import { MORNING_UPDATED_EVENT } from "./productivity/ConfirmPlanButton";
import { isFocusDesktopShell } from "../utils/focusDesktopShell";

/** Soft-landing for morning.next=plan — Productivity Plan tab (server default). */
export const MORNING_PLAN_PATH = "/productivity?tab=plan";

const GATE_BC = "calt-morning-gate";
const HEARTBEAT_MS = 5 * 60 * 1000;

/**
 * Gate APIs return absolute SPA URLs for the desktop tracker (open Edge).
 * React Router navigate() must get a path — absolute http(s) URLs become
 * broken relative paths like /http:/localhost:5173/bible.
 */
export function spaNavigateTarget(raw: string | null | undefined, fallback = "/"): string {
  const value = (raw || "").trim();
  if (!value) return fallback;
  if (value.startsWith("/")) return value;
  try {
    const u = new URL(value);
    if (u.protocol === "http:" || u.protocol === "https:") {
      return `${u.pathname}${u.search}${u.hash}` || fallback;
    }
  } catch {
    /* not a URL */
  }
  // Already a path missing leading slash, or opaque string — best effort.
  if (value.includes("://")) return fallback;
  return value.startsWith("/") ? value : `/${value}`;
}

function pathAllowed(pathname: string, allow: string[] | undefined): boolean {
  if (!allow || allow.includes("*")) return true;
  return allow.some((p) => {
    const pathOnly = spaNavigateTarget(p).split("?")[0] || p;
    return pathname === pathOnly || pathname.startsWith(pathOnly + "/");
  });
}

function defaultRedirect(morning: MorningGate): string {
  if (morning.redirect_url) return spaNavigateTarget(morning.redirect_url, "/bible");
  if (morning.next === "bible") return spaNavigateTarget(morning.bible_url, "/bible");
  if (morning.next === "plan") return spaNavigateTarget(morning.plan_url, MORNING_PLAN_PATH);
  if (morning.next === "study") return "/review?tab=loop";
  return "/bible";
}

/**
 * Soft redirect from server morning gate — trusts allow_paths + redirect_url.
 * One BroadcastChannel leader polls every 5 min; others consume; pause when hidden.
 * Rule changes still arrive via MORNING_UPDATED_EVENT (immediate).
 */
export function MorningGateRedirect() {
  const { isAuthenticated, sessionReady } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [morning, setMorning] = useState<MorningGate | null>(null);
  const lastNav = useRef<string>("");
  const isLeader = useRef(false);
  const focusShell = isFocusDesktopShell();

  useEffect(() => {
    // Focus desktop shell is Productivity-only — never soft-redirect to Bible/Study (blank shell).
    if (focusShell || !sessionReady || !isAuthenticated) {
      setMorning(null);
      return;
    }
    let cancelled = false;
    let intervalId = 0;
    const bc =
      typeof BroadcastChannel !== "undefined" ? new BroadcastChannel(GATE_BC) : null;

    const applyMorning = (m: MorningGate | null) => {
      if (!cancelled) setMorning(m);
    };

    const poll = async () => {
      try {
        const g = await fetchDistractionGate();
        const m = g.morning ?? null;
        applyMorning(m);
        bc?.postMessage({ type: "morning", morning: m });
      } catch {
        if (!cancelled) setMorning(null);
      }
    };

    const becomeLeader = () => {
      isLeader.current = true;
      void poll();
      window.clearInterval(intervalId);
      intervalId = window.setInterval(() => {
        if (document.visibilityState === "visible") void poll();
      }, HEARTBEAT_MS);
    };

    // First tab to open claims leadership; others follow BroadcastChannel.
    const claim = window.setTimeout(() => {
      if (!cancelled && !isLeader.current) becomeLeader();
    }, 50 + Math.floor(Math.random() * 200));

    bc?.addEventListener("message", (ev) => {
      const data = ev.data;
      if (data?.type === "morning") {
        applyMorning(data.morning ?? null);
      } else if (data?.type === "leader-here") {
        isLeader.current = false;
        window.clearInterval(intervalId);
      }
    });
    bc?.postMessage({ type: "leader-here" });

    const onVis = () => {
      if (document.visibilityState === "visible" && isLeader.current) void poll();
    };
    const onMorning = () => void poll();
    document.addEventListener("visibilitychange", onVis);
    window.addEventListener(MORNING_UPDATED_EVENT, onMorning);

    return () => {
      cancelled = true;
      window.clearTimeout(claim);
      window.clearInterval(intervalId);
      document.removeEventListener("visibilitychange", onVis);
      window.removeEventListener(MORNING_UPDATED_EVENT, onMorning);
      bc?.close();
    };
  }, [isAuthenticated, sessionReady, focusShell]);

  useEffect(() => {
    if (focusShell || !isAuthenticated || !morning?.enabled) return;
    if (morning.next === "open") return;
    if (pathAllowed(location.pathname, morning.allow_paths)) return;

    const target = defaultRedirect(morning);
    const targetPath = target.split("?")[0] || target;
    if (lastNav.current === target && location.pathname === targetPath) return;
    lastNav.current = target;
    navigate(target, { replace: true });
  }, [focusShell, isAuthenticated, morning, location.pathname, location.search, navigate]);

  return null;
}
