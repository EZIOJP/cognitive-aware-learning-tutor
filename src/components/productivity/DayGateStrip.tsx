/**
 * Compact morning status — Bible / Plan / SoftLand / Arm — not a full-screen trap.
 * Plan + Calendar stay reachable while SoftLand host gate may still block sites.
 */
import { Link } from "react-router";
import { BookOpen, CalendarDays, Shield, Sparkles } from "lucide-react";
import { useFocusStatus, useFreeDay } from "../../hooks/useFocusStatus";
import {
  bibleDoneToday,
  morningLockActive,
  planConfirmedToday,
  planningEnabled,
} from "../../lib/dayGate";
import { isFocusDesktopShell } from "../../utils/focusDesktopShell";

function Chip({
  ok,
  label,
  hint,
}: {
  ok: boolean;
  label: string;
  hint: string;
}) {
  return (
    <span
      title={hint}
      className={
        "inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[11px] font-medium " +
        (ok
          ? "bg-emerald-500/15 text-emerald-200 ring-1 ring-emerald-400/30"
          : "bg-amber-500/15 text-amber-100 ring-1 ring-amber-400/35")
      }
    >
      <span
        className={
          "size-1.5 rounded-full " + (ok ? "bg-emerald-300" : "bg-amber-300 animate-pulse")
        }
      />
      {label}
    </span>
  );
}

export default function DayGateStrip() {
  const focus = isFocusDesktopShell();
  const status = useFocusStatus();
  const freeDay = useFreeDay();

  if (!focus) return null;
  if (status.dayLoop?.bedtime_active) return null;
  if (!status.dayLoop && !status.softland?.goals) return null;

  const bible = bibleDoneToday(status);
  const planning = planningEnabled(status);
  const planOk = !planning || planConfirmedToday(status);
  const lock = morningLockActive(status);
  const softlandOn = Boolean(status.softland?.softland_enabled);
  const armed = Boolean(status.enforcerStatus?.armed ?? status.softland?.hard_block_armed);

  if (!lock && bible && planOk) return null;

  return (
    <div
      className="sticky top-0 z-[120] border-b border-white/10 px-3 py-2.5 backdrop-blur-md"
      style={{
        background: "linear-gradient(180deg, rgba(18,22,14,0.94), rgba(12,14,10,0.88))",
      }}
    >
      <div className="mx-auto flex max-w-5xl flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-wrap items-center gap-1.5">
          <Chip
            ok={bible}
            label={bible ? "Bible done" : "Bible pending"}
            hint="Morning chapter — SoftLand holds hosts until done"
          />
          <Chip
            ok={planOk}
            label={
              !planning
                ? "Planning off"
                : planConfirmedToday(status)
                  ? "Plan confirmed"
                  : "Confirm plan"
            }
            hint={
              planning
                ? "Confirm couples SoftLand + Arm (SoftLand ≠ Arm until then)"
                : "Session-first — work sessions & routines without Confirm"
            }
          />
          <Chip
            ok={softlandOn}
            label={softlandOn ? "SoftLand on" : "SoftLand off"}
            hint="Host gate — not the same as Arm"
          />
          <Chip
            ok={!armed}
            label={armed ? "Arm on" : "Arm off"}
            hint={freeDay ? "Free day / pass open" : "Arm changes need free day or day pass"}
          />
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {!bible ? (
            <Link
              to="/bible"
              className="inline-flex items-center gap-1.5 rounded-lg bg-amber-300 px-3 py-1.5 text-xs font-semibold text-amber-950 hover:bg-amber-200"
            >
              <BookOpen className="size-3.5" />
              Open Bible
            </Link>
          ) : null}
          {planning && !planConfirmedToday(status) ? (
            <Link
              to="/productivity?tab=plan"
              className="inline-flex items-center gap-1.5 rounded-lg bg-sky-300 px-3 py-1.5 text-xs font-semibold text-sky-950 hover:bg-sky-200"
            >
              <CalendarDays className="size-3.5" />
              Edit Plan
            </Link>
          ) : null}
          <Link
            to="/productivity"
            className="inline-flex items-center gap-1.5 rounded-lg border border-white/15 px-3 py-1.5 text-xs font-medium text-white/80 hover:bg-white/5"
          >
            <Sparkles className="size-3.5" />
            Home
          </Link>
          <span className="hidden items-center gap-1 text-[10px] text-white/40 sm:inline-flex">
            <Shield className="size-3" />
            Plan & routines stay editable
          </span>
        </div>
      </div>
    </div>
  );
}
