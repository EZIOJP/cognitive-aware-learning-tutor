/**
 * Native close browsers / named apps via calt_focus.
 */

export type PcAppsResult = {
  ok?: boolean;
  id?: string;
  op?: string;
  closed?: number;
  detail?: string;
  error?: string;
  type?: string;
};

function hasWebViewBridge(): boolean {
  const w = window as Window & {
    chrome?: { webview?: { postMessage: (m: unknown) => void } };
  };
  return Boolean(w.chrome?.webview?.postMessage);
}

export function isPcAppsBridgeAvailable(): boolean {
  return hasWebViewBridge();
}

export async function pcAppsCmd(
  op: "browsers" | "named",
  names = "",
  timeoutMs = 20000,
): Promise<PcAppsResult | null> {
  if (!hasWebViewBridge()) return null;
  const w = window as Window & {
    chrome: {
      webview: {
        postMessage: (m: unknown) => void;
        addEventListener: (type: string, fn: (e: MessageEvent) => void) => void;
        removeEventListener: (type: string, fn: (e: MessageEvent) => void) => void;
      };
    }
  };
  const id =
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : `apps-${Date.now()}`;

  return new Promise((resolve) => {
    const timer = window.setTimeout(() => {
      cleanup();
      resolve({ ok: false, id, op, error: "timeout" });
    }, timeoutMs);

    const onMsg = (e: MessageEvent) => {
      let data: PcAppsResult | null = null;
      try {
        data = typeof e.data === "string" ? JSON.parse(e.data) : (e.data as PcAppsResult);
      } catch {
        return;
      }
      if (!data || data.type !== "pc_apps_result" || data.id !== id) return;
      cleanup();
      resolve(data);
    };

    const cleanup = () => {
      window.clearTimeout(timer);
      w.chrome.webview.removeEventListener("message", onMsg);
    };

    w.chrome.webview.addEventListener("message", onMsg);
    try {
      w.chrome.webview.postMessage({ type: "pc_apps", v: 1, id, op, names });
    } catch {
      cleanup();
      resolve(null);
    }
  });
}
