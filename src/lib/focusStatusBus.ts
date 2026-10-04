/**
 * Phase A — shared Focus status bus (ultra-low-latency reads).
 *
 * One ticker refreshes mirrors (+ rare pipe reconcile). Panels subscribe instead of
 * each hammering enforcerNativeCmd. Writes still use the pipe directly; call
 * invalidateFocusStatusBus() after mutations.
 *
 * Phase B hook: optional sidecar http://127.0.0.1:18765/snapshot
 * Phase C hook: window message { type: "status_tick", ... }
 */
import {
  fetchDayLoopMirror,
  fetchDayRollupMirror,
  fetchEnforcerStatusMirror,
  type DayRollupMirror,
  type EnforcerStatusMirror,
} from "../api/focusMirrors";
import type { DayLoopSnapshot } from "../api/dayLoopClient";
import { isFocusDesktopShell } from "../utils/focusDesktopShell";
import { focusDataUrl } from "../utils/focusDataUrl";
import { timedFocusFetch } from "./focusPerfLog";
import { isFocusEnforcerBridgeAvailable, enforcerNativeCmd } from "./enforcerNativeCmd";
import { recordFocusPerf } from "./focusPerfLog";

export type SoftlandPolicySnap = {
  softland_enabled?: boolean;
  updated_at?: string;
  site_rules?: {
    allow_extra?: string[];
    watch_extra?: string[];
    block_extra?: string[];
  };
  runtime?: {
    free_until?: string | null;
    incubation_until?: string | null;
    bedtime_active?: boolean;
  };
  goals?: Record<string, unknown>;
};

export type FocusStatusSnapshot = {
  updatedAt: number;
  softland: SoftlandPolicySnap | null;
  enforcerStatus: EnforcerStatusMirror | null;
  dayRollup: DayRollupMirror | null;
  dayLoop: DayLoopSnapshot | null;
  /** true = pipe answered recently; false = down; null = not probed */
  pipeOk: boolean | null;
  source: "mirrors" | "mirrors+pipe" | "sidecar" | "push" | "idle";
};

type Listener = (snap: FocusStatusSnapshot) => void;

/** Mirror file reads are cheap — keep UI snappy; enforcer DB sync is 1 min. */
const TICK_MS = 2500;
/** Pipe reachability only — never used to load SoftLand/plan/bible UI state. */
const PIPE_RECONCILE_EVERY_MS = 600_000;
const PUSH_HEALTHY_MS = 120_000;
const SIDECAR_URL = "http://127.0.0.1:18765/snapshot";

let snap: FocusStatusSnapshot = {
  updatedAt: 0,
  softland: null,
  enforcerStatus: null,
  dayRollup: null,
  dayLoop: null,
  pipeOk: null,
  source: "idle",
};

const listeners = new Set<Listener>();
let timer: number | null = null;
let ticking = false;
let pipeInFlight = false;
let lastPipeAt = 0;
let pushHealthyUntil = 0;

function emit() {
  for (const fn of listeners) {
    try {
      fn(snap);
    } catch {
      /* ignore */
    }
  }
}

function setSnap(next: FocusStatusSnapshot) {
  snap = next;
  emit();
}

async function trySidecar(): Promise<Partial<FocusStatusSnapshot> | null> {
  try {
    const t0 = performance.now();
    const ctrl = new AbortController();
    const to = window.setTimeout(() => ctrl.abort(), 400);
    const res = await fetch(SIDECAR_URL, { cache: "no-store", signal: ctrl.signal });
    window.clearTimeout(to);
    if (!res.ok) return null;
    const j = (await res.json()) as Partial<FocusStatusSnapshot> & { ok?: boolean };
    recordFocusPerf({
      kind: "data_fetch",
      name: "status_sidecar",
      latencyMs: performance.now() - t0,
      ok: true,
    });
    return { ...j, source: "sidecar" };
  } catch {
    return null;
  }
}

async function loadSoftland(): Promise<SoftlandPolicySnap | null> {
  if (!isFocusDesktopShell()) return null;
  try {
    const res = await timedFocusFetch("softland_policy.json", focusDataUrl("softland_policy.json"), {
      cache: "no-store",
    });
    if (!res.ok) return null;
    return (await res.json()) as SoftlandPolicySnap;
  } catch {
    return null;
  }
}

