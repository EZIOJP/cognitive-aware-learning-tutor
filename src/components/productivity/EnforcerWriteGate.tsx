import { useCallback, useEffect, useState, type ReactNode } from "react";
import { AlertTriangle } from "lucide-react";
import {
  enforcerNativeCmd,
  isFocusEnforcerBridgeAvailable,
} from "../../lib/enforcerNativeCmd";
import { isFocusDesktopShell } from "../../utils/focusDesktopShell";

type Reachability = "unknown" | "ok" | "down" | "no_bridge";

/**
 * Phase 1 (decision 3A): when the Focus→enforcer pipe is down, hard-block writes.
 * Never optimistic-queue; never look armed when the enforcer is unreachable.
 */
export function useEnforcerReachability(pollMs = 4000): Reachability {
  const [state, setState] = useState<Reachability>(() =>
    isFocusDesktopShell() ? "unknown" : "no_bridge",
  );

  const probe = useCallback(async () => {
    if (!isFocusDesktopShell()) {
      setState("no_bridge");
      return;
    }
    if (!isFocusEnforcerBridgeAvailable()) {
      setState("no_bridge");
      return;
    }
    const res = await enforcerNativeCmd("status.snapshot", {}, 2500);
    if (!res) {
      setState("down");
      return;
    }
    if (res.ok === false || res.error === "enforcer_unreachable" || res.error === "timeout") {
      setState("down");
      return;
    }
    setState("ok");
  }, []);

  useEffect(() => {
    void probe();
    const t = window.setInterval(() => void probe(), pollMs);
    return () => window.clearInterval(t);
  }, [probe, pollMs]);

  return state;
}

export function EnforcerUnreachableBanner({ reachability }: { reachability: Reachability }) {
  if (reachability !== "down" && reachability !== "no_bridge") return null;
  const noBridge = reachability === "no_bridge";
  return (
    <div
      role="alert"
      className="rounded-2xl border border-amber-400/40 bg-amber-500/10 px-4 py-3 text-sm text-amber-100"
    >
      <div className="flex items-start gap-3">
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-300" aria-hidden />
        <div className="space-y-1">
          <p className="font-semibold text-amber-50">
            {noBridge ? "Enforcer bridge unavailable" : "Enforcer not running"}
          </p>
          <p className="text-[12px] leading-relaxed text-amber-100/85">
            {noBridge
              ? "Settings writes need calt_focus WebView2. Open CALT Focus from the tray — do not edit SoftLand/Arm from a normal browser."
              : "calt_enforcer is unreachable (named pipe down). SoftLand and Arm controls are locked so nothing looks armed when it is not. Start the enforcer (install script or tray Run stack), then retry."}
          </p>
        </div>
      </div>
    </div>
  );
}

/** Wraps write-capable Settings content: blocks pointer events when enforcer is down. */
export function EnforcerWriteGate({ children }: { children: ReactNode }) {
  const reachability = useEnforcerReachability();
  // Treat unknown as locked until the first probe succeeds (never look writable while unsure).
  const locked =
    reachability === "down" || reachability === "no_bridge" || reachability === "unknown";

  return (
    <div className="space-y-4">
      {reachability !== "unknown" && <EnforcerUnreachableBanner reachability={reachability} />}
      <div
        className={locked ? "pointer-events-none select-none opacity-45" : undefined}
        aria-disabled={locked || undefined}
      >
        {children}
      </div>
    </div>
  );
}
