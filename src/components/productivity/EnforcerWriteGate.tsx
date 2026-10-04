import { useEffect, type ReactNode } from "react";
import { AlertTriangle } from "lucide-react";
import { isFocusDesktopShell } from "../../utils/focusDesktopShell";
import { isFocusEnforcerBridgeAvailable } from "../../lib/enforcerNativeCmd";
import { useFocusStatus } from "../../hooks/useFocusStatus";

type Reachability = "unknown" | "ok" | "down" | "no_bridge";

/**
 * Reachability from the shared status bus (no per-panel pipe poll).
 */
export function useEnforcerReachability(): Reachability {
  const snap = useFocusStatus();

  if (!isFocusDesktopShell()) return "no_bridge";
  if (!isFocusEnforcerBridgeAvailable()) return "no_bridge";
  if (!snap.updatedAt) return "unknown";

  if (snap.pipeOk === false) return "down";

  const m = snap.enforcerStatus;
  if (m?.owns || m?.lock_present || m?.armed != null) {
    const ageMs = m.updated_at ? Date.now() - Date.parse(m.updated_at) : Infinity;
    if (Number.isFinite(ageMs) && ageMs < 60_000) return "ok";
  }
  if (snap.pipeOk === true) return "ok";
  if (snap.source === "sidecar" || snap.source === "push") return "ok";
  return "unknown";
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
  // Only lock when we know writes cannot work — "unknown" stays interactive (mirrors may still load).
  const locked = reachability === "down" || reachability === "no_bridge";

  return (
    <div className="space-y-4">
      <EnforcerUnreachableBanner reachability={reachability} />
      {reachability === "unknown" ? (
        <p className="text-[11px] text-muted-foreground">Checking enforcer…</p>
      ) : null}
      <div
        className={locked ? "pointer-events-none select-none opacity-45" : undefined}
        aria-disabled={locked || undefined}
      >
        {children}
      </div>
    </div>
  );
}
