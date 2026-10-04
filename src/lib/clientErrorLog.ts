/** Local ring-buffer error log for Focus + Study (no SaaS). */

export type ClientErrorEntry = {
  at: string;
  level: "info" | "warning" | "error";
  message: string;
  context?: string;
  url?: string;
  stack?: string;
};

const STORAGE_KEY = "calt:client-error-log";
const MAX_ENTRIES = 80;

let memory: ClientErrorEntry[] = loadFromStorage();
let installed = false;
let extraSink: ((entry: ClientErrorEntry) => void) | null = null;

function loadFromStorage(): ClientErrorEntry[] {
  if (typeof localStorage === "undefined") return [];
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(
      (e): e is ClientErrorEntry =>
        !!e &&
        typeof e === "object" &&
        typeof (e as ClientErrorEntry).message === "string" &&
        typeof (e as ClientErrorEntry).at === "string",
    );
  } catch {
    return [];
  }
}

function persist(): void {
  if (typeof localStorage === "undefined") return;
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(memory.slice(-MAX_ENTRIES)));
  } catch {
    /* quota / private mode — keep memory only */
  }
}

/** Optional sink (e.g. Study backend POST) — must not call pushClientError again. */
export function setClientErrorSink(sink: ((entry: ClientErrorEntry) => void) | null): void {
  extraSink = sink;
}

export function pushClientError(entry: Omit<ClientErrorEntry, "at"> & { at?: string }): void {
  const full: ClientErrorEntry = {
    at: entry.at ?? new Date().toISOString(),
    level: entry.level ?? "error",
    message: String(entry.message || "unknown").slice(0, 2000),
    context: entry.context?.slice(0, 500),
    url: entry.url?.slice(0, 500),
    stack: entry.stack?.slice(0, 4000),
  };
  memory = [...memory.slice(-(MAX_ENTRIES - 1)), full];
  persist();
  if (typeof console !== "undefined") {
    const label = `[CALT ${full.level}] ${full.context ?? ""} ${full.message}`.trim();
    if (full.level === "error") console.error(label, full.stack ?? "");
    else if (full.level === "warning") console.warn(label);
    else console.info(label);
  }
  try {
    extraSink?.(full);
  } catch {
    /* sink must never break logging */
  }
}

export function getClientErrorLog(): ClientErrorEntry[] {
  return memory.slice();
}

export function clearClientErrorLog(): void {
  memory = [];
  if (typeof localStorage !== "undefined") {
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch {
      /* ignore */
    }
  }
}

export function formatClientErrorLog(entries = getClientErrorLog()): string {
  if (!entries.length) return "(no client errors recorded)";
  return entries
    .map((e) => {
      const head = `[${e.at}] ${e.level.toUpperCase()} ${e.context ? `(${e.context}) ` : ""}${e.message}`;
      const url = e.url ? `\n  url: ${e.url}` : "";
      const stack = e.stack ? `\n  ${e.stack.replace(/\n/g, "\n  ")}` : "";
      return head + url + stack;
    })
    .join("\n\n");
}

export async function copyClientErrorLog(): Promise<{ ok: boolean; count: number; error?: string }> {
  const text = formatClientErrorLog();
  const count = memory.length;
  try {
    if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return { ok: true, count };
    }
  } catch (err) {
    return { ok: false, count, error: err instanceof Error ? err.message : String(err) };
  }
  /* Fallback: select a temporary textarea */
  try {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.style.position = "fixed";
    ta.style.left = "-9999px";
    document.body.appendChild(ta);
    ta.select();
    document.execCommand("copy");
    document.body.removeChild(ta);
    return { ok: true, count };
  } catch (err) {
    return { ok: false, count, error: err instanceof Error ? err.message : String(err) };
  }
}

/** Window + rejection hooks — safe to call once from main.tsx */
export function installClientErrorRingBuffer(): void {
  if (typeof window === "undefined" || installed) return;
  installed = true;
  window.addEventListener("error", (event) => {
    pushClientError({
      level: "error",
      message: event.message || "window error",
      context: `${event.filename || "?"}:${event.lineno ?? 0}`,
      url: window.location.href,
      stack: event.error instanceof Error ? event.error.stack : undefined,
    });
  });
  window.addEventListener("unhandledrejection", (event) => {
    const reason = event.reason;
    pushClientError({
      level: "error",
      message: reason instanceof Error ? reason.message : String(reason),
      context: "unhandledrejection",
      url: window.location.href,
      stack: reason instanceof Error ? reason.stack : undefined,
    });
  });
  // Dev/smoke helpers — Focus ⋯ menu also copies; these are for console/debug.
  const w = window as Window & {
    __caltCopyErrorLog?: typeof copyClientErrorLog;
    __caltGetErrorLog?: typeof getClientErrorLog;
    __caltClearErrorLog?: typeof clearClientErrorLog;
  };
  w.__caltCopyErrorLog = copyClientErrorLog;
  w.__caltGetErrorLog = getClientErrorLog;
  w.__caltClearErrorLog = clearClientErrorLog;
}
