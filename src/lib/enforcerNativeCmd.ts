/**
 * Focus shell bridge: chrome.webview.postMessage → calt_focus → enforcer named pipe.
 * Returns null when not running inside calt_focus WebView2 (browser Study app).
 */

type EnforcerCmdResult = {
  ok?: boolean;
  id?: string;
  error?: string;
  gateway_seq?: number;
  softland_enabled?: boolean;
  free_until?: string | null;
  incubation_until?: string | null;
  reward_day_active?: boolean;
  earned_ledger_seconds?: number;
  type?: string;
  [key: string]: unknown;
};

function hasWebViewBridge(): boolean {
  const w = window as Window & {
    chrome?: { webview?: { postMessage: (m: unknown) => void; addEventListener: Function } };
  };
  return Boolean(w.chrome?.webview?.postMessage);
}

export function isFocusEnforcerBridgeAvailable(): boolean {
  return hasWebViewBridge();
}

export async function enforcerNativeCmd(
  op: string,
  payload: Record<string, unknown> = {},
  timeoutMs = 5000,
): Promise<EnforcerCmdResult | null> {
  if (!hasWebViewBridge()) return null;
  const w = window as Window & {
    chrome: {
      webview: {
        postMessage: (m: unknown) => void;
        addEventListener: (type: string, fn: (e: MessageEvent) => void) => void;
        removeEventListener: (type: string, fn: (e: MessageEvent) => void) => void;
      };
    };
  };

  const id =
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : `cmd-${Date.now()}-${Math.random().toString(16).slice(2)}`;

  return new Promise((resolve) => {
    const timer = window.setTimeout(() => {
      cleanup();
      resolve({ ok: false, id, error: "timeout" });
    }, timeoutMs);

    const onMsg = (e: MessageEvent) => {
      let data: EnforcerCmdResult | null = null;
      try {
        data = typeof e.data === "string" ? JSON.parse(e.data) : (e.data as EnforcerCmdResult);
      } catch {
        return;
      }
      if (!data || data.type !== "enforcer_cmd_result") return;
      if (data.id && data.id !== id) return;
      cleanup();
      resolve(data);
    };

    const cleanup = () => {
      window.clearTimeout(timer);
      w.chrome.webview.removeEventListener("message", onMsg);
    };

    w.chrome.webview.addEventListener("message", onMsg);
    w.chrome.webview.postMessage({ type: "enforcer_cmd", v: 1, id, op, payload });
  });
}
