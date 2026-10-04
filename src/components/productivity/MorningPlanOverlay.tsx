import { Loader2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router";
import { applyRoutines, createPlannerBlock } from "../../api/plannerClient";
import { isFocusDesktopShell } from "../../utils/focusDesktopShell";
import { useFocusStatus } from "../../hooks/useFocusStatus";
import { invalidateFocusStatusBus } from "../../lib/focusStatusBus";
import { ConfirmPlanButton, MORNING_UPDATED_EVENT } from "./ConfirmPlanButton";

function localYmd(): string {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function localIso(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}:00`;
}

function bibleDoneToday(status: ReturnType<typeof useFocusStatus>): boolean {
  if (status.dayLoop?.bible_done) return true;
  const goals = status.softland?.goals;
  if (!goals?.bible_done) return false;
  const date = typeof goals.bible_done_for_date === "string" ? goals.bible_done_for_date : "";
  return date === localYmd();
}

function planConfirmedToday(status: ReturnType<typeof useFocusStatus>): boolean {
  if (status.dayLoop?.plan_confirmed) return true;
  const goals = status.softland?.goals;
  if (!goals?.plan_confirmed) return false;
  const date =
    typeof goals.plan_confirmed_for_date === "string" ? goals.plan_confirmed_for_date : "";
  return date === localYmd();
}

/**
 * After Bible: force Confirm plan before the rest of the day.
 * Plan tab stays reachable so you can edit blocks first.
 */
export default function MorningPlanOverlay() {
  const focus = isFocusDesktopShell();
  const status = useFocusStatus();
  const location = useLocation();
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const [hint, setHint] = useState<string | null>(null);

  const planned = Math.max(0, Math.floor(status.dayLoop?.planned_minutes ?? 0));
  const canConfirm = planned > 0;

  useEffect(() => {
    if (!focus) return;
    const kick = () => invalidateFocusStatusBus({ pipe: false });
    kick();
    const onMorning = () => invalidateFocusStatusBus({ pipe: true });
    window.addEventListener(MORNING_UPDATED_EVENT, onMorning);
    return () => window.removeEventListener(MORNING_UPDATED_EVENT, onMorning);
  }, [focus]);

  const refreshPipe = useCallback(() => {
    invalidateFocusStatusBus({ pipe: true });
    window.dispatchEvent(new Event(MORNING_UPDATED_EVENT));
  }, []);

  const addFocusBlock = useCallback(async () => {
    setBusy(true);
    setHint(null);
    try {
      const start = new Date();
      start.setSeconds(0, 0);
      await createPlannerBlock({
        title: "Focus block",
        category: "study",
        start_at: localIso(start),
        duration_minutes: 60,
      });
      setHint("60m Focus block added — Confirm when ready.");
      refreshPipe();
    } catch (e) {
      setHint(e instanceof Error ? e.message : "Could not add block");
    } finally {
      setBusy(false);
    }
  }, [refreshPipe]);

  const applyTodayRoutines = useCallback(async () => {
    setBusy(true);
    setHint(null);
    try {
      const r = await applyRoutines(localYmd());
      setHint(
        r.created > 0
          ? `Applied ${r.created} routine block${r.created === 1 ? "" : "s"}.`
          : "No new routine blocks.",
      );
      refreshPipe();
    } catch (e) {
      setHint(e instanceof Error ? e.message : "Could not apply routines");
    } finally {
      setBusy(false);
    }
  }, [refreshPipe]);

  if (!focus) return null;
  if (status.dayLoop?.bedtime_active) return null;
  if (!bibleDoneToday(status)) return null;
  if (planConfirmedToday(status)) return null;
  if (!status.dayLoop && !status.softland?.goals) return null;

  const path = `${location.pathname || ""}${location.search || ""}`.toLowerCase();
  if (path.includes("tab=plan") || path.includes("/bible")) return null;

  return (
    <div
      className="fixed inset-0 z-[185] flex items-center justify-center px-6 py-10"
      style={{
        background:
          "radial-gradient(ellipse 90% 70% at 50% 0%, #1c2836 0%, #0c1218 55%, #06080b 100%)",
      }}
    >
      <div className="flex w-full max-w-md flex-col items-stretch text-left">
        <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-sky-200/45">
          CALT Focus
        </p>
        <h1 className="mt-3 text-[2rem] font-semibold leading-tight tracking-tight text-sky-50">
          Confirm today&apos;s plan
        </h1>
        <p className="mt-3 text-[15px] leading-relaxed text-sky-100/65">
          Bible is done. SoftLand holds the morning gate; Arm stays off until you Confirm.
        </p>

        <div className="mt-8 border-y border-white/10 py-5 text-center">
          <p className="text-[11px] uppercase tracking-[0.14em] text-sky-200/40">
            Non-free plan today
          </p>
          <p
            className={`mt-1 text-4xl font-semibold tabular-nums tracking-tight ${
              canConfirm ? "text-emerald-300" : "text-sky-50"
            }`}
          >
            {planned}
            <span className="ml-2 text-base font-medium text-sky-100/45">min</span>
          </p>
          <p className="mt-2 text-sm text-sky-100/55">
            {canConfirm
              ? "Ready — Confirm starts SoftLand + Arm."
              : "Add a study, work, or spiritual block (not food/break)."}
          </p>
        </div>

        {!canConfirm ? (
          <div className="mt-6 flex flex-col gap-2">
            <button
              type="button"
              disabled={busy}
              className="w-full rounded-lg bg-sky-300 px-4 py-3 text-sm font-semibold text-sky-950 transition-colors hover:bg-sky-200 disabled:opacity-50"
              onClick={() => void addFocusBlock()}
            >
              {busy ? (
                <span className="inline-flex items-center justify-center gap-2">
                  <Loader2 className="size-4 animate-spin" />
                  Adding…
                </span>
              ) : (
                "Add 60m Focus block"
              )}
            </button>
            <div className="flex items-center justify-between gap-3 pt-1">
              <button
                type="button"
                disabled={busy}
                className="text-sm text-sky-100/70 underline-offset-4 transition-colors hover:text-sky-50 hover:underline disabled:opacity-50"
                onClick={() => void applyTodayRoutines()}
              >
                Apply routines
              </button>
              <button
                type="button"
                className="text-sm text-sky-100/70 underline-offset-4 transition-colors hover:text-sky-50 hover:underline"
                onClick={() => navigate("/productivity?tab=plan", { replace: true })}
              >
                Open Plan
              </button>
            </div>
          </div>
        ) : (
          <div className="mt-6">
            <button
              type="button"
              className="text-sm text-sky-100/70 underline-offset-4 transition-colors hover:text-sky-50 hover:underline"
              onClick={() => navigate("/productivity?tab=plan", { replace: true })}
            >
              Edit in Plan
            </button>
          </div>
        )}

        <div className="mt-6">
          <ConfirmPlanButton size="block" />
        </div>

        {hint ? <p className="mt-3 text-sm text-sky-100/70">{hint}</p> : null}
      </div>
    </div>
  );
}
