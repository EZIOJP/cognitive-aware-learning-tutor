import { config } from "../config";

const BASE = config.backend.apiUrl;
const TOKEN_KEY = "vocab:auth-token";

function headers(json = true): HeadersInit {
  const h: Record<string, string> = {};
  if (json) h["Content-Type"] = "application/json";
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) h.Authorization = `Bearer ${token}`;
  return h;
}

export type LogFileInfo = {
  name: string;
  path: string;
  size_bytes: number;
  modified_at: string;
  exists: boolean;
};

export type LogsListResponse = {
  logs_dir: string;
  files: LogFileInfo[];
};

export type LogTailResponse = {
  file: string;
  path: string;
  lines: number;
  content: string;
};

const FILES_CACHE_MS = 30_000;
let filesCache: { at: number; data: LogsListResponse } | null = null;
let filesInflight: Promise<LogsListResponse> | null = null;

export async function fetchLogFiles(force = false): Promise<LogsListResponse> {
  if (!force && filesCache && Date.now() - filesCache.at < FILES_CACHE_MS) {
    return filesCache.data;
  }
  if (!force && filesInflight) {
    return filesInflight;
  }

  filesInflight = (async () => {
    const res = await fetch(`${BASE}/api/system/logs`, { headers: headers(false) });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : `HTTP ${res.status}`);
    const payload = data as LogsListResponse;
    filesCache = { at: Date.now(), data: payload };
    return payload;
  })();

  try {
    return await filesInflight;
  } finally {
    filesInflight = null;
  }
}

export async function fetchLogTail(file: string, lines = 200): Promise<LogTailResponse> {
  const q = new URLSearchParams({ file, lines: String(lines) });
  const res = await fetch(`${BASE}/api/system/logs/tail?${q}`, { headers: headers(false) });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : `HTTP ${res.status}`);
  return data as LogTailResponse;
}

export function reportClientLog(payload: {
  level?: "info" | "warning" | "error";
  message: string;
  context?: string;
  url?: string;
  stack?: string;
}): void {
  void fetch(`${BASE}/api/system/logs/client`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify({
      level: payload.level ?? "error",
      message: payload.message,
      context: payload.context,
      url: payload.url ?? (typeof window !== "undefined" ? window.location.href : undefined),
      stack: payload.stack,
    }),
  }).catch(() => undefined);
}

/** Global hook — call once at app start to log uncaught UI errors to backend.log */
export function installClientErrorLogger(): void {
  if (typeof window === "undefined") return;
  window.addEventListener("error", (event) => {
    reportClientLog({
      message: event.message,
      context: `${event.filename}:${event.lineno}`,
      stack: event.error instanceof Error ? event.error.stack : undefined,
    });
  });
  window.addEventListener("unhandledrejection", (event) => {
    const reason = event.reason;
    reportClientLog({
      message: reason instanceof Error ? reason.message : String(reason),
      context: "unhandledrejection",
      stack: reason instanceof Error ? reason.stack : undefined,
    });
  });
}
