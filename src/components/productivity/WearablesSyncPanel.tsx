import { useCallback, useEffect, useState } from "react";
import { Loader2, RefreshCw, Watch } from "lucide-react";
import {
  fetchWearableStatus,
  getWearableToken,
  getWearablesHubUrl,
  postWearableIngest,
  postWearablePing,
  resolveWearablesBaseUrl,
  setWearableToken,
  setWearablesHubUrl,
} from "../../api/wearablesClient";
import { WatchDayDumpCard } from "../life/WatchDayDumpCard";
import { HealthServerToggle } from "../life/HealthServerToggle";
import { isFocusDesktopShell } from "../../utils/focusDesktopShell";
import { formatHoursMins } from "../../utils/formatDuration";
import { focusDataUrl } from "../../utils/focusDataUrl";

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
  const base = resolveWearablesBaseUrl();
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

type ZeppBridgeMirror = {
  api_ok?: boolean;
  api_version?: string;
  last_event?: string;
  last_source?: string;
  last_ingest_at?: string;
  days_written?: number;
  db_path?: string;
};

export function WearablesSyncPanel() {
  const focusShell = isFocusDesktopShell();
  const [token, setToken] = useState(() => getWearableToken());
  const [hubUrl, setHubUrl] = useState(() => getWearablesHubUrl());
  const [status, setStatus] = useState<Awaited<
    ReturnType<typeof fetchWearableStatus>
  > | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [flash, setFlash] = useState(false);
  const [pingFlash, setPingFlash] = useState<string | null>(null);
  const [lastSeenAt, setLastSeenAt] = useState<string | null>(null);
  const [lastPingId, setLastPingId] = useState<string | null>(null);
  const [showRaw, setShowRaw] = useState(true);
  const [zb, setZb] = useState<ZeppBridgeMirror | null>(null);
  const [zbBusy, setZbBusy] = useState(false);
  const [zbHint, setZbHint] = useState<string | null>(null);

  const base = resolveWearablesBaseUrl();

  const refreshZeppBridge = useCallback(async () => {
    try {
      const res = await fetch(`${focusDataUrl("wearables_ping.json")}?t=${Date.now()}`, {
        cache: "no-store",
      });
      if (!res.ok) {
        setZb(null);
        return;
      }
      const j = (await res.json()) as ZeppBridgeMirror;
      setZb(j?.last_source === "zeppbridge" || j?.last_event === "zeppbridge_pull" ? j : j);
    } catch {
      setZb(null);
    }
  }, []);

  const refresh = useCallback(async () => {
    setError(null);
    try {
      const s = await fetchWearableStatus();
      setStatus(s);
      const stamp =
        s.last_sync?.updated_at ||
        s.last_sync?.last_ingest_at ||
        s.last_ping?.at ||
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
      const pingId = s.last_ping?.id || s.last_sync?.last_ping_id || null;
      if (pingId && pingId !== lastPingId) {
        if (lastPingId) {
          setPingFlash(s.last_ping?.message || s.last_sync?.last_ping_message || "Watch ping");
          setFlash(true);
          window.dispatchEvent(new CustomEvent("hub:refresh"));
        }
        setLastPingId(pingId);
      }
    } catch (e) {
      setStatus(null);
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [lastSeenAt, lastPingId]);

  // Poll while open so watch Ping PC / Sync lights up Focus without manual Refresh.
  useEffect(() => {
    void refresh();
    const id = window.setInterval(() => void refresh(), 4000);
    return () => window.clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- mount poll
  }, []);

  useEffect(() => {
    if (!flash) return;
    const t = window.setTimeout(() => setFlash(false), 2500);
    return () => window.clearTimeout(t);
  }, [flash]);

  useEffect(() => {
    if (!pingFlash) return;
    const t = window.setTimeout(() => setPingFlash(null), 6000);
    return () => window.clearTimeout(t);
  }, [pingFlash]);

  const saveToken = () => {
    setWearableToken(token);
    void refresh();
  };

  const saveHubUrl = () => {
    setWearablesHubUrl(hubUrl);
    void refresh();
  };

  const pingHealth = async () => {
    setBusy(true);
    setError(null);
    try {
      const ok = await pingWearableHealth();
      if (ok) {
        try {
          const ping = await postWearablePing("Focus UI ping");
          setPingFlash(ping.message || "Focus UI ping");
          setFlash(true);
        } catch {
          /* older hub without /ping — health alone still useful */
        }
      }
      await refresh();
      if (!ok) {
        setError(
          focusShell
            ? "Health ping failed — turn Health server ON (or start_calt_sync_host.bat)."
            : "Health ping failed — is the backend / tracker hub running?",
        );
      }
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

  const pullZeppBridge = async () => {
    setZbBusy(true);
    setZbHint(null);
    try {
      const w = window as Window & {
        chrome?: { webview?: { postMessage: (m: unknown) => void } };
      };
      if (focusShell && w.chrome?.webview?.postMessage) {
        w.chrome.webview.postMessage({
          type: "run_repo_bat",
          name: "run\\pull_zeppbridge.bat",
          confirm: "zeppbridge_pull",
        });
        setZbHint("Pull started — reading ZeppBridge DB into Focus mirrors…");
        window.setTimeout(() => {
          void refresh();
          void refreshZeppBridge();
          setZbHint("Pulled (refresh again if Health still looks stale).");
          setZbBusy(false);
        }, 3500);
        return;
      }
      setZbHint(
        "Run on PC: python scripts\\run\\pull_zeppbridge.py  (ZeppBridge must be open / synced).",
      );
    } catch (e: unknown) {
      setZbHint(e instanceof Error ? e.message : "Pull failed");
    } finally {
      if (!(focusShell && (window as Window & { chrome?: { webview?: unknown } }).chrome?.webview)) {
        setZbBusy(false);
      }
    }
  };

  useEffect(() => {
    void refreshZeppBridge();
  }, [refreshZeppBridge]);

  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-emerald-500/25 bg-emerald-500/5 px-3 py-3 space-y-2">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 className="font-semibold flex items-center gap-2 text-sm">
              <Watch size={16} className="text-emerald-300" />
              ZeppBridge (preferred)
            </h3>
            <p className="mt-1 text-xs text-muted-foreground leading-relaxed max-w-xl">
              Desktop app syncs Amazfit → local DB. Focus pulls sleep / steps / stress into Health
              mirrors (no phone CALT Sync needed). Local REST{" "}
              <code className="text-foreground">127.0.0.1:43921</code> is for workout series; day
              cards come from <code className="text-foreground">zepp.db</code>.
            </p>
          </div>
          <button
            type="button"
            disabled={zbBusy}
            onClick={() => void pullZeppBridge()}
            className="flex items-center gap-1.5 rounded-lg border border-emerald-500/30 bg-emerald-500/15 px-3 py-2 text-xs text-emerald-100 hover:bg-emerald-500/25 disabled:opacity-50"
          >
            {zbBusy ? <Loader2 size={13} className="animate-spin" /> : <RefreshCw size={13} />}
            Pull from ZeppBridge
          </button>
        </div>
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-muted-foreground">
          <span>
            API:{" "}
            <span className={zb?.api_ok ? "text-emerald-300" : "text-amber-200"}>
              {zb?.api_ok ? `ok ${zb.api_version || ""}` : "not seen yet — open ZeppBridge + Local REST"}
            </span>
          </span>
          <span>Last pull: {fmtWhen(zb?.last_ingest_at)}</span>
          {typeof zb?.days_written === "number" ? <span>Days: {zb.days_written}</span> : null}
        </div>
        {zbHint ? <p className="text-xs text-sky-300/95">{zbHint}</p> : null}
      </div>

      <details className="group rounded-xl border border-border/40 bg-background/20 open:pb-1">
        <summary className="cursor-pointer list-none px-3 py-2.5 text-sm font-semibold marker:content-none [&::-webkit-details-marker]:hidden">
          <span className="inline-flex items-center gap-2">
            <Watch size={16} className="text-muted-foreground" />
            CALT Sync — legacy (optional)
            <span className="text-[11px] font-normal text-muted-foreground">
              collapsed · prefer ZeppBridge
            </span>
          </span>
        </summary>
        <div className="space-y-3 border-t border-border/30 px-3 pb-3 pt-2">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <p className="text-xs text-muted-foreground max-w-xl leading-relaxed">
              {focusShell ? (
                <>
                  Watch app → phone → <code className="text-foreground">calt_sync_host :8765</code>.
                  Only needed if ZeppBridge is unavailable.
                </>
              ) : (
                <>
                  Amazfit → phone <strong>CALT Sync</strong> → PC{" "}
                  <code className="text-foreground">:8765</code>.
                </>
              )}
            </p>
            {focusShell ? <HealthServerToggle /> : null}
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
          {focusShell ? (
            <>
              Use <strong>Health server ON</strong> so <code className="text-foreground">:8765</code> is
              listening. After Dump/Send, tap <strong>Refresh</strong>. Phone near watch (BLE); same Wi‑Fi.
            </>
          ) : (
            <>
              Manual sync: the watch POSTs when you Send. Replays are idempotent. Status here updates
              on <strong>Refresh</strong> or after you trigger a dump (watch → hub{" "}
              <code className="text-foreground">:8765</code>).
            </>
          )}
        </p>
        <div className="flex flex-wrap gap-x-4 gap-y-1 items-center">
          <span>
            Hub:{" "}
            <span className={status?.reachable ? "text-emerald-300" : "text-rose-300"}>
              {status?.reachable
                ? "reachable"
                : focusShell
                  ? "down — start wearables hub :8765"
                  : "down / 404 — restart backend"}
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
        {status?.categories?.present?.length ? (
          <div className="text-[11px]">
            Raw categories ({status.categories.count}):{" "}
            <span className="text-foreground">
              {status.categories.present.join(" · ")}
            </span>
            <span className="text-muted-foreground">
              {" "}
              — Health Connect / Sync extras land here (hrv, workouts, …)
            </span>
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
        {pingFlash && (
          <p className="text-sky-200 font-medium pt-1">
            Watch → Focus → PC: {pingFlash}
          </p>
        )}
        {flash && !pingFlash && (
          <p className="text-emerald-200 font-medium pt-1">Dump activity detected just now</p>
        )}
      </div>

      {focusShell ? (
        <div className="rounded-xl border border-white/10 bg-black/20 px-3 py-3 text-xs space-y-2">
          <p className="font-medium text-foreground">Where it went (Focus)</p>
          <p className="text-muted-foreground">
            Writes <code className="text-foreground">data/productivity/behavior/wearable_day.json</code>{" "}
            + per-day files under <code className="text-foreground">wearable_days/</code>. Amazfit CALT
            Sync posts to <code className="text-foreground">/api/wearables/zepp</code> (
            <code className="text-foreground">source: calt_zepp</code>
            ).
          </p>
        </div>
      ) : status?.applied_to_life || status?.estimates ? (
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
      ) : null}

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
          Nested JSON from ZeppBridge pull (preferred) or CALT Sync. Missing sensors stay
          absent or null — never fabricated zeroes. Unsupported temperature stays unavailable.
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
        {focusShell ? (
          <label className="text-xs text-muted-foreground space-y-1 min-w-[220px] flex-1">
            Hub URL (loopback for this panel; phone uses LAN IP)
            <input
              value={hubUrl}
              onChange={(e) => setHubUrl(e.target.value)}
              onBlur={saveHubUrl}
              placeholder="http://127.0.0.1:8765"
              className="w-full rounded-lg border border-white/10 bg-black/30 px-2.5 py-1.5 text-xs text-foreground"
            />
          </label>
        ) : null}
        <label className="text-xs text-muted-foreground space-y-1 min-w-[200px] flex-1">
          Ingest token (must match watch Settings)
          <input
            value={token}
            onChange={(e) => setToken(e.target.value)}
            onBlur={saveToken}
            className="w-full rounded-lg border border-white/10 bg-black/30 px-2.5 py-1.5 text-xs text-foreground"
          />
        </label>
        {focusShell ? (
          <button
            type="button"
            onClick={saveHubUrl}
            className="rounded-lg border border-white/10 px-3 py-1.5 text-xs hover:bg-white/5"
          >
            Save hub
          </button>
        ) : null}
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
          {error.includes("404") || error.includes("Failed to fetch")
            ? focusShell
              ? "Hub unreachable — start calt_sync_host (:8765), then Ping health."
              : "404 — restart the backend so /api/wearables/zepp is mounted."
            : error}
        </p>
      )}
        </div>
      </details>
    </div>
  );
}

export default WearablesSyncPanel;
