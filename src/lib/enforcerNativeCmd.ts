/**
 * Focus shell bridge: chrome.webview.postMessage → calt_focus → enforcer named pipe.
 * Returns null when not running inside calt_focus WebView2 (browser Study app).
 *
 * Commands are serialized — overlapping polls were freezing the UI when Settings
 * (WriteGate + FocusControlPanel) hammered the pipe every few seconds.
 *
 * Latency is logged via focusPerfLog (queue wait + round-trip); high latency/errors
 * are filtered into the review buffer (Settings → Tools).
 */

import { recordFocusPerf } from "./focusPerfLog";

type EnforcerCmdResult = {
  ok?: boolean;
  id?: string;
  error?: string;
  gateway_seq?: number;
  softland_enabled?: boolean;
  free_until?: string | null;
  incubation_until?: string | null;
  reward_day_active?: boolean;
  earned_ledger_seconds?: number;
  type?: string;
  [key: string]: unknown;
};

function hasWebViewBridge(): boolean {
  const w = window as Window & {
    chrome?: { webview?: { postMessage: (m: unknown) => void; addEventListener: Function } };
  };
  return Boolean(w.chrome?.webview?.postMessage);
}

export function isFocusEnforcerBridgeAvailable(): boolean {
  return hasWebViewBridge();
}

type QueueItem = {
  op: string;
  payload: Record<string, unknown>;
  timeoutMs: number;
  enqueuedAt: number;
  resolve: (v: EnforcerCmdResult | null) => void;
};

let queue: QueueItem[] = [];
let draining = false;

async function runOne(item: QueueItem): Promise<void> {
  if (!hasWebViewBridge()) {
    item.resolve(null);
    return;
  }
  const w = window as Window & {
    chrome: {
      webview: {
        postMessage: (m: unknown) => void;
        addEventListener: (type: string, fn: (e: MessageEvent) => void) => void;
        removeEventListener: (type: string, fn: (e: MessageEvent) => void) => void;
      };
    };
  };

  const queueWaitMs = performance.now() - item.enqueuedAt;
  const id =
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : `cmd-${Date.now()}-${Math.random().toString(16).slice(2)}`;

  const tSend = performance.now();
  const result = await new Promise<EnforcerCmdResult | null>((resolve) => {
    const timer = window.setTimeout(() => {
      cleanup();
      resolve({ ok: false, id, error: "timeout" });
    }, item.timeoutMs);

    const onMsg = (e: MessageEvent) => {
      let data: EnforcerCmdResult | null = null;
      try {
        data = typeof e.data === "string" ? JSON.parse(e.data) : (e.data as EnforcerCmdResult);
      } catch {
        return;
      }
      if (!data || data.type !== "enforcer_cmd_result") return;
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
      type: "enforcer_cmd",
      v: 1,
      id,
      op: item.op,
      payload: item.payload,
    });
  });

  const roundTripMs = performance.now() - tSend;
  const latencyMs = performance.now() - item.enqueuedAt;
  const err =
    !result
      ? "no_bridge_result"
      : result.error
        ? String(result.error)
        : result.ok === false
          ? "ok_false"
          : undefined;

  recordFocusPerf({
    kind: "enforcer_cmd",
    name: item.op,
    queueWaitMs,
    roundTripMs,
    latencyMs,
    queueDepth: queue.length,
    ok: Boolean(result && result.ok !== false && !result.error),
    error: err,
    detail: err ? JSON.stringify(result).slice(0, 240) : undefined,
  });

  item.resolve(result);
}

async function drainQueue(): Promise<void> {
  if (draining) return;
  draining = true;
  try {
    while (queue.length > 0) {
      const next = queue.shift();
      if (!next) break;
      await runOne(next);
    }
  } finally {
    draining = false;
    if (queue.length > 0) void drainQueue();
  }
}

/** Collapse duplicate status probes waiting in queue (keeps latest). */
function coalesceStatusProbes(): void {
  const STATUS_OPS = new Set(["status.snapshot", "day.status", "day.loop_snapshot", "reward.status"]);
  const seen = new Set<string>();
  const kept: QueueItem[] = [];
  for (let i = queue.length - 1; i >= 0; i--) {
    const q = queue[i];
    if (STATUS_OPS.has(q.op)) {
      if (seen.has(q.op)) {
        q.resolve({ ok: false, error: "coalesced" });
        recordFocusPerf({
          kind: "enforcer_cmd",
          name: q.op,
          latencyMs: performance.now() - q.enqueuedAt,
          queueWaitMs: performance.now() - q.enqueuedAt,
          ok: false,
          error: "coalesced",
          detail: "duplicate status probe dropped from queue",
        });
        continue;
      }
      seen.add(q.op);
    }
    kept.push(q);
  }
  queue = kept.reverse();
}

export async function enforcerNativeCmd(
  op: string,
  payload: Record<string, unknown> = {},
  timeoutMs = 5000,
): Promise<EnforcerCmdResult | null> {
  if (!hasWebViewBridge()) return null;
  return new Promise((resolve) => {
    queue.push({ op, payload, timeoutMs, enqueuedAt: performance.now(), resolve });
    coalesceStatusProbes();
    // Cap backlog: drop oldest status probes so UI writes stay responsive.
    if (queue.length > 8) {
      const kept: QueueItem[] = [];
      for (const q of queue) {
        if (kept.length >= 6 && (q.op === "status.snapshot" || q.op === "day.status")) {
          q.resolve({ ok: false, error: "queue_dropped" });
          recordFocusPerf({
            kind: "enforcer_cmd",
            name: q.op,
            latencyMs: performance.now() - q.enqueuedAt,
            queueWaitMs: performance.now() - q.enqueuedAt,
            queueDepth: queue.length,
            ok: false,
            error: "queue_dropped",
          });
          continue;
        }
        kept.push(q);
      }
      queue = kept;
    }
    void drainQueue();
  });
}
