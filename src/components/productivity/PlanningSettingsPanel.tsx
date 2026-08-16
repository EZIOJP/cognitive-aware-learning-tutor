import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router";
import { CalendarCheck, Loader2, RefreshCw, Settings2 } from "lucide-react";
import {
  fetchDistractionGate,
  type BrowserGateSection,
  type MorningGate,
} from "../../api/behaviorClient";
import { applyRoutines, autoApplyRoutinesToday } from "../../api/plannerClient";
import {
  loadPlanningPrefs,
  setAutoApplyRoutinesOnLogin,
  type PlanningPrefs,
} from "./planningPrefs";

type Props = {
  refreshKey?: number;
  onPlannerChange?: () => void;
};

function KnobRow({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint?: string;
}) {
  return (
    <div className="flex flex-wrap items-baseline justify-between gap-2 rounded-lg border border-white/10 bg-black/20 px-3 py-2">
      <div className="min-w-0">
        <p className="text-xs font-medium text-foreground">{label}</p>
        {hint ? <p className="text-[10px] text-muted-foreground mt-0.5">{hint}</p> : null}
      </div>
      <code className="text-xs font-mono tabular-nums text-sky-200/90 shrink-0">{value}</code>
    </div>
  );
}

/**
 * Planning-related Settings — routine auto-apply pref + read-only morning/browser knobs.
 */
