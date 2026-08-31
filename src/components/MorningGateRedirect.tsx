import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router";
import { BookOpen, CalendarCheck, Sparkles } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { fetchDistractionGate, type MorningGate } from "../api/behaviorClient";
import { ConfirmPlanButton, MORNING_UPDATED_EVENT } from "./productivity/ConfirmPlanButton";

/** Soft-landing for morning.next=plan — Productivity Plan tab. */
export const MORNING_PLAN_PATH = "/productivity?tab=plan";

function pathAllowed(pathname: string, allow: string[] | undefined): boolean {
  if (!allow || allow.includes("*")) return true;
  return allow.some((p) => pathname === p || pathname.startsWith(p + "/"));
}

function onPlanTab(pathname: string, search: string): boolean {
  return pathname === "/productivity" && new URLSearchParams(search).get("tab") === "plan";
}

function rewardLine(morning: MorningGate): string | null {
  const awards = morning.rewards?.awards;
  if (!awards) return null;
  const bits: string[] = [];
  if (awards.bible?.granted) bits.push(awards.bible.label);
  if (awards.plan?.granted) bits.push(awards.plan.label);
  if (morning.next === "bible" && !awards.bible?.granted) {
    bits.push(`Next: Bible +${morning.rewards?.bible_points ?? 10}`);
  } else if (morning.next === "plan" && !awards.plan?.granted) {
    bits.push(`Next: Plan +${morning.rewards?.plan_points ?? 10}`);
  }
  return bits.length ? bits.join(" · ") : null;
}

/**
 * Forces Bible → Confirm plan before the rest of the SPA opens.
 * Separate from desktop game hard-block (same API, nested `morning`).
 */
export function MorningGateRedirect() {
  const { isAuthenticated, sessionReady } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [morning, setMorning] = useState<MorningGate | null>(null);
  const lastNav = useRef<string>("");

  useEffect(() => {
    if (!sessionReady || !isAuthenticated) {
      setMorning(null);
      return;
    }
    let cancelled = false;
    const poll = async () => {
      try {
        const g = await fetchDistractionGate();
        if (!cancelled) setMorning(g.morning ?? null);
      } catch {
        if (!cancelled) setMorning(null);
      }
    };
    void poll();
    const id = window.setInterval(poll, 15000);
    const onVis = () => {
      if (document.visibilityState === "visible") void poll();
    };
    const onMorning = () => void poll();
    document.addEventListener("visibilitychange", onVis);
    window.addEventListener(MORNING_UPDATED_EVENT, onMorning);
    return () => {
      cancelled = true;
      window.clearInterval(id);
      document.removeEventListener("visibilitychange", onVis);
      window.removeEventListener(MORNING_UPDATED_EVENT, onMorning);
    };
  }, [isAuthenticated, sessionReady]);

  useEffect(() => {
    if (!isAuthenticated || !morning?.enabled) return;
    if (morning.next === "open") return;

    if (morning.next === "bible") {
      if (pathAllowed(location.pathname, morning.allow_paths)) return;
      const target = "/bible";
      if (lastNav.current === target && location.pathname === "/bible") return;
      lastNav.current = target;
      navigate(target, { replace: true });
      return;
    }

    // morning.next === "plan" — land on Plan tab; Bible/profile still allowed.
    if (
      location.pathname === "/bible" ||
      location.pathname.startsWith("/bible/") ||
      location.pathname === "/profile"
    ) {
      return;
    }
    if (onPlanTab(location.pathname, location.search)) return;
    const target = MORNING_PLAN_PATH;
    if (lastNav.current === target && onPlanTab(location.pathname, location.search)) return;
    lastNav.current = target;
    navigate(target, { replace: true });
  }, [isAuthenticated, morning, location.pathname, location.search, navigate]);

  if (!isAuthenticated || !morning?.enabled || morning.next === "open") {
    return null;
  }

  const rewards = rewardLine(morning);

  return (
    <div className="fixed bottom-3 left-1/2 z-[60] -translate-x-1/2 max-w-md w-[min(92vw,28rem)] rounded-xl border border-amber-500/40 bg-amber-950/95 text-amber-50 shadow-lg px-4 py-3 flex gap-3 items-start">
      {morning.next === "bible" ? (
        <BookOpen className="size-5 shrink-0 mt-0.5 text-amber-300" />
      ) : (
        <CalendarCheck className="size-5 shrink-0 mt-0.5 text-amber-300" />
      )}
      <div className="min-w-0 text-sm">
        <p className="font-semibold text-amber-100">
          {morning.next === "bible"
            ? "Morning: Bible chapter first (+10)"
            : "Morning: confirm today’s plan when ready (+10)"}
        </p>
        <p className="text-[12px] text-amber-100/80 mt-0.5 leading-snug">
          {morning.hint ||
            (morning.next === "bible"
              ? "Finish today’s chapter in the Bible reader (web or CALT Desktop → Bible) to continue."
              : `Edit goals & blocks anytime, then tap Confirm (${morning.blocks_today} block${morning.blocks_today === 1 ? "" : "s"} today) — or confirm in CALT Desktop → Plan.`)}
        </p>
        {rewards && (
          <p className="text-[11px] text-emerald-200/90 mt-1.5 flex items-center gap-1">
            <Sparkles className="size-3.5 shrink-0" />
            {rewards}
            {typeof morning.rewards?.total_points === "number" && morning.rewards.total_points > 0
              ? ` · ${morning.rewards.total_points} pts today`
              : ""}
          </p>
        )}
        {morning.next === "plan" && !morning.plan_done ? (
          <div className="mt-2">
            <ConfirmPlanButton
              size="banner"
              onDone={() =>
                void fetchDistractionGate().then((g) => setMorning(g.morning ?? null))
              }
            />
          </div>
        ) : null}
      </div>
    </div>
  );
}
