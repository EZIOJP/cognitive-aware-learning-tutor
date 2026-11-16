/**
 * Native WinHTTP bridge for Focus LLM hosts.
 * WebView fetch to OpenJarvis :8000 fails CORS ("Failed to fetch");
 * calt_focus proxies allowlisted URLs without SoftLand/Arm involvement.
 */

export type LlmHttpResult = {
  ok: boolean;
  status: number;
  body: string;
  error?: string;
  is_base64?: boolean;
};

function hasWebViewBridge(): boolean {
  const w = window as Window & {
    chrome?: { webview?: { postMessage: (m: unknown) => void } };
  };
  return Boolean(w.chrome?.webview?.postMessage);
}

export function isFocusLlmNativeHttpAvailable(): boolean {
  return hasWebViewBridge();
}

export async function focusLlmNativeHttp(opts: {
  method: "GET" | "POST" | "HEAD";
  url: string;
  authorization?: string;
  contentType?: string;
  body?: string;
  timeoutMs?: number;
  base64Response?: boolean;
}): Promise<LlmHttpResult | null> {
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
      : `llm-${Date.now()}`;
  const timeoutMs = Math.min(120000, Math.max(1000, opts.timeoutMs ?? 60000));

  return new Promise((resolve) => {
    const timer = window.setTimeout(() => {
      cleanup();
      resolve({ ok: false, status: 0, body: "", error: "timeout" });
    }, timeoutMs + 2000);

    const onMsg = (e: MessageEvent) => {
      let data: {
        type?: string;
        id?: string;
        ok?: boolean;
        status?: number;
        body?: string;
        error?: string;
        is_base64?: boolean;
      } | null = null;
      try {
        data = typeof e.data === "string" ? JSON.parse(e.data) : e.data;
      } catch {
        return;
      }
      if (!data || data.type !== "llm_http_result" || data.id !== id) return;
      cleanup();
      resolve({
        ok: Boolean(data.ok),
        status: typeof data.status === "number" ? data.status : 0,
        body: typeof data.body === "string" ? data.body : "",
        error: data.error,
        is_base64: Boolean(data.is_base64),
      });
    };

    const cleanup = () => {
      window.clearTimeout(timer);
      w.chrome.webview.removeEventListener("message", onMsg);
    };

    w.chrome.webview.addEventListener("message", onMsg);
    try {
      w.chrome.webview.postMessage({
        type: "llm_http",
        v: 1,
        id,
        method: opts.method,
        url: opts.url,
        authorization: opts.authorization || "",
        content_type: opts.contentType || "",
        body: opts.body || "",
        timeout_ms: timeoutMs,
        base64_response: Boolean(opts.base64Response),
      });
    } catch {
      cleanup();
      resolve(null);
    }
  });
}

/** Prefer native proxy; fall back to browser fetch (dev :5180). */
export async function focusLlmHttp(opts: {
  method: "GET" | "POST" | "HEAD";
  url: string;
  headers?: Record<string, string>;
  body?: string;
  timeoutMs?: number;
  base64Response?: boolean;
}): Promise<LlmHttpResult> {
  const auth = opts.headers?.Authorization || opts.headers?.authorization || "";
  const ct = opts.headers?.["Content-Type"] || opts.headers?.["content-type"] || "";
  const native = await focusLlmNativeHttp({
    method: opts.method,
    url: opts.url,
    authorization: auth,
    contentType: ct,
    body: opts.body,
    timeoutMs: opts.timeoutMs,
    base64Response: opts.base64Response,
  });
  if (native) return native;

  try {
    const res = await fetch(opts.url, {
      method: opts.method,
      headers: opts.headers,
      body: opts.method === "GET" || opts.method === "HEAD" ? undefined : opts.body,
      signal: AbortSignal.timeout(opts.timeoutMs ?? 60000),
    });
    if (opts.base64Response) {
      const buffer = await res.arrayBuffer();
      const bytes = new Uint8Array(buffer);
      let binary = "";
      for (let i = 0; i < bytes.length; i++) {
        binary += String.fromCharCode(bytes[i]);
      }
      return { ok: res.ok, status: res.status, body: btoa(binary), is_base64: true };
    }
    const body = await res.text();
    return { ok: true, status: res.status, body };
  } catch (e) {
    return {
      ok: false,
      status: 0,
      body: "",
      error: e instanceof Error ? e.message : "unreachable",
    };
  }
}
