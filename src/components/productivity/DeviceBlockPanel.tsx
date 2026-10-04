import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, Loader2, Lock, RefreshCw, Shield, ShieldOff } from "lucide-react";
import {
  fetchDeviceBlockNative,
  isDeviceBlockNativeAvailable,
  refreshDeviceBlockListNative,
  removeDeviceBlockNative,
  saveDeviceBlockNative,
  type DeviceBlockStatus,
} from "../../api/deviceBlockClient";
import { isFocusDesktopShell } from "../../utils/focusDesktopShell";

const CONFIRM_PHRASE = "DEVICE LOCK";

function launchRepoBat(
  name: "device_block_apply.bat" | "device_block_remove.bat",
  confirm: string,
) {
  const w = window as Window & {
    chrome?: { webview?: { postMessage: (m: unknown) => void } };
  };
  if (w.chrome?.webview?.postMessage) {
    w.chrome.webview.postMessage({ type: "run_repo_bat", v: 1, name, confirm });
    return true;
  }
  return false;
}

/**
 * Permanent PC-wide porn block via Windows hosts file (native enforcer).
 * SoftLand Allow cannot override this.
 */
export function DeviceBlockPanel() {
  const [status, setStatus] = useState<DeviceBlockStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [confirmPhrase, setConfirmPhrase] = useState("");
  const [showEnableConfirm, setShowEnableConfirm] = useState(false);
  const [showRemoveConfirm, setShowRemoveConfirm] = useState(false);
  const focusShell = isFocusDesktopShell();
  const nativeOk = isDeviceBlockNativeAvailable();

  const refresh = useCallback(async () => {
    try {
      if (!isDeviceBlockNativeAvailable()) {
        setErr("Start calt_enforcer (Arm engine) — Device lock no longer uses Study :8000.");
        return;
      }
      const s = await fetchDeviceBlockNative();
      setStatus(s);
      setErr(null);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Could not load device lock — is calt_enforcer running?");
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const enableWithConfirm = async () => {
    if (confirmPhrase.trim() !== CONFIRM_PHRASE) {
      setErr(`Type ${CONFIRM_PHRASE} exactly to enable permanent device lock.`);
      return;
    }
    setBusy(true);
    setErr(null);
    setMsg(null);
    try {
      const r = await saveDeviceBlockNative({
        enabled: true,
        block_porn: true,
        block_watch: false,
        block_social: false,
        apply_now: true,
        confirm: CONFIRM_PHRASE,
      });
      setStatus(r);
      setShowEnableConfirm(false);
      setConfirmPhrase("");
      if (r.apply?.needs_admin || (r.settings.enabled && !r.active)) {
        setMsg("Settings saved — hosts need Admin. Launching Apply as Admin…");
        if (focusShell) launchRepoBat("device_block_apply.bat", CONFIRM_PHRASE);
        else setErr("Run scripts\\device_block_apply.bat as Administrator with confirm.");
      } else if (r.active) {
        setMsg(`Device lock ACTIVE — ${r.configured_domain_count} domains.`);
      } else if (focusShell) {
        // Ensure Admin path always gets confirm after enable dialog
        launchRepoBat("device_block_apply.bat", CONFIRM_PHRASE);
        setMsg("Enabled — Admin apply launched if hosts need elevation.");
      }
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Enable failed");
    } finally {
      setBusy(false);
    }
  };

  const removeWithConfirm = async () => {
    if (confirmPhrase.trim() !== CONFIRM_PHRASE) {
      setErr(`Type ${CONFIRM_PHRASE} exactly to remove device lock.`);
      return;
    }
    setBusy(true);
    setErr(null);
    setMsg(null);
    try {
      const r = await removeDeviceBlockNative(CONFIRM_PHRASE);
      setStatus(r);
      setShowRemoveConfirm(false);
      setConfirmPhrase("");
      if (r.apply?.needs_admin || r.active) {
        setMsg("Disabled in settings — hosts need Admin remove.");
        if (focusShell) launchRepoBat("device_block_remove.bat", CONFIRM_PHRASE);
      } else {
        setMsg("Device lock removed from hosts.");
      }
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Remove failed");
    } finally {
      setBusy(false);
    }
  };

  const rescrape = async () => {
    setBusy(true);
    setErr(null);
    setMsg(null);
    try {
      const r = await refreshDeviceBlockListNative(true);
      setStatus(r);
      setMsg(`Refresh ${r.refresh || "kicked"} — ${r.configured_domain_count} domains (seeds∪cache).`);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Refresh failed");
    } finally {
      setBusy(false);
    }
  };

  const s = status?.settings;
  const verify = status?.verify_sample;
  const active = Boolean(status?.active);

  return (
    <div className="rounded-xl border border-rose-500/25 bg-rose-500/[0.04] p-4 space-y-3">
      <div className="flex items-center gap-2">
        <Lock className="w-4 h-4 text-rose-300 shrink-0" aria-hidden />
        <h3 className="text-sm font-semibold text-foreground">Device lock (hosts)</h3>
        {active ? (
          <span className="ml-auto text-[10px] font-medium text-emerald-300">ACTIVE in hosts</span>
        ) : (
          <span className="ml-auto text-[10px] text-muted-foreground">not in hosts</span>
        )}
      </div>

      {!nativeOk ? (
        <p className="text-xs text-amber-200/90 rounded-lg border border-amber-400/25 bg-amber-500/10 px-3 py-2">
          Start <code className="text-amber-50">calt_enforcer</code> to manage Device lock. Apply/Remove as
          Admin still works from Focus once you type {CONFIRM_PHRASE}.
        </p>
      ) : null}

      <div
        role="note"
        className="rounded-lg border border-amber-400/35 bg-amber-500/10 px-3 py-2.5 text-[11px] text-amber-100/95 leading-relaxed space-y-1"
      >
        <p className="font-semibold text-amber-50 flex items-center gap-1.5">
          <AlertTriangle size={13} aria-hidden /> Permanent · PC-wide · use sparingly
        </p>
        <ul className="list-disc pl-4 space-y-0.5 text-amber-100/85">
          <li>Windows <code className="text-amber-50/90">hosts</code> — every app. SoftLand Allow does not override.</li>
          <li>Native enforcer only — no Study API. Type {CONFIRM_PHRASE} to enable or remove.</li>
          <li>Default porn-only; YouTube stays off unless you opt into streaming under details.</li>
        </ul>
      </div>

      {err ? <p className="text-xs text-rose-300">{err}</p> : null}
      {msg ? <p className="text-xs text-emerald-300">{msg}</p> : null}

      {!showEnableConfirm && !showRemoveConfirm ? (
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            disabled={busy}
            className="inline-flex items-center gap-1.5 rounded-lg bg-rose-600/85 hover:bg-rose-600 px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-50"
            onClick={() => {
              setShowEnableConfirm(true);
              setConfirmPhrase("");
              setErr(null);
            }}
          >
            <Shield className="w-3.5 h-3.5" />
            Enable device lock…
          </button>
          <button
            type="button"
            disabled={busy}
            className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 px-3 py-1.5 text-xs hover:bg-white/5 disabled:opacity-50"
            onClick={() => {
              if (!s?.enabled) {
                setShowEnableConfirm(true);
                setConfirmPhrase("");
                setErr(null);
                setMsg("Confirm enable first — Admin apply will follow.");
                return;
              }
              if (launchRepoBat("device_block_apply.bat", CONFIRM_PHRASE)) {
                setMsg("Launched Admin apply — approve UAC, then Status.");
              } else {
                setErr("Focus shell required to launch Admin apply, or run scripts\\device_block_apply.bat");
              }
            }}
          >
            Apply as Admin
          </button>
          <button
            type="button"
            disabled={busy || !nativeOk}
            className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 px-3 py-1.5 text-xs hover:bg-white/5 disabled:opacity-50"
            onClick={() => void rescrape()}
          >
            {busy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}
            Refresh list
          </button>
          <button
            type="button"
            disabled={busy || !nativeOk}
            className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 px-3 py-1.5 text-xs hover:bg-white/5 disabled:opacity-50"
            onClick={() => void refresh()}
          >
            Status
          </button>
          <button
            type="button"
            disabled={busy || (!s?.enabled && !active)}
            className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 px-3 py-1.5 text-xs hover:bg-white/5 disabled:opacity-50"
            onClick={() => {
              setShowRemoveConfirm(true);
              setConfirmPhrase("");
              setErr(null);
            }}
          >
            <ShieldOff className="w-3.5 h-3.5" />
            Remove…
          </button>
        </div>
      ) : (
        <div className="rounded-lg border border-rose-400/30 bg-black/30 p-3 space-y-2">
          <p className="text-xs text-foreground/90">
            Type <code className="text-rose-200">{CONFIRM_PHRASE}</code> to{" "}
            {showRemoveConfirm ? "remove" : "enable"} permanent hosts porn lock:
          </p>
          <input
            value={confirmPhrase}
            onChange={(e) => setConfirmPhrase(e.target.value)}
            className="w-full rounded-lg border border-white/15 bg-black/40 px-2.5 py-1.5 text-xs font-mono"
            placeholder={CONFIRM_PHRASE}
            autoComplete="off"
            spellCheck={false}
          />
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              disabled={busy || confirmPhrase.trim() !== CONFIRM_PHRASE}
              className="rounded-lg bg-rose-600 px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-40"
              onClick={() => void (showRemoveConfirm ? removeWithConfirm() : enableWithConfirm())}
            >
              {busy ? "Working…" : showRemoveConfirm ? "Confirm & remove" : "Confirm & enable"}
            </button>
            <button
              type="button"
              disabled={busy}
              className="rounded-lg border border-white/10 px-3 py-1.5 text-xs"
              onClick={() => {
                setShowEnableConfirm(false);
                setShowRemoveConfirm(false);
                setConfirmPhrase("");
              }}
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      <details className="text-xs text-muted-foreground">
        <summary className="cursor-pointer hover:text-foreground">Optional: also lock streaming / social in hosts</summary>
        <p className="mt-1.5 text-[10px] text-amber-200/80">
          Warning: hosts streaming/social stays blocked after SoftLand unlock — prefer SoftLand Block for those.
        </p>
        <div className="grid gap-2 text-sm pl-1 border-l-2 border-white/10 mt-2">
          <label className="flex items-center justify-between gap-3">
            <span className="text-muted-foreground">YouTube / streaming (hosts)</span>
            <input
              type="checkbox"
              disabled={busy || !s || !nativeOk}
              checked={Boolean(s?.block_watch)}
              onChange={(e) =>
                void saveDeviceBlockNative({ block_watch: e.target.checked, apply_now: true }).then(setStatus)
              }
            />
          </label>
          <label className="flex items-center justify-between gap-3">
            <span className="text-muted-foreground">Social (Reddit, X, …)</span>
            <input
              type="checkbox"
              disabled={busy || !s || !nativeOk}
              checked={Boolean(s?.block_social)}
              onChange={(e) =>
                void saveDeviceBlockNative({ block_social: e.target.checked, apply_now: true }).then(setStatus)
              }
            />
          </label>
        </div>
      </details>

      {status ? (
        <p className="text-[10px] text-muted-foreground font-mono break-all">
          {active ? (
            <span className="text-emerald-300">ACTIVE · </span>
          ) : (
            <span className="text-rose-300">NOT in hosts · </span>
          )}
          {status.configured_domain_count} domains · {status.managed_host_entries} host lines
          {s?.enabled ? " · settings on" : " · settings off"}
          {status.refresh ? ` · refresh ${status.refresh}` : ""}
          {verify ? (
            <>
              {" "}
              · sample {verify.hostname}
              {verify.blocked ? " ✓" : " ✗"}
            </>
          ) : null}
        </p>
      ) : null}
    </div>
  );
}
