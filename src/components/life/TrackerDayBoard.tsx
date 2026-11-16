import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router";
import { Activity, AlertTriangle, Footprints, Target, Zap } from "lucide-react";
import { fetchDayStatus, type DayStatusResponse } from "../../api/behaviorClient";
import { fetchWearableStatus } from "../../api/wearablesClient";
import { fetchEnforcerStatusMirror, fetchDayRollupMirror } from "../../api/focusMirrors";
import { isFocusDesktopShell } from "../../utils/focusDesktopShell";
import { formatHoursMins } from "../../utils/formatDuration";
import { scoreColor } from "../productivity/GlanceBar";

function zeppStepsFromWearableDay(wd: NonNullable<Awaited<ReturnType<typeof fetchWearableStatus>>>["wearable_day"]): number | null {
  if (!wd) return null;
  const collector = wd.payload && typeof wd.payload === "object" ? (wd.payload as { collector?: { daily?: Record<string, unknown> } }).collector : null;
  const raw = collector?.daily?.steps;
  if (typeof raw === "number" && Number.isFinite(raw)) return raw;
  if (wd.data_quality?.steps_ok === true && typeof wd.steps === "number" && Number.isFinite(wd.steps)) {
    return wd.steps;
  }
  // FE zero-fill when Zepp row is missing — do not show as real steps.
  return null;
}

async function fetchFocusDayBoard(): Promise<DayStatusResponse> {
  const [wear, enf, rollup] = await Promise.all([
    fetchWearableStatus().catch(() => null),
    fetchEnforcerStatusMirror().catch(() => null),
    fetchDayRollupMirror().catch(() => null),
  ]);
  const wd = wear?.wearable_day;
  const ls = wear?.last_sync;
  const productive = Math.max(0, Math.floor(Number(rollup?.productive_minutes) || 0));
  const goal = Math.max(1, Math.floor(Number(rollup?.daily_focus_minutes) || 480));
  const goalPct = Math.min(100, Math.round((productive / goal) * 100));
  const steps = zeppStepsFromWearableDay(wd);
  const fromZepp = wd?.source === "zeppbridge";
  return {
    ok: true,
    schema: 1,
    day: wd?.local_date || rollup?.local_date || new Date().toISOString().slice(0, 10),
    browser_mode: "focus",
    browser_mode_label: "Focus",
    tracker_alive: true,
    hard_block: {
      armed: Boolean(enf?.armed),
      locked: false,
    },
    desktop: {
      control: "calt_focus",
      enforcer_owns_kills: true,
      hint: fromZepp
        ? "ZeppBridge pull"
        : wear?.reachable
          ? "CALT Sync hub up"
          : "Pull ZeppBridge or start hub :8765",
    },
    wearables: {
      sleep_hours: wd?.sleep_hours ?? ls?.last_sleep_hours ?? null,
      sleep_score: wd?.sleep_score ?? ls?.last_sleep_quality ?? null,
      sleep_label: wd?.sleep_label ?? null,
      steps,
    },
    productivity: {
      pulse: goalPct,
      pulse_label: fromZepp ? "ZeppBridge" : wear?.reachable ? "Hub up" : "Hub idle",
      goal_pct: goalPct,
      productive_label: formatHoursMins(productive),
      goal_met: Boolean(rollup?.goal_met) || productive >= goal,
      alerts: [],
      focus_quality: {
        score: steps != null ? Math.min(100, Math.round((Number(steps) / 8000) * 100)) : undefined,
        label: steps != null ? `${Number(steps).toLocaleString()} steps` : "Waiting for Zepp day metrics",
      },
    },
  };
}

