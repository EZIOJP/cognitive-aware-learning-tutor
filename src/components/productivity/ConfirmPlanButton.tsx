import { useCallback, useEffect, useState } from "react";
import { CheckCircle2, Loader2 } from "lucide-react";
import { confirmMorningPlan, fetchDistractionGate } from "../../api/behaviorClient";
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
};

export function ConfirmPlanButton({ size = "block", onDone }: Props) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [planDone, setPlanDone] = useState(false);
  const [bibleDone, setBibleDone] = useState(true);
  const [enabled, setEnabled] = useState(true);
  const [next, setNext] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const g = await fetchDistractionGate();
      const m = g.morning;
      setEnabled(Boolean(m?.enabled));
      setPlanDone(Boolean(m?.plan_done));
      setBibleDone(Boolean(m?.bible_done));
      setNext(m?.next ?? null);
    } catch {
      /* keep last */
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const run = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const r = await confirmMorningPlan({ goals: goalsPayload() });
      setPlanDone(Boolean(r.morning?.plan_done) || true);
      await refresh();
      window.dispatchEvent(new Event(MORNING_UPDATED_EVENT));
      onDone?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Confirm failed");
    } finally {
      setBusy(false);
    }
  }, [onDone, refresh]);

  if (!enabled || next === "bible" || !bibleDone) {
    return null;
  }

  if (planDone) {
    return (
      <p className="inline-flex items-center gap-1.5 text-sm text-emerald-200">
        <CheckCircle2 className="size-4 shrink-0" />
        Plan confirmed
      </p>
    );
  }

  const wide = size === "banner";
  return (
    <div className={wide ? "shrink-0" : "space-y-1 w-full"}>
      <button
        type="button"
        disabled={busy}
        onClick={() => void run()}
        className={
          wide
            ? "rounded-lg bg-amber-400 px-3 py-2 text-sm font-semibold text-amber-950 hover:bg-amber-300 disabled:opacity-50"
            : "w-full rounded-xl bg-amber-400 px-4 py-3 text-base font-semibold text-amber-950 hover:bg-amber-300 disabled:opacity-50"
        }
      >
        {busy ? (
          <span className="inline-flex items-center gap-2">
            <Loader2 className="size-4 animate-spin" />
            Confirming…
          </span>
        ) : (
          "Confirm plan"
        )}
      </button>
      {error ? <p className="text-[11px] text-rose-200 mt-1">{error}</p> : null}
    </div>
  );
}
