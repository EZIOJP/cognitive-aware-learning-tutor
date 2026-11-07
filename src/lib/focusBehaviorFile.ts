/**
 * Focus WebView → native: copy / reveal / open whitelisted behavior files.
 * Used so Settings export does not depend on fragile multi-MB calt-data fetch.
 */

type BehaviorFileResult = {
  ok?: boolean;
  id?: string;
  detail?: string;
  path?: string;
  error?: string;
  type?: string;
};

function hasWebViewBridge(): boolean {
  const w = window as Window & {
    chrome?: { webview?: { postMessage: (m: unknown) => void } };
  };
  return Boolean(w.chrome?.webview?.postMessage);
}

export function isFocusBehaviorFileAvailable(): boolean {
  return hasWebViewBridge();
}

export async function focusBehaviorFile(opts: {
  op: "copy_downloads" | "reveal" | "open";
  file: string;
  downloadName?: string;
  timeoutMs?: number;
}): Promise<BehaviorFileResult | null> {
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
      : `bf-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  const timeoutMs = opts.timeoutMs ?? 20_000;

  return new Promise((resolve) => {
    const timer = window.setTimeout(() => {
      cleanup();
      resolve({ ok: false, id, error: "timeout", detail: "timeout" });
    }, timeoutMs);

    const onMsg = (e: MessageEvent) => {
      let data: BehaviorFileResult | null = null;
      try {
        data = typeof e.data === "string" ? JSON.parse(e.data) : (e.data as BehaviorFileResult);
      } catch {
        return;
      }
      if (!data || data.type !== "behavior_file_result") return;
      if (data.id && data.id !== id) return;
      cleanup();
      resolve(data);
    };

    const cleanup = () => {
      window.clearTimeout(timer);
      w.chrome.webview.removeEventListener("message", onMsg);
    };

    w.chrome.webview.addEventListener("message", onMsg);
    w.chrome.webview.postMessage({
      type: "behavior_file",
      v: 1,
      id,
      op: opts.op,
      file: opts.file,
      download_name: opts.downloadName || "",
    });
  });
}

export function focusShellAction(
  action:
    | "reload_ui"
    | "ensure_tray"
    | "quit"
    | "open_settings"
    | "popup_tray"
    | "restart_enforcer"
    | "open_roadmap"
    | "open_openjarvis"
    | "update_ui"
    | "update_stack"
    | "apply_update",
): boolean {
  if (!hasWebViewBridge()) return false;
  const w = window as Window & {
    chrome: { webview: { postMessage: (m: unknown) => void } };
  };
  w.chrome.webview.postMessage({ type: "focus_shell", v: 1, action });
  return true;
}
