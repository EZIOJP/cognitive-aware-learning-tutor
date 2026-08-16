/**
 * Softens lag between wearables → life → hub → widgets and tracker → hub.
 * One watcher in AppShell; widgets listen for hub:refresh / calt:pipeline.
 */

import { resolveApiUrl } from "./resolveBackendUrl";

export const HUB_REFRESH_EVENT = "hub:refresh";
export const PIPELINE_EVENT = "calt:pipeline";

export type PipelineSource =
  | "wearables"
  | "tracker"
  | "hub"
  | "nutrition"
  | "manual"
  | "poll";

const TOKEN_KEY = "vocab:auth-token";
const WEARABLE_TOKEN_KEY = "calt:wearables:token";
const DEFAULT_WEARABLE_TOKEN = "calt-local-wearables";

function authHeaders(): HeadersInit {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  try {
    const token = localStorage.getItem(TOKEN_KEY);
    if (token) headers.Authorization = `Bearer ${token}`;
  } catch {
    /* ignore */
  }
  return headers;
}

function wearableHeaders(): HeadersInit {
  let t = DEFAULT_WEARABLE_TOKEN;
  try {
    t = localStorage.getItem(WEARABLE_TOKEN_KEY) || DEFAULT_WEARABLE_TOKEN;
  } catch {
    /* ignore */
  }
  return { Authorization: `Bearer ${t}`, "Content-Type": "application/json" };
}

export function notifyPipeline(source: PipelineSource, detail?: Record<string, unknown>) {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent(HUB_REFRESH_EVENT, { detail: { source, ...detail } }));
  window.dispatchEvent(new CustomEvent(PIPELINE_EVENT, { detail: { source, ...detail } }));
}

let watchStarted = false;
let lastFingerprint = "";

async function fingerprint(): Promise<string> {
  const base = resolveApiUrl().replace(/\/$/, "");
  const parts: string[] = [];

  try {
    const hubRes = await fetch(`${base}/api/hub/daily/today`, { headers: authHeaders() });
    if (hubRes.ok) {
      const h = await hubRes.json();
      parts.push(
        `h:${h.date}:${h.sleep_minutes ?? 0}:${h.productive_minutes ?? 0}:${(h.segments || []).length}`,
      );
    }
  } catch {
    /* ignore */
  }

  try {
    const wRes = await fetch(`${base}/api/wearables/zepp/status`, { headers: wearableHeaders() });
    if (wRes.ok) {
      const w = await wRes.json();
      const ls = w.last_sync || {};
      parts.push(
        `w:${ls.last_ingest_at || ""}:${ls.last_sleep_hours ?? ""}:${ls.last_steps ?? ""}:${ls.updated_at || ""}`,
      );
    }
  } catch {
    /* ignore */
  }

  try {
    const tRes = await fetch(`${base}/api/behavior/tracker-health`, { headers: authHeaders() });
    if (tRes.ok) {
      const t = await tRes.json();
      parts.push(`t:${t.last_event_at || t.status || ""}:${t.pid || ""}`);
    }
  } catch {
    /* ignore */
  }

  return parts.join("|");
}

/**
 * Call once from AppShell. Polls lightly while the tab is visible and
 * fires hub:refresh when any upstream fingerprint changes.
 */
export function startDataPipelineWatch() {
  if (typeof window === "undefined" || watchStarted) return () => {};
  watchStarted = true;

  let timer: ReturnType<typeof setInterval> | undefined;
  let cancelled = false;

  const tick = async () => {
    if (cancelled) return;
    if (typeof document !== "undefined" && document.visibilityState === "hidden") return;
    try {
      const next = await fingerprint();
      if (!next) return;
      if (lastFingerprint && next !== lastFingerprint) {
        notifyPipeline("poll", { fingerprint: next });
      }
      lastFingerprint = next;
    } catch {
      /* ignore */
    }
  };

  const arm = () => {
    if (timer) clearInterval(timer);
    // Visible: snappy. Hidden: pause (tick no-ops).
    timer = setInterval(() => void tick(), 12_000);
    void tick();
  };

  arm();
  const onVis = () => {
    if (document.visibilityState === "visible") void tick();
  };
  document.addEventListener("visibilitychange", onVis);

  return () => {
    cancelled = true;
    watchStarted = false;
    if (timer) clearInterval(timer);
    document.removeEventListener("visibilitychange", onVis);
  };
}