function localYmd(): string {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

/** Prefer SoftLand goals mirror for bible/plan flags — updates before the next pipe reconcile. */
function syncDayLoopFromSoftland(
  dayLoop: DayLoopSnapshot | null,
  softland: SoftlandPolicySnap | null,
): DayLoopSnapshot | null {
  if (!dayLoop || !softland?.goals) return dayLoop;
  const goals = softland.goals;
  const today = localYmd();
  const bibleFlag = Boolean(goals.bible_done);
  const bibleDate = typeof goals.bible_done_for_date === "string" ? goals.bible_done_for_date : "";
  const bibleDone = bibleFlag && bibleDate === today;
  const planFlag = Boolean(goals.plan_confirmed);
  const planDate =
    typeof goals.plan_confirmed_for_date === "string" ? goals.plan_confirmed_for_date : "";
  const planConfirmed = planFlag && planDate === today;
  const loopDate = typeof dayLoop.date === "string" ? dayLoop.date : "";
  const dateOk = !loopDate || loopDate === today;
  const next = {
    ...dayLoop,
    bible_done: dateOk ? bibleDone : false,
    plan_confirmed: dateOk ? planConfirmed : false,
    ...(loopDate && loopDate !== today ? { date: today } : null),
  };
  if (
    dayLoop.bible_done === next.bible_done &&
    dayLoop.plan_confirmed === next.plan_confirmed &&
    loopDate === next.date
  ) {
    return dayLoop;
  }
  return next;
}

async function tick(forcePipe = false): Promise<void> {
  if (ticking) return;
  if (typeof document !== "undefined" && document.visibilityState === "hidden") return;
  ticking = true;
  const t0 = performance.now();
  try {
    // Phase C: if push is healthy, mirrors-only light refresh
    const pushLive = Date.now() < pushHealthyUntil;

    // Phase B: sidecar first
    if (!forcePipe) {
      const side = await trySidecar();
      if (side && (side.enforcerStatus || side.softland)) {
        setSnap({
          updatedAt: Date.now(),
          softland: (side.softland as SoftlandPolicySnap) || snap.softland,
          enforcerStatus: (side.enforcerStatus as EnforcerStatusMirror) || snap.enforcerStatus,
          dayRollup: (side.dayRollup as DayRollupMirror) || snap.dayRollup,
          dayLoop: (side.dayLoop as DayLoopSnapshot) || snap.dayLoop,
          pipeOk: side.pipeOk ?? snap.pipeOk,
          source: "sidecar",
        });
        recordFocusPerf({
          kind: "ui",
          name: "focusStatusBus.tick",
          latencyMs: performance.now() - t0,
          ok: true,
          detail: "sidecar",
        });
        return;
      }
    }

    const [softland, enforcerStatus, dayRollup, dayLoopMir] = await Promise.all([
      loadSoftland(),
      fetchEnforcerStatusMirror(),
      fetchDayRollupMirror(),
      fetchDayLoopMirror(),
    ]);

    let dayLoop = snap.dayLoop;
    if (dayLoopMir && typeof dayLoopMir === "object" && dayLoopMir.date) {
      const loop = dayLoopMir as unknown as DayLoopSnapshot;
      dayLoop = { ...loop, tasks: Array.isArray(loop.tasks) ? loop.tasks : [] };
    }
    let pipeOk = snap.pipeOk;
    let source: FocusStatusSnapshot["source"] = pushLive ? "push" : "mirrors";

    // Optional reachability probe only — UI data comes from mirrors above.
    const needPipe =
      !pipeInFlight &&
      (forcePipe ||
        (!pushLive &&
          isFocusEnforcerBridgeAvailable() &&
          Date.now() - lastPipeAt > PIPE_RECONCILE_EVERY_MS));

    if (needPipe) {
      pipeInFlight = true;
      lastPipeAt = Date.now();
      try {
        const r = await enforcerNativeCmd("status.snapshot", {}, 1500);
        if (r && r.ok !== false && !r.error) {
          pipeOk = true;
          source = "mirrors+pipe";
        } else if (r?.error === "timeout" || r?.error === "queue_dropped") {
          pipeOk = false;
        } else if (r) {
          pipeOk = r.ok !== false;
        }
      } catch {
        pipeOk = false;
      } finally {
        pipeInFlight = false;
      }
    } else if (enforcerStatus?.owns || enforcerStatus?.lock_present) {
      const age = enforcerStatus.updated_at
        ? Date.now() - Date.parse(enforcerStatus.updated_at)
        : Infinity;
      if (Number.isFinite(age) && age < 45_000) pipeOk = true;
    }

    setSnap({
      updatedAt: Date.now(),
      softland,
      enforcerStatus,
      dayRollup,
      dayLoop: (() => {
        let loop = syncDayLoopFromSoftland(dayLoop, softland);
        if (!loop) return loop;
        const rollMin =
          typeof dayRollup?.productive_minutes === "number"
            ? Math.floor(dayRollup.productive_minutes)
            : typeof dayRollup?.productive_seconds === "number"
              ? Math.floor(dayRollup.productive_seconds / 60)
              : null;
        if (rollMin == null) return loop;
        const loopMin = loop.tracked_productive_minutes;
        if (typeof loopMin === "number" && loopMin >= rollMin) return loop;
        return { ...loop, tracked_productive_minutes: rollMin };
      })(),
      pipeOk,
      source,
    });

    recordFocusPerf({
      kind: "ui",
      name: "focusStatusBus.tick",
      latencyMs: performance.now() - t0,
      ok: true,
      detail: source,
    });
  } finally {
    ticking = false;
  }
}

function ensureTimer() {
  if (timer != null) return;
  if (typeof window === "undefined") return;
  // Mirrors first — do not force a pipe hit on every subscriber mount (lag).
  void tick(false);
  timer = window.setInterval(() => void tick(false), TICK_MS);
}

function stopTimerIfIdle() {
  if (listeners.size > 0) return;
  if (timer != null) {
    window.clearInterval(timer);
    timer = null;
  }
}

/** Subscribe; starts the shared ticker while anyone is listening. */
export function subscribeFocusStatus(fn: Listener): () => void {
  listeners.add(fn);
  fn(snap);
  ensureTimer();
  return () => {
    listeners.delete(fn);
    stopTimerIfIdle();
  };
}

export function getFocusStatusSnapshot(): FocusStatusSnapshot {
  return snap;
}

/**
 * Force immediate mirror refresh (e.g. after SoftLand/Arm write).
 * Default is mirrors-only — pipe probe is optional (`pipe: true`).
 */
export function invalidateFocusStatusBus(opts?: { pipe?: boolean }): void {
  void tick(opts?.pipe === true);
}

let lastPushFp = "";

/** Phase C: Focus native shell can push ticks here. */
export function ingestFocusStatusPush(partial: Partial<FocusStatusSnapshot> & { keepalive?: boolean }): void {
  pushHealthyUntil = Date.now() + PUSH_HEALTHY_MS;
  if (partial.keepalive) {
    return;
  }
  // Skip identical pushes — native used to fire every 2.5s and re-render the whole shell.
  const fp = JSON.stringify({
    e: partial.enforcerStatus ?? null,
    s: partial.softland ?? null,
    l: partial.dayLoop ?? null,
  });
  if (fp === lastPushFp) {
    return;
  }
  lastPushFp = fp;
  setSnap({
    ...snap,
    ...partial,
    updatedAt: Date.now(),
    source: "push",
  });
}

/** Wire once from App shell — listens for C++ status_tick messages. */
export function installFocusStatusPushListener(): () => void {
  if (typeof window === "undefined") return () => {};
  const onMsg = (e: MessageEvent) => {
    let data: { type?: string; [k: string]: unknown } | null = null;
    try {
      data = typeof e.data === "string" ? JSON.parse(e.data) : (e.data as typeof data);
    } catch {
      return;
    }
    if (!data || data.type !== "status_tick") return;
    if (data.keepalive) {
      ingestFocusStatusPush({ keepalive: true, pipeOk: true });
      return;
    }
    ingestFocusStatusPush({
      enforcerStatus: (data.enforcer_status as EnforcerStatusMirror) || snap.enforcerStatus,
      softland: (data.softland as SoftlandPolicySnap) || snap.softland,
      dayLoop: (data.loop as DayLoopSnapshot) || snap.dayLoop,
      pipeOk: true,
    });
  };
  window.addEventListener("message", onMsg);
  const w = window as Window & {
    chrome?: { webview?: { addEventListener: (t: string, fn: (e: MessageEvent) => void) => void; removeEventListener: (t: string, fn: (e: MessageEvent) => void) => void } };
  };
  w.chrome?.webview?.addEventListener?.("message", onMsg);
  return () => {
    window.removeEventListener("message", onMsg);
    w.chrome?.webview?.removeEventListener?.("message", onMsg);
  };
}