export function PlanningSettingsPanel({ refreshKey = 0, onPlannerChange }: Props) {
  const [prefs, setPrefs] = useState<PlanningPrefs>(() => loadPlanningPrefs());
  const [morning, setMorning] = useState<MorningGate | null>(null);
  const [browser, setBrowser] = useState<BrowserGateSection | null>(null);
  const [busy, setBusy] = useState<"auto" | "force" | null>(null);
  const [hint, setHint] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadGate = useCallback(async () => {
    try {
      const g = await fetchDistractionGate();
      setMorning(g.morning ?? null);
      setBrowser(g.browser ?? null);
    } catch {
      setMorning(null);
      setBrowser(null);
    }
  }, []);

  useEffect(() => {
    void loadGate();
  }, [loadGate, refreshKey]);

  const onToggleAutoApply = (on: boolean) => {
    setPrefs(setAutoApplyRoutinesOnLogin(on));
    setHint(
      on
        ? "Enabled routines will auto-apply once per day after sign-in."
        : "Sign-in will skip routine auto-apply. You can still Apply on the Plan tab.",
    );
  };

  const runAutoApply = async () => {
    setBusy("auto");
    setError(null);
    try {
      const r = await autoApplyRoutinesToday();
      if (r.skipped) {
        setHint(`Already applied today${r.date ? ` (${r.date})` : ""} — 0 new blocks.`);
      } else {
        setHint(`Applied ${r.created} routine block${r.created === 1 ? "" : "s"} for today.`);
        onPlannerChange?.();
      }
      await loadGate();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Auto-apply failed");
    } finally {
      setBusy(null);
    }
  };

  const forceApply = async () => {
    setBusy("force");
    setError(null);
    try {
      const r = await applyRoutines();
      setHint(`Force-applied ${r.created} block${r.created === 1 ? "" : "s"} (overlaps skipped).`);
      onPlannerChange?.();
      await loadGate();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Apply failed");
    } finally {
      setBusy(null);
    }
  };

  const start =
    morning?.config?.plan_start ||
    morning?.plan_window?.start_hhmm ||
    "05:00";
  const eod =
    morning?.config?.plan_eod || morning?.plan_window?.eod_hhmm || "23:59";
  const autoPlanOn =
    morning?.config?.auto_plan ??
    (morning?.auto_plan != null ? true : null);
  const autoConfirmOn = morning?.config?.auto_plan_confirm ?? false;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="font-semibold flex items-center gap-2 text-sm">
            <Settings2 size={16} className="text-primary" />
            Planning
          </h3>
          <p className="mt-1 text-sm text-muted-foreground">
            Morning window, routine auto-apply, and browser study vs free defaults.
          </p>
        </div>
        <Link
          to="/productivity?tab=plan"
          className="inline-flex items-center gap-1.5 text-xs text-primary hover:underline"
        >
          <CalendarCheck size={13} />
          Open Plan tab
        </Link>
      </div>

      <div className="space-y-2">
        <p className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
          Routines
        </p>
        <label className="flex items-center justify-between gap-3 rounded-xl border border-white/10 bg-black/20 px-3 py-2.5 text-sm cursor-pointer">
          <span>
            <span className="block font-medium">Auto-apply on sign-in</span>
            <span className="text-xs text-muted-foreground">
              Opt-in — once per day, enabled routines only. Off by default so Planning stays manual.
            </span>
          </span>
          <input
            type="checkbox"
            checked={prefs.autoApplyRoutinesOnLogin}
            onChange={(e) => onToggleAutoApply(e.target.checked)}
          />
        </label>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            disabled={busy !== null}
            onClick={() => void runAutoApply()}
            className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-xs hover:bg-white/10 disabled:opacity-50"
          >
            {busy === "auto" ? (
              <Loader2 size={13} className="animate-spin" />
            ) : (
              <RefreshCw size={13} />
            )}
            Apply once (today)
          </button>
          <button
            type="button"
            disabled={busy !== null}
            onClick={() => void forceApply()}
            className="inline-flex items-center gap-1.5 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-1.5 text-xs text-amber-100 hover:bg-amber-500/20 disabled:opacity-50"
          >
            {busy === "force" ? <Loader2 size={13} className="animate-spin" /> : null}
            Force apply now
          </button>
        </div>
      </div>

      <div className="space-y-2">
        <p className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
          Morning gate <span className="normal-case font-normal">(read-only · .env)</span>
        </p>
        <div className="grid gap-2 sm:grid-cols-2">
          <KnobRow
            label="MORNING_GATE"
            value={morning?.enabled ? "on" : morning == null ? "—" : "off"}
            hint="Bible → plan confirm → open"
          />
          <KnobRow
            label="Plan window"
            value={`${start} → ${eod}`}
            hint="MORNING_PLAN_START → MORNING_PLAN_EOD"
          />
          <KnobRow
            label="MORNING_AUTO_PLAN"
            value={
              autoPlanOn === null ? "—" : autoPlanOn ? "on" : "off"
            }
            hint="Draft after Bible"
          />
          <KnobRow
            label="MORNING_AUTO_PLAN_CONFIRM"
            value={autoConfirmOn ? "on" : "off"}
            hint="Usually off — keep Confirm CTA"
          />
        </div>
        {morning?.enabled && (
          <p className="text-[11px] text-muted-foreground">
            Today: next=<code className="text-foreground/80">{morning.next}</code>
            {" · "}
            blocks={morning.blocks_today}
            {morning.plan_done ? " · plan confirmed" : ""}
            {morning.plan_window?.phase
              ? ` · window=${morning.plan_window.phase}`
              : ""}
          </p>
        )}
      </div>

      <div className="space-y-2">
        <p className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
          Browser mode
        </p>
        <div className="grid gap-2 sm:grid-cols-2">
          <KnobRow
            label="Daytime default"
            value={(browser?.daytime_default || "study").toUpperCase()}
            hint="After plan confirm"
          />
          <KnobRow
            label="BROWSER_FREE_AFTER"
            value={browser?.free_after || "21:00"}
            hint="Evening free window (local)"
          />
        </div>
        {browser?.mode_label && (
          <p className="text-[11px] text-muted-foreground">
            Now:{" "}
            <span className="font-semibold text-foreground">{browser.mode_label}</span>
            {browser.note ? ` — ${browser.note}` : ""}
          </p>
        )}
      </div>

      {hint && <p className="text-xs text-sky-300">{hint}</p>}
      {error && (
        <p className="text-sm text-red-300 bg-red-500/10 border border-red-500/30 rounded-lg px-3 py-2">
          {error}
        </p>
      )}
      <p className="text-[11px] text-muted-foreground pt-1">
        Need Soft-land demos?{" "}
        <Link to="/productivity?tab=settings#demo-mode" className="text-amber-200 underline underline-offset-2 hover:text-white">
          Open Demo mode
        </Link>{" "}
        (same Settings tab, below).
      </p>
    </div>
  );
}

export default PlanningSettingsPanel;
