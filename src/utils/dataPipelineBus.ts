/**
 * Softens lag between tracker → hub → widgets.
 * Wearables are manual Dump→Send only (notifyPipeline("wearables") after Refresh).
 * One BroadcastChannel leader across tabs; never hammer hub/daily or zepp/status.
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
const POLL_MS = 120_000;
const CHANNEL = "calt-pipeline-watch";

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

export function notifyPipeline(source: PipelineSource, detail?: Record<string, unknown>) {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent(HUB_REFRESH_EVENT, { detail: { source, ...detail } }));
  window.dispatchEvent(new CustomEvent(PIPELINE_EVENT, { detail: { source, ...detail } }));
}

let watchStarted = false;
let lastFingerprint = "";
let tickInFlight = false;

/** Cheap fingerprint — avoid hub/daily rebuild + voice-notes directory walks. */
async function fingerprint(): Promise<string> {
  const base = resolveApiUrl().replace(/\/$/, "");
  try {
    const tRes = await fetch(`${base}/api/behavior/tracker-health`, {
      headers: authHeaders(),
      signal: AbortSignal.timeout(8_000),
    });
    if (tRes.ok) {
      const t = await tRes.json();
      return `t:${t.last_event_at || t.status || ""}:${t.sessions_today ?? ""}:${t.pid || ""}`;
    }
  } catch {
    /* ignore */
  }
  return "";
}

/**
 * Call once from AppShell. Only the BroadcastChannel leader polls;
 * followers react to hub:refresh from the leader (and local events).
 */
export function startDataPipelineWatch() {
  if (typeof window === "undefined" || watchStarted) return () => {};
  watchStarted = true;

  let timer: ReturnType<typeof setInterval> | undefined;
  let cancelled = false;
  let isLeader = false;
  let bc: BroadcastChannel | null = null;

  try {
    bc = new BroadcastChannel(CHANNEL);
  } catch {
    bc = null;
  }

  const claimLeader = () => {
    isLeader = true;
    try {
      bc?.postMessage({ type: "leader" });
    } catch {
      /* ignore */
    }
  };

  // First tab wins; late tabs yield when they hear a leader.
  claimLeader();
  if (bc) {
    bc.onmessage = (ev) => {
      const msg = ev.data;
      if (msg?.type === "leader" && !isLeader) {
        /* already follower */
      } else if (msg?.type === "leader" && isLeader) {
        // Another tab also claims — yield if we are older? Keep simple: random yield
        if (Math.random() < 0.5) isLeader = false;
      } else if (msg?.type === "fingerprint" && typeof msg.value === "string") {
        if (lastFingerprint && msg.value !== lastFingerprint) {
          notifyPipeline("poll", { fingerprint: msg.value, via: "bc" });
        }
        lastFingerprint = msg.value;
      }
    };
  }

  const tick = async () => {
    if (cancelled || !isLeader) return;
    if (typeof document !== "undefined" && document.visibilityState === "hidden") return;
    if (tickInFlight) return;
    tickInFlight = true;
    try {
      const next = await fingerprint();
      if (!next) return;
      if (lastFingerprint && next !== lastFingerprint) {
        notifyPipeline("poll", { fingerprint: next });
      }
      lastFingerprint = next;
      try {
        bc?.postMessage({ type: "fingerprint", value: next });
      } catch {
        /* ignore */
      }
    } catch {
      /* ignore */
    } finally {
      tickInFlight = false;
    }
  };

  const arm = () => {
    if (timer) clearInterval(timer);
    timer = setInterval(() => void tick(), POLL_MS);
    void tick();
  };

  arm();
  const onVis = () => {
    if (document.visibilityState === "visible" && isLeader) void tick();
  };
  document.addEventListener("visibilitychange", onVis);

  return () => {
    cancelled = true;
    watchStarted = false;
    if (timer) clearInterval(timer);
    document.removeEventListener("visibilitychange", onVis);
    try {
      bc?.close();
    } catch {
      /* ignore */
    }
  };
}
