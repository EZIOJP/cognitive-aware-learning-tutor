import { useCallback, useEffect, useState } from "react";
import { Loader2, RefreshCw, Shield, ShieldOff } from "lucide-react";
import {
  fetchDeviceBlock,
  refreshDeviceBlockList,
  saveDeviceBlock,
  type DeviceBlockStatus,
} from "../../api/behaviorClient";

export function DeviceBlockPanel() {
  const [status, setStatus] = useState<DeviceBlockStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const s = await fetchDeviceBlock();
      setStatus(s);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Could not load device block");
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const save = async (patch: Parameters<typeof saveDeviceBlock>[0]) => {
    setBusy(true);
    setErr(null);
    setMsg(null);
    try {
      const r = await saveDeviceBlock({ ...patch, apply_now: true });
      setStatus(r);
      if (r.apply?.needs_admin) {
        setErr(
          "Not active yet — run scripts\\device_block_apply.bat once as Admin. Desktop tracker retries hourly.",
        );
      } else if (r.apply?.ok && r.settings.enabled) {
        setMsg(`Porn block active — ${r.apply.domain_count ?? r.configured_domain_count} sites (YouTube not blocked).`);
      } else if (r.apply?.ok && !r.settings.enabled) {
        setMsg("Device block removed from hosts file.");
      }
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Save failed");
    } finally {
      setBusy(false);
    }
  };

  const rescrape = async () => {
    setBusy(true);
    setErr(null);
    setMsg(null);
    try {
      const r = await refreshDeviceBlockList();
      setStatus(r);
      const n = r.list?.count ?? r.configured_domain_count;
      setMsg(`Refreshed list from theporndude.com — ${n} domains.`);
      if (r.apply?.needs_admin) {
        setErr("List saved but hosts need Admin — run scripts\\device_block_apply.bat");
      }
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Refresh failed");
    } finally {
      setBusy(false);
    }
  };

  const s = status?.settings;
  const verify = status?.verify_sample;

  return (
    <div className="rounded-xl border border-white/10 bg-white/[0.03] p-4 space-y-3">
      <div className="flex items-center gap-2">
        <Shield className="w-4 h-4 text-primary shrink-0" />
        <h3 className="text-sm font-semibold">Porn block (desktop tracker)</h3>
        {status?.active ? (
          <span className="ml-auto text-[10px] text-emerald-300">hosts active</span>
        ) : (
          <span className="ml-auto text-[10px] text-muted-foreground">off</span>
        )}
      </div>
      <p className="text-xs text-muted-foreground leading-relaxed">
        Synced by the <strong className="text-foreground/90">desktop tracker</strong> into Windows{" "}
        <code className="text-foreground/80">hosts</code> — blocks porn in every app (Edge, Cursor
        browser, etc.). List scraped from <strong className="text-foreground/90">theporndude.com</strong>{" "}
        weekly. <strong className="text-foreground/90">YouTube is not blocked.</strong>
      </p>

      {err ? <p className="text-xs text-rose-300">{err}</p> : null}
      {msg ? <p className="text-xs text-emerald-300">{msg}</p> : null}

      <label className="flex items-center justify-between gap-3 text-sm">
        <span>Enable porn block on this PC</span>
        <input
          type="checkbox"
          disabled={busy || !s}
          checked={Boolean(s?.enabled)}
          onChange={(e) => void save({ enabled: e.target.checked, block_watch: false })}
        />
      </label>

      <details className="text-xs text-muted-foreground">
        <summary className="cursor-pointer hover:text-foreground">Optional: also block streaming / social</summary>
        <div className="grid gap-2 text-sm pl-1 border-l-2 border-white/10 mt-2">
          <label className="flex items-center justify-between gap-3">
            <span className="text-muted-foreground">YouTube / streaming</span>
            <input
              type="checkbox"
              disabled={busy || !s}
              checked={Boolean(s?.block_watch)}
              onChange={(e) => void save({ block_watch: e.target.checked })}
            />
          </label>
          <label className="flex items-center justify-between gap-3">
            <span className="text-muted-foreground">Social (Reddit, X, …)</span>
            <input
              type="checkbox"
              disabled={busy || !s}
              checked={Boolean(s?.block_social)}
              onChange={(e) => void save({ block_social: e.target.checked })}
            />
          </label>
        </div>
      </details>

      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          disabled={busy}
          className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground disabled:opacity-50"
          onClick={() => void save({ enabled: true, block_porn: true, block_watch: false })}
        >
          {busy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Shield className="w-3.5 h-3.5" />}
          Apply now
        </button>
        <button
          type="button"
          disabled={busy}
          className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 px-3 py-1.5 text-xs hover:bg-white/5 disabled:opacity-50"
          onClick={() => void rescrape()}
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Refresh TPD list
        </button>
        <button
          type="button"
          disabled={busy}
          className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 px-3 py-1.5 text-xs hover:bg-white/5 disabled:opacity-50"
          onClick={() => void save({ enabled: false })}
        >
          <ShieldOff className="w-3.5 h-3.5" />
          Remove
        </button>
      </div>

      {status ? (
        <p className="text-[10px] text-muted-foreground font-mono break-all">
          {status.active ? (
            <span className="text-emerald-300">ACTIVE · </span>
          ) : (
            <span className="text-rose-300">NOT in hosts · </span>
          )}
          {status.configured_domain_count} porn domains · {status.managed_host_entries} host lines
          {verify ? (
            <>
              {" "}
              · sample {verify.hostname} → {(verify.ips || []).join(", ") || "blocked"}
              {verify.blocked ? " ✓" : " ✗"}
            </>
          ) : null}
        </p>
      ) : null}
    </div>
  );
}
