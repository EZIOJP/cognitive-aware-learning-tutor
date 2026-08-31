import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router";
import { Activity, AlertTriangle, Target, Zap } from "lucide-react";
import { fetchDayStatus, type DayStatusResponse } from "../../api/behaviorClient";
import { scoreColor } from "../productivity/GlanceBar";
import { CommunityRanksPanel } from "./CommunityRanksPanel";

export function TrackerDayBoard() {
  const [status, setStatus] = useState<DayStatusResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const data = await fetchDayStatus();
      setStatus(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }, []);

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
    <section className="gloss-panel rounded-2xl p-5 space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <span className="text-xs uppercase tracking-wide text-muted-foreground">Tracker board</span>
          <h2 className="text-lg font-semibold mt-0.5">Today at a glance</h2>
          <p className="text-sm text-muted-foreground mt-1">
            Unified day-status — same payload as CALT Android and hub.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => void refresh()}
            disabled={busy}
            className="text-xs rounded-lg border border-border/50 px-2.5 py-1 hover:bg-muted/40 disabled:opacity-50"
          >
            {busy ? "Refreshing…" : "Refresh"}
          </button>
          <Link
            to="/productivity?tab=calendar"
            className="text-xs rounded-lg border border-border/50 px-2.5 py-1 hover:bg-muted/40"
          >
            Calendar
          </Link>
        </div>
      </div>

      {error ? <p className="text-sm text-rose-300">{error}</p> : null}

      {!status && busy ? (
        <p className="text-sm text-muted-foreground">Loading tracker snapshot…</p>
      ) : null}

      {status ? (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <div className="rounded-xl border border-border/40 bg-muted/10 p-3">
            <div className="flex items-center gap-2 text-muted-foreground text-xs mb-1">
              <Zap className="w-3.5 h-3.5" />
              Pulse
            </div>
            <p className={`text-2xl font-semibold tabular-nums ${scoreColor(p?.pulse ?? 0)}`}>
              {p?.pulse ?? "—"}
            </p>
            <p className="text-xs text-muted-foreground">{p?.pulse_label ?? "No data"}</p>
          </div>

          <div className="rounded-xl border border-border/40 bg-muted/10 p-3">
            <div className="flex items-center gap-2 text-muted-foreground text-xs mb-1">
              <Target className="w-3.5 h-3.5" />
              Daily goal
            </div>
            <p className="text-2xl font-semibold tabular-nums">{p?.goal_pct ?? 0}%</p>
            <p className="text-xs text-muted-foreground">
              {p?.productive_label ?? "—"} productive
              {p?.goal_met ? " · met" : ""}
            </p>
          </div>

          <div className="rounded-xl border border-border/40 bg-muted/10 p-3">
            <div className="flex items-center gap-2 text-muted-foreground text-xs mb-1">
              <Activity className="w-3.5 h-3.5" />
              Focus quality
            </div>
            <p className="text-2xl font-semibold tabular-nums">
              {p?.focus_quality?.score ?? "—"}
            </p>
            <p className="text-xs text-muted-foreground">
              {p?.focus_quality?.label ?? "—"}
              {p?.focus_quality?.switches != null ? ` · ${p.focus_quality.switches} switches` : ""}
            </p>
          </div>

          <div className="rounded-xl border border-border/40 bg-muted/10 p-3">
            <div className="flex items-center gap-2 text-muted-foreground text-xs mb-1">
              Mode
            </div>
            <p className="text-base font-semibold">{status.browser_mode_label ?? status.browser_mode}</p>
            <p className="text-xs text-muted-foreground">
              Hard-block {hb?.armed ? "armed" : "off"}
              {hb?.locked ? " · locked" : ""}
              {status.tracker_alive ? " · tracker on" : " · tracker idle"}
            </p>
          </div>
        </div>
      ) : null}

      {status && (alert || w?.recovery_hint?.label || p?.study_mode_nudge?.active) ? (
        <div className="space-y-2 text-sm">
          {alert ? (
            <p className="flex items-center gap-2 text-amber-300">
              <AlertTriangle className="w-4 h-4 shrink-0" />
              {alert.label} — threshold reached
            </p>
          ) : null}
          {w?.recovery_hint?.label ? (
            <p className="text-muted-foreground">
              Recovery: {w.recovery_hint.label}
              {w.recovery_hint.suggested_focus_hours != null
                ? ` · ~${w.recovery_hint.suggested_focus_hours}h suggested focus`
                : ""}
            </p>
          ) : null}
          {p?.study_mode_nudge?.active ? (
            <p className="text-violet-300">Study mode nudge active after distraction alert</p>
          ) : null}
        </div>
      ) : null}

      {status?.comms ? (
        <div className="rounded-xl border border-border/40 bg-muted/10 p-3 text-sm space-y-1">
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Comms</p>
          <p>
            Extension {status.comms.extension?.status ?? "unknown"}
            {status.comms.api_up ? " · API up" : " · API down"}
            {status.comms.web_up ? " · Web up" : " · Web down"}
            {status.comms.startup_grace ? " · startup grace" : ""}
          </p>
          <p className="text-xs text-muted-foreground">
            SelfTracker {status.comms.extension?.selftracker_status ?? "—"}
            {status.comms.extension?.selftracker_age_s != null
              ? ` (${Math.round(status.comms.extension.selftracker_age_s)}s)`
              : " (never)"}
            {" · "}Gate {status.comms.extension?.calt_gate_status ?? "—"}
            {status.comms.extension?.calt_gate_age_s != null
              ? ` (${Math.round(status.comms.extension.calt_gate_age_s)}s)`
              : " (never)"}
            {(status.comms.extension?.false_positives || []).length
              ? ` · FP ${status.comms.extension?.false_positives?.join(", ")}`
              : ""}
            {(status.comms.extension?.false_negatives || []).length
              ? ` · FN ${status.comms.extension?.false_negatives?.join(", ")}`
              : ""}
          </p>
          {status.comms.current_issue?.why ? (
            <p className="text-amber-200 text-xs">Why: {status.comms.current_issue.why}</p>
          ) : null}
          {status.comms.current_issue?.how_to_fix ? (
            <p className="text-xs text-muted-foreground">Fix: {status.comms.current_issue.how_to_fix}</p>
          ) : null}
          {(status.comms.why_rules_idle || []).slice(0, 2).map((line) => (
            <p key={line} className="text-xs text-muted-foreground">
              {line}
            </p>
          ))}
          {status.comms.last_incident?.kind === "edge_closed" ? (
            <p className="text-amber-300 text-xs">
              Last Edge close: {status.comms.last_incident.why}
            </p>
          ) : null}
          {status.comms.edge_policy?.may_close_edge ? (
            <p className="text-amber-300 text-xs">Edge close allowed — extension confirmed absent</p>
          ) : (
            <p className="text-xs text-muted-foreground">Edge stays open while the extension is active or stale</p>
          )}
        </div>
      ) : null}

      <CommunityRanksPanel compact />
    </section>
  );
}
