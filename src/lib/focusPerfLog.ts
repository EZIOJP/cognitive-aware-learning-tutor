/**
 * Focus perf / latency log — ring buffer + review filter for high latency & errors.
 * SoftLand/Arm feel slow mainly when enforcerNativeCmd queue serializes many polls.
 */
export type FocusPerfKind = "enforcer_cmd" | "data_fetch" | "ui";

export type FocusPerfEntry = {
  id: string;
  ts: number;
  kind: FocusPerfKind;
  name: string;
  /** Time waiting in the enforcer cmd queue before send */
  queueWaitMs?: number;
  /** End-to-end latency (includes queue wait for cmds) */
  latencyMs: number;
  /** Pipe round-trip only (after dequeue) */
  roundTripMs?: number;
  queueDepth?: number;
  ok: boolean;
  error?: string;
  detail?: string;
};

export type FocusPerfLevel = "ok" | "warn" | "high" | "critical" | "error";

/** Thresholds (ms) — tune if needed */
export const FOCUS_PERF_THRESHOLDS = {
  warnMs: 500,
  highMs: 1500,
  criticalMs: 3000,
} as const;

const RING_MAX = 200;
const REVIEW_MAX = 80;
const STORAGE_KEY = "calt:focus-perf-review";

const ring: FocusPerfEntry[] = [];
const listeners = new Set<() => void>();

function notify() {
  for (const fn of listeners) {
    try {
      fn();
    } catch {
      /* ignore */
    }
  }
}

export function subscribeFocusPerf(fn: () => void): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

export function focusPerfLevel(e: FocusPerfEntry): FocusPerfLevel {
  if (!e.ok || e.error) return "error";
  if (e.latencyMs >= FOCUS_PERF_THRESHOLDS.criticalMs) return "critical";
  if (e.latencyMs >= FOCUS_PERF_THRESHOLDS.highMs) return "high";
  if (e.latencyMs >= FOCUS_PERF_THRESHOLDS.warnMs) return "warn";
  return "ok";
}

/** Review filter: high/critical latency OR any error */
export function isFocusPerfReviewWorthy(e: FocusPerfEntry): boolean {
  const lvl = focusPerfLevel(e);
  return lvl === "high" || lvl === "critical" || lvl === "error";
}

function persistReviewSlice() {
  try {
    const review = ring.filter(isFocusPerfReviewWorthy).slice(-REVIEW_MAX);
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        updated_at: new Date().toISOString(),
        thresholds: FOCUS_PERF_THRESHOLDS,
        count: review.length,
        entries: review,
      }),
    );
  } catch {
    /* private mode / quota */
  }
}

export function recordFocusPerf(
  partial: Omit<FocusPerfEntry, "id" | "ts"> & { id?: string; ts?: number },
): FocusPerfEntry {
  const entry: FocusPerfEntry = {
    id:
      partial.id ||
      (typeof crypto !== "undefined" && "randomUUID" in crypto
        ? crypto.randomUUID()
        : `perf-${Date.now()}-${Math.random().toString(16).slice(2)}`),
    ts: partial.ts ?? Date.now(),
    kind: partial.kind,
    name: partial.name,
    queueWaitMs: partial.queueWaitMs,
    latencyMs: Math.max(0, Math.round(partial.latencyMs)),
    roundTripMs:
      partial.roundTripMs != null ? Math.max(0, Math.round(partial.roundTripMs)) : undefined,
    queueDepth: partial.queueDepth,
    ok: partial.ok,
    error: partial.error,
    detail: partial.detail,
  };

  ring.push(entry);
  if (ring.length > RING_MAX) ring.splice(0, ring.length - RING_MAX);

  const level = focusPerfLevel(entry);
  if (level !== "ok") {
    const prefix = `[FocusPerf ${level}]`;
    const q =
      entry.queueWaitMs != null ? ` queue=${entry.queueWaitMs}ms` : "";
    const rt =
      entry.roundTripMs != null ? ` rt=${entry.roundTripMs}ms` : "";
    const err = entry.error ? ` err=${entry.error}` : "";
    // eslint-disable-next-line no-console
    console.warn(
      `${prefix} ${entry.kind} ${entry.name} latency=${entry.latencyMs}ms${q}${rt}${err}`,
      entry.detail || "",
    );
    persistReviewSlice();
  }

  notify();
  return entry;
}

export function getFocusPerfRing(): FocusPerfEntry[] {
  return [...ring];
}

/** High latency + errors only (for review UI / export). */
export function getFocusPerfReview(): FocusPerfEntry[] {
  return ring.filter(isFocusPerfReviewWorthy);
}

export function clearFocusPerfLog(): void {
  ring.length = 0;
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    /* ignore */
  }
  notify();
}

export function focusPerfSummary(): {
  total: number;
  review: number;
  errors: number;
  high: number;
  p50: number;
  p95: number;
  slowest: FocusPerfEntry | null;
} {
  const all = [...ring];
  const review = all.filter(isFocusPerfReviewWorthy);
  const errors = all.filter((e) => !e.ok || Boolean(e.error)).length;
  const high = all.filter((e) => {
    const l = focusPerfLevel(e);
    return l === "high" || l === "critical";
  }).length;
  const sorted = all.map((e) => e.latencyMs).sort((a, b) => a - b);
  const pct = (p: number) => {
    if (!sorted.length) return 0;
    const i = Math.min(sorted.length - 1, Math.floor((p / 100) * sorted.length));
    return sorted[i] ?? 0;
  };
  let slowest: FocusPerfEntry | null = null;
  for (const e of all) {
    if (!slowest || e.latencyMs > slowest.latencyMs) slowest = e;
  }
  return {
    total: all.length,
    review: review.length,
    errors,
    high,
    p50: pct(50),
    p95: pct(95),
    slowest,
  };
}

export async function timedFocusFetch(
  name: string,
  input: RequestInfo | URL,
  init?: RequestInit,
): Promise<Response> {
  const t0 = performance.now();
  try {
    const res = await fetch(input, init);
    recordFocusPerf({
      kind: "data_fetch",
      name,
      latencyMs: performance.now() - t0,
      ok: res.ok,
      error: res.ok ? undefined : `http_${res.status}`,
      detail: typeof input === "string" ? input : String(input),
    });
    return res;
  } catch (e) {
    recordFocusPerf({
      kind: "data_fetch",
      name,
      latencyMs: performance.now() - t0,
      ok: false,
      error: e instanceof Error ? e.message : String(e),
      detail: typeof input === "string" ? input : String(input),
    });
    throw e;
  }
}
