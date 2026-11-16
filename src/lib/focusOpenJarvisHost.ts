/**
 * Native bridge: start/stop OpenJarvis API daemon (`jarvis start`) without the desktop GUI.
 */

export type OpenJarvisHostResult = {
  ok?: boolean;
  id?: string;
  op?: string;
  reachable?: boolean;
  pid?: number;
  jarvis_exe?: string;
  model?: string;
  error?: string;
  type?: string;
};

function hasWebViewBridge(): boolean {
  const w = window as Window & {
    chrome?: { webview?: { postMessage: (m: unknown) => void } };
  };
  return Boolean(w.chrome?.webview?.postMessage);
}

export function isOpenJarvisHostBridgeAvailable(): boolean {
  return hasWebViewBridge();
}

export async function openJarvisHostCmd(
  op: "status" | "start" | "stop" | "ensure",
  model?: string,
  timeoutMs = 90000,
): Promise<OpenJarvisHostResult | null> {
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
      : `oj-${Date.now()}`;

  return new Promise((resolve) => {
    const timer = window.setTimeout(() => {
      cleanup();
      resolve({ ok: false, id, op, error: "timeout" });
    }, timeoutMs);

    const onMsg = (e: MessageEvent) => {
      let data: OpenJarvisHostResult | null = null;
      try {
        data = typeof e.data === "string" ? JSON.parse(e.data) : (e.data as OpenJarvisHostResult);
      } catch {
        return;
      }
      if (!data || data.type !== "openjarvis_host_result" || data.id !== id) return;
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
        type: "openjarvis_host",
        v: 1,
        id,
        op,
        model: model || "",
      });
    } catch {
      cleanup();
      resolve(null);
    }
  });
}

/** Ensure :8000 is up — starts `jarvis start` in background if needed. */
export async function ensureOpenJarvisServe(model?: string): Promise<{
  ok: boolean;
  detail: string;
}> {
  const r = await openJarvisHostCmd("ensure", model, 90000);
  if (!r) {
    return {
      ok: false,
      detail: "native bridge missing — open Focus desktop (calt_focus)",
    };
  }
  if (r.ok && r.reachable) {
    return { ok: true, detail: `OpenJarvis serve up${r.pid ? ` (pid ${r.pid})` : ""}` };
  }
  return {
    ok: Boolean(r.reachable),
    detail: r.error || (r.reachable ? "up" : "serve still down"),
  };
}
