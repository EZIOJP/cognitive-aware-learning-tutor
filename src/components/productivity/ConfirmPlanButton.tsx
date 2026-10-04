import { useCallback, useEffect, useState } from "react";
import { CheckCircle2, Loader2 } from "lucide-react";
import { confirmMorningPlan, fetchDistractionGate } from "../../api/behaviorClient";
import { requestBibleDayPass, requestRewardDay } from "../../api/bibleClient";
import { confirmPlanNative, fetchDayLoopSnapshot } from "../../api/dayLoopClient";
import { isFocusDesktopShell } from "../../utils/focusDesktopShell";
import { isFocusEnforcerBridgeAvailable } from "../../lib/enforcerNativeCmd";
import { subscribeFocusStatus } from "../../lib/focusStatusBus";
import {
  formatGoalsForPrompt,
  loadProductivityGoals,
} from "./ProductivityGoalsPanel";

export const MORNING_UPDATED_EVENT = "calt-morning-updated";

function goalsPayload(): string {
  try {
    const text = formatGoalsForPrompt(loadProductivityGoals()).trim();
    return text.length >= 3 ? text : "Focus today";
  } catch {
    return "Focus today";
  }
}

type Props = {
  size?: "banner" | "block";
  onDone?: () => void;
  /** When false, Confirm stays disabled (empty day — need a non-free block first). */
  requirePlannedMinutes?: boolean;
};

export function ConfirmPlanButton({
  size = "block",
  onDone,
  requirePlannedMinutes = true,
}: Props) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [planDone, setPlanDone] = useState(false);
  const [bibleDone, setBibleDone] = useState(true);
  const [enabled, setEnabled] = useState(true);
  const [next, setNext] = useState<string | null>(null);
  const [plannedMinutes, setPlannedMinutes] = useState(0);
  const focusShell = isFocusDesktopShell();

  const applyLoop = useCallback(
    (loop: {
      plan_confirmed?: boolean;
      bible_done?: boolean;
      planned_minutes?: number;
    }) => {
      setEnabled(true);
      setPlanDone(Boolean(loop.plan_confirmed));
      setBibleDone(Boolean(loop.bible_done));
      setPlannedMinutes(Math.max(0, Math.floor(loop.planned_minutes ?? 0)));
      setNext(!loop.bible_done ? "bible" : !loop.plan_confirmed ? "plan" : "open");
    },
    [],
  );

  const refresh = useCallback(async () => {
    try {
      if (focusShell && isFocusEnforcerBridgeAvailable()) {
        // After confirm/mutations only — cold start reads the shared status bus.
        const loop = await fetchDayLoopSnapshot();
        if (loop) {
          applyLoop(loop);
          return;
        }
      }
      const g = await fetchDistractionGate();
      const m = g.morning;
      setEnabled(Boolean(m?.enabled));
      setPlanDone(Boolean(m?.plan_done));
      setBibleDone(Boolean(m?.bible_done));
      setNext(m?.next ?? null);
    } catch {
      /* keep last */
    }
  }, [focusShell, applyLoop]);

  useEffect(() => {
    if (focusShell) {
      return subscribeFocusStatus((snap) => {
        if (snap.dayLoop) applyLoop(snap.dayLoop);
      });
    }
    void refresh();
  }, [focusShell, refresh, applyLoop]);

  const finish = useCallback(async () => {
    setPlanDone(true);
    await refresh();
    window.dispatchEvent(new Event(MORNING_UPDATED_EVENT));
    onDone?.();
  }, [onDone, refresh]);

  const planReady = !focusShell || plannedMinutes > 0;
  const confirmAllowed = requirePlannedMinutes ? planReady : true;

  const runConfirm = useCallback(async () => {
    if (!confirmAllowed) {
      setError("Add at least one non-free plan block for today, then Confirm.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      if (focusShell && isFocusEnforcerBridgeAvailable()) {
        const r = await confirmPlanNative();
        if (!r.ok) {
          const err = r.error || "Native confirm failed";
          if (err === "bible_required") throw new Error("Finish Bible first, then Confirm.");
          if (err === "plan_required")
            throw new Error("Add at least one non-free plan block for today, then Confirm.");
          throw new Error(err);
        }
      } else {
        await confirmMorningPlan({ goals: goalsPayload() });
      }
      await finish();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Confirm failed");
    } finally {
      setBusy(false);
    }
  }, [finish, focusShell, confirmAllowed]);

  const runReward = useCallback(async () => {
    const ok = window.prompt("Claim a reward day? Type REWARD:");
    if (ok == null) return;
    setBusy(true);
    setError(null);
    try {
      await requestRewardDay(ok);
      await finish();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Reward claim failed");
    } finally {
      setBusy(false);
    }
  }, [finish]);

  const runPass = useCallback(async () => {
    const ok = window.prompt("Use one day pass? Type PASS:");
    if (ok == null) return;
    setBusy(true);
    setError(null);
    try {
      await requestBibleDayPass(ok);
      await finish();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Day pass failed");
    } finally {
      setBusy(false);
    }
  }, [finish]);

  if (!enabled || next === "bible" || !bibleDone) {
    return null;
  }

  if (planDone) {
    return (
      <p className="inline-flex items-center gap-1.5 text-sm text-emerald-200">
        <CheckCircle2 className="size-4 shrink-0" />
        Plan confirmed — SoftLand + Arm on for study
      </p>
    );
  }

  const wide = size === "banner";
  return (
    <div className={wide ? "shrink-0 space-y-2" : "w-full space-y-3"}>
      <button
        type="button"
        disabled={busy || !confirmAllowed}
        onClick={() => void runConfirm()}
        className={
          wide
            ? "rounded-lg bg-amber-400 px-3 py-2 text-sm font-semibold text-amber-950 hover:bg-amber-300 disabled:opacity-45"
            : "w-full rounded-lg bg-amber-400 px-4 py-3.5 text-[15px] font-semibold text-amber-950 transition-colors hover:bg-amber-300 disabled:opacity-45"
        }
      >
        {busy ? (
          <span className="inline-flex items-center justify-center gap-2">
            <Loader2 className="size-4 animate-spin" />
            Starting day…
          </span>
        ) : !confirmAllowed ? (
          "Confirm (needs a plan block)"
        ) : (
          "Confirm plan — SoftLand + Arm"
        )}
      </button>
      {focusShell ? (
        <div className="flex items-center justify-center gap-4">
          <button
            type="button"
            disabled={busy}
            onClick={() => void runReward()}
            className="text-xs text-white/50 underline-offset-4 hover:text-white/80 hover:underline disabled:opacity-50"
          >
            Free day
          </button>
          <span className="text-white/20" aria-hidden>
            ·
          </span>
          <button
            type="button"
            disabled={busy}
            onClick={() => void runPass()}
            className="text-xs text-white/50 underline-offset-4 hover:text-white/80 hover:underline disabled:opacity-50"
          >
            Day pass
          </button>
        </div>
      ) : null}
      {!wide ? (
        <p className="text-center text-[11px] leading-relaxed text-white/40">
          Focus until today&apos;s goal, then free until midnight — or claim a free day / pass above.
        </p>
      ) : null}
      {error ? <p className="text-center text-[11px] text-rose-200">{error}</p> : null}
    </div>
  );
}
