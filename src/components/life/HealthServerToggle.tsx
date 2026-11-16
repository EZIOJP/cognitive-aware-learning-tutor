import { useCallback, useEffect, useState } from "react";
import { Loader2, Power, Server } from "lucide-react";
import { isFocusDesktopShell } from "../../utils/focusDesktopShell";
import { syncHostCmd, type SyncHostResult } from "../../lib/syncHostCmd";

/**
 * Turn the CALT Sync receiver (:8765) on/off from the Health page.
 * Only works inside calt_focus WebView2.
 */
export function HealthServerToggle() {
  const focusShell = isFocusDesktopShell();
  const [st, setSt] = useState<SyncHostResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [hint, setHint] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!focusShell) return;
    const r = await syncHostCmd("status", 4000);
    if (r) setSt(r);
  }, [focusShell]);

  useEffect(() => {
    void refresh();
    if (!focusShell) return;
    const id = window.setInterval(() => void refresh(), 5000);
    return () => window.clearInterval(id);
  }, [focusShell, refresh]);

  if (!focusShell) return null;

  const on = Boolean(st?.running || st?.reachable);
  const label = busy
    ? "Working…"
    : on
      ? "Health server ON"
      : "Health server OFF";

  const toggle = async () => {
    setBusy(true);
    setHint(null);
    try {
      const r = await syncHostCmd(on ? "stop" : "start", 15000);
      if (r) setSt(r);
      if (r && r.ok === false) {
        setHint(r.error || "Could not toggle health server");
      } else if (r?.base_url) {
        setHint(on ? "Receiver stopped — watch cannot upload." : `Listening — ${r.base_url}`);
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex flex-col items-stretch gap-1 min-w-[11rem]">
      <button
        type="button"
        disabled={busy}
        onClick={() => void toggle()}
        className={`inline-flex items-center justify-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors disabled:opacity-50 ${
          on
            ? "border-emerald-500/40 bg-emerald-500/15 text-emerald-100 hover:bg-emerald-500/25"
            : "border-border/50 bg-muted/30 text-muted-foreground hover:bg-muted/50"
        }`}
        title={
          on
            ? "Stop calt_sync_host (:8765) — watch uploads will fail"
            : "Start calt_sync_host (:8765) for Amazfit Dump & Send"
        }
      >
        {busy ? (
          <Loader2 className="w-3.5 h-3.5 animate-spin" />
        ) : on ? (
          <Server className="w-3.5 h-3.5" />
        ) : (
          <Power className="w-3.5 h-3.5" />
        )}
        {label}
      </button>
      {hint ? (
        <p className="text-[10px] text-muted-foreground leading-snug max-w-[16rem]">{hint}</p>
      ) : st?.base_url ? (
        <p className="text-[10px] text-muted-foreground tabular-nums truncate max-w-[16rem]">
          {st.base_url}
        </p>
      ) : null}
    </div>
  );
}
