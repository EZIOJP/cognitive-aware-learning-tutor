/**
 * Focus shell bridge for CALT Sync receiver (:8765).
 * postMessage { type: "sync_host", op: "status"|"start"|"stop" } → calt_focus.
 */

export type SyncHostResult = {
  ok?: boolean;
  id?: string;
  op?: string;
  running?: boolean;
  reachable?: boolean;
  pid?: number;
  base_url?: string;
  token?: string;
  error?: string;
  type?: string;
};

function hasWebViewBridge(): boolean {
  const w = window as Window & {
    chrome?: { webview?: { postMessage: (m: unknown) => void } };
  };
  return Boolean(w.chrome?.webview?.postMessage);
}

export function isSyncHostBridgeAvailable(): boolean {
  return hasWebViewBridge();
}

export async function syncHostCmd(
  op: "status" | "start" | "stop",
  timeoutMs = 12000,
): Promise<SyncHostResult | null> {
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
      : `sync-${Date.now()}`;

  return new Promise((resolve) => {
    const timer = window.setTimeout(() => {
      cleanup();
      resolve({ ok: false, id, error: "timeout" });
    }, timeoutMs);

    const onMsg = (e: MessageEvent) => {
      let data: SyncHostResult | null = null;
      try {
        data = typeof e.data === "string" ? JSON.parse(e.data) : (e.data as SyncHostResult);
      } catch {
        return;
      }
      if (!data || data.type !== "sync_host_result" || data.id !== id) return;
      cleanup();
      resolve(data);
    };

    const cleanup = () => {
      window.clearTimeout(timer);
      w.chrome.webview.removeEventListener("message", onMsg);
    };

    w.chrome.webview.addEventListener("message", onMsg);
    try {
      w.chrome.webview.postMessage({ type: "sync_host", id, op, v: 1 });
    } catch {
      cleanup();
      resolve(null);
    }
  });
}
