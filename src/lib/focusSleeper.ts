/**
 * Focus Game Sleeper — low-CPU mode while gaming.
 * Unloads webcam/attention models, slows status polls. SoftLand ≠ Arm unchanged.
 */

const KEY = "calt:focus:sleeper";
const EVT = "calt:focus:sleeper-changed";

export type FocusSleeperState = {
  /** When true: no FaceTracker/Human.js, BodyCare timers idle, slow status bus. */
  active: boolean;
  /** Hide Focus window to tray when entering sleeper (native shell). */
  hideToTray: boolean;
};

const DEFAULT: FocusSleeperState = {
  active: false,
  hideToTray: true,
};

export function loadFocusSleeper(): FocusSleeperState {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return { ...DEFAULT };
    const j = JSON.parse(raw) as Partial<FocusSleeperState>;
    return {
      active: j.active === true,
      hideToTray: j.hideToTray !== false,
    };
  } catch {
    return { ...DEFAULT };
  }
}

export function saveFocusSleeper(next: FocusSleeperState): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(next));
    window.dispatchEvent(new CustomEvent(EVT, { detail: next }));
  } catch {
    /* ignore */
  }
}

export function setFocusSleeperActive(active: boolean): FocusSleeperState {
  const cur = loadFocusSleeper();
  const next = { ...cur, active };
  saveFocusSleeper(next);
  return next;
}

export function subscribeFocusSleeper(cb: (s: FocusSleeperState) => void): () => void {
  const on = (e: Event) => {
    const d = (e as CustomEvent<FocusSleeperState>).detail;
    cb(d ?? loadFocusSleeper());
  };
  const onStorage = (e: StorageEvent) => {
    if (e.key === KEY) cb(loadFocusSleeper());
  };
  window.addEventListener(EVT, on);
  window.addEventListener("storage", onStorage);
  return () => {
    window.removeEventListener(EVT, on);
    window.removeEventListener("storage", onStorage);
  };
}

export function isFocusSleeperActive(): boolean {
  return loadFocusSleeper().active;
}

/**
 * Post to calt_focus WebView host.
 * active+hide → tray hide + slow push; active+!hide → soft (slow push only); !active → wake.
 */
export function postFocusSleeperShell(active: boolean, hideToTray = true): boolean {
  if (typeof window === "undefined") return false;
  const w = window as Window & {
    chrome?: { webview?: { postMessage: (m: unknown) => void } };
  };
  if (!w.chrome?.webview?.postMessage) return false;
  try {
    const action = !active ? "sleeper_off" : hideToTray ? "sleeper_on" : "sleeper_soft";
    w.chrome.webview.postMessage({
      type: "focus_shell",
      v: 1,
      action,
    });
    return true;
  } catch {
    return false;
  }
}
