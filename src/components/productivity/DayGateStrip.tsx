/**
 * Dynamic hard-gate top bar — shows while Bible / Confirm lock is active.
 * Enforcer chip uses status-bus mirrors (no stampede pipe probes).
 * SoftLand ≠ Arm. Bible → Plan → Confirm.
 */
import { useEffect } from "react";
import { Link, useLocation } from "react-router";
import { BookOpen, CalendarDays, Shield } from "lucide-react";
import { useFocusStatus } from "../../hooks/useFocusStatus";
import { invalidateFocusStatusBus } from "../../lib/focusStatusBus";
import {
  bibleDoneToday,
  dueBibleSlot,
  morningLockActive,
  planConfirmedToday,
} from "../../lib/dayGate";
import { isFocusDesktopShell } from "../../utils/focusDesktopShell";
import { PlanningPrefsGearButton } from "./PlanningPrefsSheet";
import { useEnforcerReachability } from "./EnforcerWriteGate";
import { cn } from "../../app/components/ui/utils";

function routeBlob(pathname: string, search: string, hash: string): string {
  return `${pathname || ""}${search || ""}${hash || ""}`.toLowerCase();
}

function Stage({
  label,
  state,
}: {
  label: string;
  state: "done" | "active" | "soon";
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center justify-center gap-1.5 rounded-full px-3 py-1 text-[11px] font-semibold tracking-wide min-w-[5.5rem]",
        state === "done" && "bg-emerald-500/15 text-emerald-200 ring-1 ring-emerald-400/25",
        state === "active" && "bg-amber-400/20 text-amber-50 ring-1 ring-amber-300/45",
        state === "soon" && "bg-white/5 text-muted-foreground ring-1 ring-white/10",
      )}
    >
      <span
        className={cn(
          "size-1.5 rounded-full",
          state === "done" && "bg-emerald-300",
          state === "active" && "bg-amber-300 animate-pulse",
          state === "soon" && "bg-white/25",
        )}
        aria-hidden
      />
      {label}
    </span>
  );
}

function EnforcerChip({
  reach,
}: {
  reach: ReturnType<typeof useEnforcerReachability>;
}) {
  const label =
    reach === "ok"
      ? "Enforcer live"
      : reach === "down"
        ? "Enforcer down"
        : reach === "no_bridge"
          ? "No bridge"
          : "Enforcer…";
  const tone =
    reach === "ok"
      ? "text-[#9FCB8A] ring-[#9FCB8A]/35 bg-[#9FCB8A]/10"
      : reach === "unknown"
        ? "text-muted-foreground ring-white/15 bg-white/5"
        : "text-amber-100 ring-amber-400/40 bg-amber-500/15";

  return (
    <span
      title={
        reach === "ok"
          ? "Named pipe + SoftLand/Arm SoT responding"
          : reach === "down"
            ? "calt_enforcer unreachable — mark-done / Confirm will fail until it is up"
            : reach === "no_bridge"
              ? "Open calt_focus.exe (not a normal browser) for the enforcer bridge"
              : "Checking enforcer pipe…"
      }
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-semibold ring-1",
        tone,
      )}
    >
      <Shield className="size-3.5 opacity-80" aria-hidden />
      {label}
    </span>
  );
}

