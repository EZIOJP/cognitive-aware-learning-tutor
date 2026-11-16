/**
 * Native PC power actions via calt_focus (lock / sleep / shutdown / cancel).
 */

export type PcPowerOp = "lock" | "sleep" | "shutdown" | "cancel";

export type PcPowerResult = {
  ok?: boolean;
  id?: string;
  op?: string;
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

export function isPcPowerBridgeAvailable(): boolean {
  return hasWebViewBridge();
}

export async function pcPowerCmd(
  op: PcPowerOp,
  opts?: { seconds?: number; timeoutMs?: number },
): Promise<PcPowerResult | null> {
  const timeoutMs = opts?.timeoutMs ?? 15000;
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
      : `pc-${Date.now()}`;

  return new Promise((resolve) => {
    const timer = window.setTimeout(() => {
      cleanup();
      resolve({ ok: false, id, op, error: "timeout" });
    }, timeoutMs);

    const onMsg = (e: MessageEvent) => {
      let data: PcPowerResult | null = null;
      try {
        data = typeof e.data === "string" ? JSON.parse(e.data) : (e.data as PcPowerResult);
      } catch {
        return;
      }
      if (!data || data.type !== "pc_power_result" || data.id !== id) return;
      cleanup();
      resolve(data);
    };

    const cleanup = () => {
      window.clearTimeout(timer);
      w.chrome.webview.removeEventListener("message", onMsg);
    };

    w.chrome.webview.addEventListener("message", onMsg);
    try {
      w.chrome.webview.postMessage({
        type: "pc_power",
        v: 1,
        id,
        op,
        ...(typeof opts?.seconds === "number" ? { seconds: opts.seconds } : {}),
      });
    } catch {
      cleanup();
      resolve(null);
    }
  });
}
