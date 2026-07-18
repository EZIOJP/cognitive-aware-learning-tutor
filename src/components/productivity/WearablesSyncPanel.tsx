import { useCallback, useEffect, useState } from "react";
import { Loader2, RefreshCw, Watch } from "lucide-react";
import {
  fetchWearablePlans,
  fetchWearableStatus,
  getWearableToken,
  pingWearableWithPlans,
  postWearableIngest,
  setWearableToken,
  type WearablePlan,
  type WearableSyncStatus,
} from "../../api/wearablesClient";
import { resolveApiUrl } from "../../utils/resolveBackendUrl";

function fmtWhen(iso?: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return iso;
  }
}

export function WearablesSyncPanel() {
  const [token, setToken] = useState(() => getWearableToken());
  const [status, setStatus] = useState<WearableSyncStatus | null>(null);
  const [plans, setPlans] = useState<WearablePlan[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [watching, setWatching] = useState(true);
  const [flash, setFlash] = useState(false);
  const [lastSeenAt, setLastSeenAt] = useState<string | null>(null);

  const base = resolveApiUrl().replace(/\/$/, "");

  const refresh = useCallback(async () => {
    setError(null);
    try {
      const s = await fetchWearableStatus();
      setStatus(s);
      const stamp =
        s.last_sync?.updated_at ||
        s.last_sync?.last_ingest_at ||
        s.last_sync?.last_plans_at ||
        null;
      if (stamp && stamp !== lastSeenAt) {
        if (lastSeenAt) setFlash(true);
        setLastSeenAt(stamp);
      }
    } catch (e) {
      setStatus(null);
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [lastSeenAt]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    if (!watching) return;
    const id = window.setInterval(() => void refresh(), 2500);
    return () => window.clearInterval(id);
  }, [watching, refresh]);

  useEffect(() => {
    if (!flash) return;
    const t = window.setTimeout(() => setFlash(false), 2500);
    return () => window.clearTimeout(t);
  }, [flash]);

  const saveToken = () => {
    setWearableToken(token);
    void refresh();
  };

  const pullPlans = async () => {
    setBusy(true);
    setError(null);
    try {
      const rows = await fetchWearablePlans(24, "web_test");
      setPlans(rows);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const pingPlusPlans = async () => {
    setBusy(true);
    setError(null);
    try {
      const r = await pingWearableWithPlans(24);
      setPlans(r.plans);
      await refresh();
      if (!r.healthOk) setError("Health ping failed — is the backend running?");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const sendTestPayload = async () => {
    setBusy(true);
    setError(null);
    try {
      await postWearableIngest({
        source: "web_test",
        sleep: { total_min: 420, deep_min: 90, score: 80 },
        activity: { steps: 6543, target: 8000 },
        heart: { last: 72 },
      });
      const r = await pingWearableWithPlans(24);
      setPlans(r.plans);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const ls = status?.last_sync;
  const wd = status?.wearable_day;
  const authentic = status?.authentic;
  const isAuthenticWatch = authentic?.verdict === "authentic_watch";
  const plansFromWatch = !!authentic?.plans_from_watch;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="font-semibold flex items-center gap-2 text-sm">
            <Watch size={16} className="text-primary" />
            Amazfit / Zepp sync
          </h3>
          <p className="mt-1 text-xs text-muted-foreground">
            PC tests never count as watch. Authentic ={" "}
            <code className="text-[10px]">source=mini_program</code> + Life write. Install via QR:{" "}
            <code className="text-[10px]">packages\calt-zepp\sideload.bat</code>
          </p>
        </div>
        <label className="inline-flex items-center gap-2 text-xs text-muted-foreground">
          <input
            type="checkbox"
            checked={watching}
            onChange={(e) => setWatching(e.target.checked)}
            className="rounded border-white/20"
          />
          Live watch (2.5s)
        </label>
      </div>

      <div
        className={`rounded-xl border px-3 py-3 text-xs space-y-1.5 transition-colors ${
          flash
            ? "border-emerald-400/50 bg-emerald-500/15 text-emerald-100"
            : status?.reachable
              ? "border-white/10 bg-black/25 text-muted-foreground"
              : "border-rose-500/30 bg-rose-500/10 text-rose-200"
        }`}
      >
        <div className="flex flex-wrap gap-x-4 gap-y-1 items-center">
          <span>
            API:{" "}
            <span className={status?.reachable ? "text-emerald-300" : "text-rose-300"}>
              {status?.reachable ? "reachable" : "down / 404 — restart backend"}
            </span>
          </span>
          <span
            className={`rounded px-1.5 py-0.5 text-[10px] uppercase tracking-wide ${
              isAuthenticWatch
                ? "bg-emerald-500/25 text-emerald-200"
                : plansFromWatch
                  ? "bg-sky-500/20 text-sky-200"
                  : "bg-amber-500/20 text-amber-200"
            }`}
          >
            {isAuthenticWatch
              ? "Authentic watch sync"
              : plansFromWatch
                ? "Watch plans pull (no ingest yet)"
                : authentic?.verdict === "web_or_test"
                  ? "PC / test only"
                  : "Waiting for watch"}
          </span>
          <span className="truncate" title={base}>
            {base}/api/wearables/zepp
          </span>
        </div>
        <div>
          Last event:{" "}
          <span className="text-foreground">{ls?.last_event ?? "none yet"}</span>
          {ls?.last_source ? ` · ${ls.last_source}` : ""}
          {ls?.last_source === "web_test" || ls?.last_wrote_life === false ? (
            <span className="ml-2 text-amber-300">
              (test — does NOT write Life Tracker)
            </span>
          ) : ls?.last_is_watch || ls?.last_source === "mini_program" ? (
            <span className="ml-2 text-emerald-300">(watch → Life Tracker)</span>
          ) : null}
        </div>
        <div className="text-foreground font-medium tabular-nums grid grid-cols-2 gap-x-3 gap-y-1">
          <span>
            Steps:{" "}
            {wd?.steps != null
              ? `${wd.steps.toLocaleString()}${wd.step_target != null ? ` / ${wd.step_target.toLocaleString()}` : ""}`
              : ls?.last_steps != null
                ? ls.last_steps.toLocaleString()
                : "—"}
          </span>
          <span>
            Sleep:{" "}
            {wd?.sleep_hours != null
              ? `${wd.sleep_hours}h (score ${wd.sleep_score ?? "—"})`
              : ls?.last_sleep_hours != null
                ? `${ls.last_sleep_hours}h`
                : "—"}
          </span>
          <span>kcal: {wd?.calories ?? ls?.last_calories ?? "—"}</span>
          <span>
            Dist:{" "}
            {wd?.distance_m != null
              ? `${(wd.distance_m / 1000).toFixed(2)} km`
              : ls?.last_distance_m != null
                ? `${(ls.last_distance_m / 1000).toFixed(2)} km`
                : "—"}
          </span>
          <span>HR: {wd?.hr_last ?? ls?.last_hr ?? "—"}{wd?.hr_resting != null ? ` / rest ${wd.hr_resting}` : ""}</span>
          <span>SpO₂: {wd?.spo2 ?? ls?.last_spo2 ?? "—"}%</span>
          <span>Stress: {wd?.stress ?? ls?.last_stress ?? "—"}</span>
          <span>PAI: {wd?.pai_today ?? ls?.last_pai ?? "—"}</span>
          <span>
            Stand:{" "}
            {wd?.stand_hours != null
              ? `${wd.stand_hours}${wd.stand_target != null ? ` / ${wd.stand_target}` : ""}h`
              : ls?.last_stand ?? "—"}
          </span>
          <span>Battery: {wd?.battery_pct ?? ls?.last_battery ?? "—"}%</span>
        </div>
        <div>Ingest: {fmtWhen(ls?.last_ingest_at)}</div>
        <div>
          Plans pull: {fmtWhen(ls?.last_plans_at)}
          {ls?.last_plan_count != null ? ` · ${ls.last_plan_count} blocks` : ""}
        </div>
        {flash && (
          <p className="text-emerald-200 font-medium pt-1">Sync activity detected just now</p>
        )}
      </div>

      {(status?.applied_to_life || status?.estimates) && (
        <div className="rounded-xl border border-white/10 bg-black/20 px-3 py-3 text-xs space-y-2">
          <p className="font-medium text-foreground">Where it went (proof)</p>
          {status.applied_to_life ? (
            <ul className="space-y-1 text-muted-foreground">
              <li>
                Life Tracker {status.applied_to_life.date}: sleep{" "}
                <span className="text-foreground">
                  {status.applied_to_life.sleep_hours ?? 0}h
                </span>
                , exercise{" "}
                <span className="text-foreground">
                  {status.applied_to_life.exercise_minutes ?? 0}m
                </span>
                , outdoor{" "}
                <span className="text-foreground">
                  {status.applied_to_life.outdoor_minutes ?? 0}m
                </span>
                , stress{" "}
                <span className="text-foreground">
                  {status.applied_to_life.stress_level ?? "—"}
                </span>
                , life score{" "}
                <span className="text-foreground">{status.applied_to_life.life_score ?? "—"}</span>
              </li>
              <li>
                Estimate:{" "}
                <span className="text-foreground">
                  {status.estimates?.exercise_from_last_steps != null
                    ? `${ls?.last_steps?.toLocaleString() ?? "?"} steps → ~${status.estimates.exercise_from_last_steps}m exercise`
                    : "no steps yet"}
                </span>{" "}
                <span className="text-muted-foreground">(steps ÷ 100, max 180)</span>
              </li>
              <li className="text-[11px]">
                Stored in SQLite <code className="text-foreground">life_daily_log</code> + hub{" "}
                <code className="text-foreground">readings</code> (sleep_hours / steps). Mirror:{" "}
                <code className="text-foreground">data/wearables_last_sync.json</code>
              </li>
              <li className="text-[11px] text-amber-200/80">
                Not wired yet: HR beyond this panel; sleep → softer planner load (P5).
              </li>
            </ul>
          ) : (
            <p className="text-muted-foreground">
              No Life Tracker row yet — run Send test payload or Sync on the watch.
            </p>
          )}
        </div>
      )}

      <div className="flex flex-wrap gap-2 items-end">
        <label className="text-xs text-muted-foreground space-y-1 min-w-[200px] flex-1">
          Ingest token (must match watch Settings)
          <input
            value={token}
            onChange={(e) => setToken(e.target.value)}
            onBlur={saveToken}
            className="w-full rounded-lg border border-white/10 bg-black/30 px-2.5 py-1.5 text-xs text-foreground"
          />
        </label>
        <button
          type="button"
          onClick={saveToken}
          className="rounded-lg border border-white/10 px-3 py-1.5 text-xs hover:bg-white/5"
        >
          Save token
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => void refresh()}
          className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 px-3 py-1.5 text-xs hover:bg-white/5 disabled:opacity-50"
        >
          <RefreshCw size={12} /> Refresh
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => void pingPlusPlans()}
          className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 px-3 py-1.5 text-xs hover:bg-white/5 disabled:opacity-50"
        >
          {busy ? <Loader2 size={12} className="animate-spin" /> : null}
          Ping + plans
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => void sendTestPayload()}
          className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 px-3 py-1.5 text-xs hover:bg-white/5 disabled:opacity-50"
        >
          {busy ? <Loader2 size={12} className="animate-spin" /> : null}
          Send test payload
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => void pullPlans()}
          className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-3 py-1.5 text-xs text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
        >
          {busy ? <Loader2 size={12} className="animate-spin" /> : <Watch size={12} />}
          Pull plans (PC)
        </button>
      </div>

      {error && (
        <p className="text-xs text-rose-300 break-words">
          {error.includes("404")
            ? "404 — restart the backend so /api/wearables/zepp is mounted."
            : error}
        </p>
      )}

      {plans.length > 0 && (
        <ul className="max-h-36 overflow-y-auto space-y-1 text-[11px] border border-white/10 rounded-lg p-2 bg-black/20">
          {plans.slice(0, 8).map((p) => (
            <li key={p.id} className="flex justify-between gap-2">
              <span className="truncate text-foreground">{p.title}</span>
              <span className="shrink-0 text-muted-foreground tabular-nums">
                {new Date(p.start_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default WearablesSyncPanel;
