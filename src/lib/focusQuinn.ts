/**
 * Focus dashboard toggle for Quinn / Qwen porn appeals (Gate reads the mirror).
 * SoftLand blocking stays in the extension; this only gates whether appeals run.
 */

import { enforcerNativeCmd, isFocusEnforcerBridgeAvailable } from "./enforcerNativeCmd";
import { focusDataUrl } from "../utils/focusDataUrl";

const LS_KEY = "calt:focus-quinn:v1";
export const FOCUS_QUINN_EVENT = "calt:focus-quinn-updated";

export type FocusQuinnPrefs = {
  /** When false, Gate rejects porn appeals (SoftLand still blocks). */
  appealsEnabled: boolean;
};

export const DEFAULT_FOCUS_QUINN: FocusQuinnPrefs = {
  appealsEnabled: true,
};

export function loadFocusQuinnPrefs(): FocusQuinnPrefs {
  try {
    const raw = localStorage.getItem(LS_KEY);
    if (!raw) return { ...DEFAULT_FOCUS_QUINN };
    const p = JSON.parse(raw) as Partial<FocusQuinnPrefs>;
    return {
      appealsEnabled:
        typeof p.appealsEnabled === "boolean" ? p.appealsEnabled : DEFAULT_FOCUS_QUINN.appealsEnabled,
    };
  } catch {
    return { ...DEFAULT_FOCUS_QUINN };
  }
}

export function saveFocusQuinnPrefs(
  prefs: FocusQuinnPrefs,
  opts?: { skipEnforcer?: boolean },
): FocusQuinnPrefs {
  const next = { ...prefs };
  try {
    localStorage.setItem(LS_KEY, JSON.stringify(next));
    window.dispatchEvent(new CustomEvent(FOCUS_QUINN_EVENT, { detail: next }));
  } catch {
    /* ignore */
  }
  // Mirror for Gate / msg_host (enforcer writes behavior/quinn_dashboard.json).
  if (!opts?.skipEnforcer && isFocusEnforcerBridgeAvailable()) {
    void enforcerNativeCmd("quinn.set", { appeals_enabled: next.appealsEnabled });
  }
  return next;
}

/** Best-effort read of published mirror (Focus WebView calt-data). */
export async function fetchQuinnDashboardMirror(): Promise<FocusQuinnPrefs | null> {
  try {
    const url = focusDataUrl("quinn_dashboard.json");
    if (!url) return null;
    const res = await fetch(url, { cache: "no-store" });
    if (!res.ok) return null;
    const j = (await res.json()) as { appeals_enabled?: boolean };
    if (typeof j.appeals_enabled !== "boolean") return null;
    return { appealsEnabled: j.appeals_enabled };
  } catch {
    return null;
  }
}