export default function DayGateStrip() {
  const focus = isFocusDesktopShell();
  const status = useFocusStatus();
  const location = useLocation();
  const reach = useEnforcerReachability();

  useEffect(() => {
    if (!focus) return;
    // Mirrors only — forced pipe probes here caused live/down flicker during Bible/Plan.
    invalidateFocusStatusBus({ pipe: false });
    const id = window.setInterval(() => invalidateFocusStatusBus({ pipe: false }), 15_000);
    return () => window.clearInterval(id);
  }, [focus]);

  if (!focus) return null;
  if (status.dayLoop?.bedtime_active) return null;
  if (!status.dayLoop && !status.softland?.goals) return null;
  if (!morningLockActive(status)) return null;

  const due = dueBibleSlot(status);
  const planOk = planConfirmedToday(status);
  const bible = bibleDoneToday(status);
  const blob = routeBlob(location.pathname, location.search, location.hash);
  const onBible = blob.includes("/bible") || blob.includes("#/bible");
  const onPlan = blob.includes("tab=plan");
  const onDueSurface = Boolean((due && onBible) || (!due && !planOk && onPlan));

  const bibleState: "done" | "active" | "soon" = bible && !due ? "done" : due ? "active" : "soon";
  const planState: "done" | "active" | "soon" = planOk ? "done" : !due ? "active" : "soon";
  const confirmState: "done" | "active" | "soon" = planOk
    ? "done"
    : planState === "active"
      ? "active"
      : "soon";

  const slotLabel =
    due === "morning"
      ? "Morning chapter"
      : due === "afternoon"
        ? "Afternoon chapter"
        : due === "evening"
          ? "Evening chapter"
          : null;

  const headline = onDueSurface
    ? due && onBible
      ? `Hard gate · ${slotLabel} in progress`
      : "Hard gate · Confirm plan"
    : due
      ? `Hard gate · ${slotLabel} required`
      : "Hard gate · Confirm plan required";

  const sub =
    reach === "ok"
      ? onDueSurface
        ? "SoftLand holds distraction sites until this step clears."
        : "Enforcer is up — finish the active stage to open the day."
      : reach === "down" || reach === "no_bridge"
        ? "Enforcer is not reachable — SoftLand/Arm writes and mark-done will not stick."
        : "Checking enforcer…";

  return (
    <div
      className="shrink-0 z-[120] border-b border-[color:var(--focus-line,rgba(240,238,232,0.1))] px-4 py-3 sm:px-6"
      style={{
        background:
          reach === "ok"
            ? "color-mix(in srgb, var(--focus-ink-lift, #181714) 88%, var(--focus-teal, #0d7a70))"
            : "color-mix(in srgb, var(--focus-ink-lift, #181714) 80%, #7a3b12)",
      }}
      role="status"
      aria-live="polite"
    >
      <div className="mx-auto grid w-full max-w-5xl gap-3 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)_auto] lg:items-center">
        <div className="min-w-0 space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center gap-1.5 text-[13px] font-semibold text-[color:var(--focus-paper,#f0eee8)]">
              <span className="size-1.5 rounded-full bg-amber-300 animate-pulse" aria-hidden />
              {headline}
            </span>
            <EnforcerChip reach={reach} />
          </div>
          <p className="text-[12px] text-muted-foreground leading-snug">{sub}</p>
        </div>

        <div className="flex flex-wrap items-center justify-center gap-2 lg:justify-evenly">
          <Stage label="Bible" state={bibleState} />
          <span className="hidden text-[11px] text-muted-foreground sm:inline" aria-hidden>
            →
          </span>
          <Stage label="Plan" state={planState} />
          <span className="hidden text-[11px] text-muted-foreground sm:inline" aria-hidden>
            →
          </span>
          <Stage label="Confirm" state={confirmState} />
        </div>

        <div className="flex shrink-0 flex-wrap items-center justify-end gap-2">
          {!due && !planOk ? <PlanningPrefsGearButton /> : null}
          {!onDueSurface && due ? (
            <Link
              to={`/bible?slot=${due}`}
              className="inline-flex min-h-9 items-center gap-1.5 rounded-lg bg-[color:var(--focus-teal,#0d7a70)] px-3.5 text-[12px] font-semibold text-[#f5fffd] hover:brightness-110"
            >
              <BookOpen className="size-3.5" />
              Open Bible
            </Link>
          ) : null}
          {!onDueSurface && !due && !planOk ? (
            <Link
              to="/productivity?tab=plan"
              className="inline-flex min-h-9 items-center gap-1.5 rounded-lg bg-[color:var(--focus-teal,#0d7a70)] px-3.5 text-[12px] font-semibold text-[#f5fffd] hover:brightness-110"
            >
              <CalendarDays className="size-3.5" />
              Finish plan
            </Link>
          ) : null}
          {onDueSurface && due && onBible ? (
            <span className="text-[12px] text-[color:var(--focus-teal-bright,#8fd6cc)]">
              Mark chapter done to advance
            </span>
          ) : null}
          {onDueSurface && !due && onPlan ? (
            <span className="text-[12px] text-[color:var(--focus-teal-bright,#8fd6cc)]">
              Apply / Confirm to unlock SoftLand
            </span>
          ) : null}
        </div>
      </div>
    </div>
  );
}
