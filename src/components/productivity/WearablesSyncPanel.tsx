import { useCallback, useEffect, useState } from "react";
import { Loader2, RefreshCw, Watch } from "lucide-react";
import {
  fetchWearableStatus,
  getWearableToken,
  postWearableIngest,
  setWearableToken,
} from "../../api/wearablesClient";
import { WatchDayDumpCard } from "../life/WatchDayDumpCard";
import { resolveApiUrl } from "../../utils/resolveBackendUrl";
import { formatHoursMins } from "../../utils/formatDuration";

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

async function pingWearableHealth(): Promise<boolean> {
  const base = resolveApiUrl().replace(/\/$/, "");
  const token = getWearableToken();
  const res = await fetch(`${base}/api/wearables/zepp/health`, {
    headers: {
      Authorization: `Bearer ${token}`,
      "X-CALT-Wearable-Key": token,
    },
  });
  if (!res.ok) return false;
  const data = (await res.json()) as { ok?: boolean };
  return !!data.ok;
}

export function WearablesSyncPanel() {
  const [token, setToken] = useState(() => getWearableToken());
  const [status, setStatus] = useState<Awaited<
    ReturnType<typeof fetchWearableStatus>
  > | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [watching, setWatching] = useState(true);
  const [flash, setFlash] = useState(false);
  const [lastSeenAt, setLastSeenAt] = useState<string | null>(null);
  const [showRaw, setShowRaw] = useState(true);

  const base = resolveApiUrl().replace(/\/$/, "");

  const refresh = useCallback(async () => {
    setError(null);
    try {
      const s = await fetchWearableStatus();
      setStatus(s);
      const stamp =
        s.last_sync?.updated_at ||
        s.last_sync?.last_ingest_at ||
        null;
      if (stamp && stamp !== lastSeenAt) {
        if (lastSeenAt) setFlash(true);
        setLastSeenAt(stamp);
        try {
          const { notifyPipeline } = await import("../../utils/dataPipelineBus");
          notifyPipeline("wearables", { stamp });
        } catch {
          window.dispatchEvent(new CustomEvent("hub:refresh"));
        }
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

  const pingHealth = async () => {
    setBusy(true);
    setError(null);
    try {
      const ok = await pingWearableHealth();
      await refresh();
      if (!ok) setError("Health ping failed — is the backend / tracker hub running?");
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
  const caps = wd?.capabilities;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="font-semibold flex items-center gap-2 text-sm">
            <Watch size={16} className="text-primary" />
            Amazfit health dump
          </h3>
          <p className="mt-1 text-xs text-muted-foreground">
            CALT Sync 4.0 is a <span className="text-foreground">manual health dumper</span> — Dump
            on the watch, then Send. Queue holds up to 7 days you previously captured (sensors do not
            invent history). Install:{" "}
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
        <p className="text-[11px] text-amber-200/90 leading-relaxed">
          Watch dump needs the <span className="text-foreground">desktop tracker hub</span> on{" "}
          <code className="text-foreground">http://&lt;PC-LAN-IP&gt;:8765</code>. In Zepp → CALT Sync
          settings set that Base URL + token{" "}
          <code className="text-foreground">calt-local-wearables</code>. Replays are idempotent —
          sending the same chunk twice will not duplicate Life Tracker / hub rows.
        </p>
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
                : "bg-amber-500/20 text-amber-200"
            }`}
          >
            {isAuthenticWatch
              ? "Authentic watch dump"
              : authentic?.verdict === "web_or_test"
                ? "PC / test only"
                : "Waiting for watch dump"}
          </span>
          <span className="truncate" title={base}>
            {base}/api/wearables/zepp
          </span>
        </div>
        <div>
          Last event:{" "}
          <span className="text-foreground">{ls?.last_event ?? "none yet"}</span>
          {ls?.last_source ? ` · ${ls.last_source}` : ""}
          {ls?.last_duplicate ? (
            <span className="ml-2 text-sky-300">(replay / duplicate ACK)</span>
          ) : ls?.last_source === "web_test" || ls?.last_wrote_life === false ? (
            <span className="ml-2 text-amber-300">(test — does NOT write Life Tracker)</span>
          ) : ls?.last_is_watch || ls?.last_source === "mini_program" ? (
            <span className="ml-2 text-emerald-300">(watch → Life Tracker)</span>
          ) : null}
        </div>
        <div className="text-[11px]">
          Dump id:{" "}
          <span className="text-foreground">{wd?.last_dump_id || ls?.last_dump_id || "—"}</span>
          {wd?.last_chunk_id || ls?.last_chunk_id ? (
            <>
              {" "}
              · chunk{" "}
              <span className="text-foreground">{wd?.last_chunk_id || ls?.last_chunk_id}</span>
            </>
          ) : null}
        </div>
        {caps && typeof caps === "object" ? (
          <div className="text-[11px]">
            Sensors:{" "}
            {Object.entries(caps)
              .slice(0, 12)
              .map(([k, v]) => `${k}:${v ? "ok" : "n/a"}`)
              .join(" · ") || "—"}
          </div>
        ) : null}
        <WatchDayDumpCard
          day={wd}
          includeRaw={false}
          fallback={{
            last_steps: ls?.last_steps,
            last_sleep_hours: ls?.last_sleep_hours,
            last_calories: ls?.last_calories,
            last_distance_m: ls?.last_distance_m,
            last_hr: ls?.last_hr,
            last_spo2: ls?.last_spo2,
            last_stress: ls?.last_stress,
            last_pai: ls?.last_pai,
            last_stand: ls?.last_stand,
            last_sitting_min: ls?.last_sitting_min,
            last_battery: ls?.last_battery,
          }}
        />
        <div>
          Ingest: {fmtWhen(ls?.last_ingest_at)}
          {ls?.last_ingest_at ? (
            <span className="text-muted-foreground">
              {" "}
              (
              {Math.max(
                0,
                Math.round((Date.now() - new Date(ls.last_ingest_at).getTime()) / 60000),
              )}
              m ago)
            </span>
          ) : null}
        </div>
        {flash && (
          <p className="text-emerald-200 font-medium pt-1">Dump activity detected just now</p>
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
                  {formatHoursMins(status.applied_to_life.exercise_minutes ?? 0)}
                </span>
                , outdoor{" "}
                <span className="text-foreground">
                  {formatHoursMins(status.applied_to_life.outdoor_minutes ?? 0)}
                </span>
                , stress{" "}
                <span className="text-foreground">
                  {status.applied_to_life.stress_level ?? "—"}
                </span>
                , life score{" "}
                <span className="text-foreground">{status.applied_to_life.life_score ?? "—"}</span>
              </li>
              <li className="text-[11px]">
                Stored in SQLite <code className="text-foreground">life_daily_log</code> + hub{" "}
                <code className="text-foreground">readings</code>. Replay ledger:{" "}
                <code className="text-foreground">wearable_ingest_event</code>
              </li>
            </ul>
          ) : (
            <p className="text-muted-foreground">
              No Life Tracker row yet — Dump + Send on the watch (or Send test payload).
            </p>
          )}
        </div>
      )}

      <div className="rounded-xl border border-white/10 bg-black/25 px-3 py-3 text-xs space-y-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="font-medium text-foreground">Raw watch payload</p>
          <button
            type="button"
            onClick={() => setShowRaw((v) => !v)}
            className="rounded border border-white/10 px-2 py-0.5 text-[10px] hover:bg-white/5"
          >
            {showRaw ? "Hide" : "Show"}
          </button>
        </div>
        <p className="text-[11px] text-muted-foreground leading-relaxed">
          Nested JSON from CALT Sync Dump → Send. Missing sensors stay absent (never fabricated
          zeroes). Unsupported temperature stays unavailable.
          {wd?.local_date ? (
            <>
              {" "}
              Day: <span className="text-foreground">{wd.local_date}</span>
            </>
          ) : null}
        </p>
        {showRaw ? (
          wd?.payload ? (
            <pre className="max-h-80 overflow-auto rounded-lg border border-white/10 bg-black/40 p-2 text-[10px] leading-relaxed text-emerald-100/90 whitespace-pre-wrap break-all">
              {JSON.stringify(wd.payload, null, 2)}
            </pre>
          ) : (
            <p className="text-amber-200/90">
              No stored payload yet — Dump + Send from the watch.
            </p>
          )
        ) : null}
      </div>

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
          onClick={() => void pingHealth()}
          className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 px-3 py-1.5 text-xs hover:bg-white/5 disabled:opacity-50"
        >
          {busy ? <Loader2 size={12} className="animate-spin" /> : null}
          Ping health
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => void sendTestPayload()}
          className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-3 py-1.5 text-xs text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
        >
          {busy ? <Loader2 size={12} className="animate-spin" /> : <Watch size={12} />}
          Send test payload
        </button>
      </div>

      {error && (
        <p className="text-xs text-rose-300 break-words">
          {error.includes("404")
            ? "404 — restart the backend so /api/wearables/zepp is mounted."
            : error}
        </p>
      )}
    </div>
  );
}

export default WearablesSyncPanel;