export function TrackerDayBoard() {
  const focusShell = isFocusDesktopShell();
  const [status, setStatus] = useState<DayStatusResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const data = focusShell ? await fetchFocusDayBoard() : await fetchDayStatus();
      setStatus(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }, [focusShell]);

  useEffect(() => {
    void refresh();
    const id = window.setInterval(() => void refresh(), 60_000);
    return () => window.clearInterval(id);
  }, [refresh]);

  const p = status?.productivity;
  const hb = status?.hard_block;
  const w = status?.wearables;
  const alert = (p?.alerts || []).find((a) => a.triggered);

  return (
    <section className="gloss-panel rounded-2xl p-4 sm:p-5 space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-[15px] font-semibold tracking-tight">Today</h2>
          <p className="text-[11px] text-muted-foreground mt-0.5">
            {status?.desktop?.hint || "Focus · watch · tracker"}
          </p>
        </div>
        <div className="flex items-center gap-1.5">
          <button
            type="button"
            onClick={() => void refresh()}
            disabled={busy}
            className="text-[11px] rounded-lg border border-border/50 px-2.5 py-1 hover:bg-muted/40 disabled:opacity-50"
          >
            {busy ? "…" : "Refresh"}
          </button>
          <Link
            to="/productivity?tab=calendar"
            className="text-[11px] rounded-lg border border-border/50 px-2.5 py-1 hover:bg-muted/40"
          >
            Calendar
          </Link>
        </div>
      </div>

      {error ? <p className="text-sm text-rose-300">{error}</p> : null}

      {!status && busy ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : null}

      {status ? (
        <div className="grid gap-2 grid-cols-2 lg:grid-cols-4">
          <div className="rounded-xl border border-border/40 bg-muted/10 px-3 py-2.5">
            <div className="flex items-center gap-1.5 text-muted-foreground text-[10px] uppercase tracking-wide mb-1">
              <Zap className="w-3 h-3" />
              Goal
            </div>
            <p className={`text-xl font-semibold tabular-nums ${scoreColor(p?.pulse ?? p?.goal_pct ?? 0)}`}>
              {p?.goal_pct ?? 0}%
            </p>
            <p className="text-[11px] text-muted-foreground truncate">
              {p?.productive_label ?? "—"}
              {p?.goal_met ? " · met" : ""}
            </p>
          </div>

          <div className="rounded-xl border border-border/40 bg-muted/10 px-3 py-2.5">
            <div className="flex items-center gap-1.5 text-muted-foreground text-[10px] uppercase tracking-wide mb-1">
              <Footprints className="w-3 h-3" />
              Steps
            </div>
            <p className="text-xl font-semibold tabular-nums">
              {w?.steps != null ? Number(w.steps).toLocaleString() : "—"}
            </p>
            <p className="text-[11px] text-muted-foreground truncate">
              {p?.focus_quality?.label ?? "Watch"}
            </p>
          </div>

          <div className="rounded-xl border border-border/40 bg-muted/10 px-3 py-2.5">
            <div className="flex items-center gap-1.5 text-muted-foreground text-[10px] uppercase tracking-wide mb-1">
              <Activity className="w-3 h-3" />
              Mode
            </div>
            <p className="text-base font-semibold">{status.browser_mode_label ?? status.browser_mode}</p>
            <p className="text-[11px] text-muted-foreground truncate">
              Arm {hb?.armed ? "on" : "off"}
              {status.tracker_alive ? " · tracker" : ""}
            </p>
          </div>

          <div className="rounded-xl border border-border/40 bg-muted/10 px-3 py-2.5">
            <div className="flex items-center gap-1.5 text-muted-foreground text-[10px] uppercase tracking-wide mb-1">
              <Target className="w-3 h-3" />
              Sleep
            </div>
            <p className="text-xl font-semibold tabular-nums">
              {w?.sleep_hours != null && Number(w.sleep_hours) > 0
                ? `${Number(w.sleep_hours).toFixed(1)}h`
                : "—"}
            </p>
            <p className="text-[11px] text-muted-foreground truncate">
              {w?.sleep_label || (w?.sleep_score != null ? `score ${w.sleep_score}` : "from watch")}
            </p>
          </div>
        </div>
      ) : null}

      {status && (alert || w?.recovery_hint?.label || p?.study_mode_nudge?.active) ? (
        <div className="space-y-1.5 text-sm">
          {alert ? (
            <p className="flex items-center gap-2 text-amber-300">
              <AlertTriangle className="w-4 h-4 shrink-0" />
              {alert.label} — threshold reached
            </p>
          ) : null}
          {w?.recovery_hint?.label ? (
            <p className="text-muted-foreground text-xs">
              Recovery: {w.recovery_hint.label}
              {w.recovery_hint.suggested_focus_hours != null
                ? ` · ~${w.recovery_hint.suggested_focus_hours}h suggested focus`
                : ""}
            </p>
          ) : null}
          {p?.study_mode_nudge?.active ? (
            <p className="text-violet-300 text-xs">Focus nudge active after distraction alert</p>
          ) : null}
        </div>
      ) : null}

      {!focusShell && status?.comms ? (
        <div className="rounded-xl border border-border/40 bg-muted/10 p-3 text-sm space-y-1">
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Comms</p>
          <p>
            Extension {status.comms.extension?.status ?? "unknown"}
            {status.comms.api_up ? " · API up" : " · API down"}
            {status.comms.web_up ? " · Web up" : " · Web down"}
          </p>
        </div>
      ) : null}
    </section>
  );
}
