import { resolveApiUrl } from "../utils/resolveBackendUrl";
import { planEditsOpen } from "../lib/dayGate";
import { getFocusStatusSnapshot, isFreeDay } from "../lib/focusStatusBus";
import { enforcerNativeCmd, isFocusEnforcerBridgeAvailable } from "../lib/enforcerNativeCmd";
import { agentDebugLog } from "../lib/agentDebugLog";
import { isFocusDesktopShell } from "../utils/focusDesktopShell";
import { focusDataUrl } from "../utils/focusDataUrl";

const TOKEN_KEY = "vocab:auth-token";

/**
 * Focus sole Productivity door — plan mutations go through the enforcer pipe.
 * Reads soft-fail to `"offline"` when the WebView bridge is missing (design host /
 * enforcer down) so Analytics never hard-depends on Study `:8000`.
 */
function tryPlanTransport(): "gateway" | "http" | "offline" {
  if (!isFocusDesktopShell()) return "http";
  if (!isFocusEnforcerBridgeAvailable()) return "offline";
  return "gateway";
}

/** Write / mutate path — still throws when Focus bridge is missing. */
function planTransport(): "gateway" | "http" {
  const t = tryPlanTransport();
  if (t === "offline") throw new Error("enforcer_unreachable");
  return t;
}

function dayIsoLocal(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function emptyAdherence(day: string): AdherenceSummary {
  return {
    day,
    planned_minutes: 0,
    actual_minutes: 0,
    productive_minutes: 0,
    effective_focus_minutes: 0,
    adherence_pct: null,
    block_count: 0,
    session_count: 0,
  };
}

/** Study-HTTP-only features: fail fast in Focus (no hung :8000 fetch). */
function focusNeedsStudyApi(feature: string): never {
  throw new Error(
    `${feature} needs Study API (tray → Start API) — not available offline in Focus yet`,
  );
}

async function planGateway(
  op: string,
  payload: Record<string, unknown> = {},
  timeoutMs = 8000,
  /** Hot-path reads (list/overlay) — one short try; mutations keep retries. */
  retries = 3,
): Promise<Record<string, unknown>> {
  const edits = new Set([
    "plan.upsert",
    "plan.delete",
    "plan.clear_day",
    "plan.import_from_date",
    "routine.upsert",
    "routine.delete",
    "routine.apply",
    "plan.roll_forward",
  ]);
  if (edits.has(op) && isFocusDesktopShell()) {
    const status = getFocusStatusSnapshot();
    if (!planEditsOpen(status, isFreeDay(status.softland))) {
      throw new Error("free_day_required");
    }
  }
  let last: Record<string, unknown> | null = null;
  const attempts = Math.max(1, retries);
  for (let attempt = 0; attempt < attempts; attempt++) {
    const res = await enforcerNativeCmd(op, payload, timeoutMs);
    if (res && res.ok !== false && !res.error) return res as Record<string, unknown>;
    if (res?.error && res.error !== "timeout" && res.error !== "queue_dropped" && res.error !== "coalesced") {
      throw new Error(String(res.error));
    }
    last = res as Record<string, unknown> | null;
    if (attempt + 1 < attempts) {
      await new Promise((r) => window.setTimeout(r, 120 + attempt * 150));
    }
  }
  if (!last) throw new Error("enforcer_unreachable");
  throw new Error(String(last.error || "enforcer_unreachable"));
}

function authHeaders(): HeadersInit {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) headers.Authorization = `Bearer ${token}`;
  return headers;
}

export type PlannerBlockStatus = "scheduled" | "in_progress" | "done" | "rolled" | "cancelled";

export interface PlannerBlock {
  id: number;
  title: string;
  category: string;
  start_at: string;
  end_at: string;
  planned_minutes: number;
  planned_label?: string;
  remaining_minutes: number;
  remaining_label?: string;
  status: PlannerBlockStatus;
  rolled_from_id: number | null;
  roll_count: number;
  task_id: number | null;
  color: string | null;
  created_at: string | null;
}

export interface ActualSession {
  session_id: string;
  start_time: string | null;
  end_time: string | null;
  source: string;
  category?: string | null;
  productivity_score?: number | null;
  task_id?: number | null;
  app_name?: string | null;
  window_title?: string | null;
  /** Domain / site label (extension URL sessions, desktop browser). */
  site?: string | null;
}

/** Backend hour_slices from GET /api/planner/overlay/actual */
export type OverlayHourSlice = import("../components/productivity/hourSliceTypes").HourSlice;

export type ActualOverlayPayload = {
  sessions: ActualSession[];
  hour_slices: OverlayHourSlice[];
};

export interface AdherenceSummary {
  day: string;
  planned_minutes: number;
  planned_label?: string;
  actual_minutes: number;
  actual_label?: string;
  productive_minutes: number;
  productive_label?: string;
  effective_focus_minutes: number;
  effective_focus_label?: string;
  on_plan_focus_minutes?: number;
  on_plan_focus_label?: string;
  off_plan_productive_minutes?: number;
  off_plan_productive_label?: string;
  distraction_on_plan_minutes?: number;
  distraction_on_plan_label?: string;
  adherence_pct: number | null;
  block_count: number;
  session_count: number;
}

export async function fetchPlannerBlocks(from: Date, to: Date): Promise<PlannerBlock[]> {
  if (isFocusDesktopShell()) {
    try {
      const r = await fetch(focusDataUrl("plan_blocks.json"), { cache: "no-store" });
      if (r.ok) {
        const j = (await r.json()) as { blocks?: PlannerBlock[] };
        const blocks = Array.isArray(j.blocks) ? j.blocks : [];
        const fromMs = from.getTime();
        const toMs = to.getTime();
        return blocks.filter((b) => {
          const s = Date.parse(String(b.start_at || ""));
          return Number.isFinite(s) && s >= fromMs && s < toMs;
        });
      }
    } catch {
      /* fall through */
    }
  }
  const transport = tryPlanTransport();
  if (transport === "offline") return [];
  if (transport === "gateway") {
    try {
      // Calendar tab paint: one 2.5s try — do not burn 3×8s on a busy pipe.
      const res = await planGateway(
        "plan.list",
        { from: from.toISOString(), to: to.toISOString() },
        2500,
        1,
      );
      return (res.blocks as PlannerBlock[]) ?? [];
    } catch {
      return [];
    }
  }
  const params = new URLSearchParams({
    from: from.toISOString(),
    to: to.toISOString(),
  });
  const res = await fetch(resolveApiUrl(`/api/planner/blocks?${params}`), { headers: authHeaders() });
  if (!res.ok) throw new Error(await res.text());
  const data = (await res.json()) as { blocks: PlannerBlock[] };
  return data.blocks;
}

export async function createPlannerBlock(body: {
  title: string;
  category?: string;
  start_at: string;
  duration_minutes?: number;
  end_at?: string;
  color?: string;
}): Promise<PlannerBlock> {
  if (planTransport() === "gateway") {
    const res = await planGateway("plan.upsert", { ...body });
    return res.block as PlannerBlock;
  }
  const res = await fetch(resolveApiUrl("/api/planner/blocks"), {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await res.text());
  const data = (await res.json()) as { block: PlannerBlock };
  return data.block;
}

export async function updatePlannerBlock(
  id: number,
  body: Partial<{
    title: string;
    category: string;
    start_at: string;
    end_at: string;
    duration_minutes: number;
    remaining_minutes: number;
    color: string;
    status: PlannerBlockStatus;
  }>,
): Promise<PlannerBlock> {
  if (planTransport() === "gateway") {
    const res = await planGateway("plan.upsert", { id, ...body });
    return res.block as PlannerBlock;
  }
  const res = await fetch(resolveApiUrl(`/api/planner/blocks/${id}`), {
    method: "PATCH",
    headers: authHeaders(),
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await res.text());
  const data = (await res.json()) as { block: PlannerBlock };
  return data.block;
}

export async function deletePlannerBlock(id: number): Promise<void> {
  if (planTransport() === "gateway") {
    await planGateway("plan.delete", { id });
    return;
  }
  const res = await fetch(resolveApiUrl(`/api/planner/blocks/${id}`), {
    method: "DELETE",
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(await res.text());
}

/** Delete every planner block overlapping the local calendar day (default: today). */
export async function clearPlannerDay(date?: string): Promise<{ deleted: number }> {
  const ymd =
    date ??
    (() => {
      const t = new Date();
      const y = t.getFullYear();
      const m = String(t.getMonth() + 1).padStart(2, "0");
      const d = String(t.getDate()).padStart(2, "0");
      return `${y}-${m}-${d}`;
    })();
  if (planTransport() === "gateway") {
    const res = await planGateway("plan.clear_day", { date: ymd });
    return { deleted: Number(res.deleted ?? 0) };
  }
  // Study HTTP: delete listed blocks for the day (no dedicated clear endpoint).
  const from = new Date(`${ymd}T00:00:00`);
  const to = new Date(from);
  to.setDate(to.getDate() + 1);
  const blocks = await fetchPlannerBlocks(from, to);
  let deleted = 0;
  for (const b of blocks) {
    await deletePlannerBlock(b.id);
    deleted += 1;
  }
  return { deleted };
}

export async function startPlannerBlock(id: number): Promise<PlannerBlock> {
  if (planTransport() === "gateway") {
    const res = await planGateway("plan.start", { id });
    return res.block as PlannerBlock;
  }
  const res = await fetch(resolveApiUrl(`/api/planner/blocks/${id}/start`), {
    method: "POST",
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(await res.text());
  const data = (await res.json()) as { block: PlannerBlock };
  return data.block;
}

export async function completePlannerBlock(
  id: number,
  minutes_spent?: number,
): Promise<PlannerBlock> {
  if (planTransport() === "gateway") {
    const payload: Record<string, unknown> = { id };
    if (typeof minutes_spent === "number") payload.minutes_spent = minutes_spent;
    const res = await planGateway("plan.complete", payload);
    return res.block as PlannerBlock;
  }
  const res = await fetch(resolveApiUrl(`/api/planner/blocks/${id}/complete`), {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({ minutes_spent }),
  });
  if (!res.ok) throw new Error(await res.text());
  const data = (await res.json()) as { block: PlannerBlock };
  return data.block;
}

export async function rollForwardPlannerBlock(
  _id: number,
  _new_start?: string,
): Promise<{ rolled_block: PlannerBlock; new_block: PlannerBlock }> {
  throw new Error("Carry-forward disabled — unfinished plans do not move to another day.");
}

export async function fetchActualOverlay(from: Date, to: Date): Promise<ActualSession[]> {
  const payload = await fetchActualOverlayFull(from, to);
  return payload.sessions;
}

type SleepWindowsMirror = {
  windows?: Array<{ date?: string; start?: string; end?: string; minutes?: number }>;
};

/**
 * Sleep mirrors store local wall times without a Z suffix
 * (`2026-10-09T00:15:00`). Parse as local, not UTC — `parseApiDate` would
 * append Z and shift the block by the timezone offset (blank calendar night).
 */
function parseLocalWallDate(raw: string): Date {
  const s = String(raw || "").trim();
  if (!s) return new Date(NaN);
  if (/[zZ]$|[+-]\d{2}:\d{2}$/.test(s)) return new Date(s);
  const m = s.match(
    /^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2})(?::(\d{2}))?)?/,
  );
  if (!m) return new Date(s);
  return new Date(
    Number(m[1]),
    Number(m[2]) - 1,
    Number(m[3]),
    Number(m[4] || 0),
    Number(m[5] || 0),
    Number(m[6] || 0),
    0,
  );
}

/** Amazfit / CALT Sync sleep → calendar actual chips (Focus mirrors; no Study). */
export async function sleepSessionsFromFocusMirrors(from: Date, to: Date): Promise<ActualSession[]> {
  // Prefer Focus shell, but still try calt-data on design host / file loads.
  const out: ActualSession[] = [];
  const fromMs = from.getTime();
  const toMs = to.getTime();
  const pushWindow = (startRaw: string, endRaw: string, dayKey: string) => {
    const start = parseLocalWallDate(startRaw);
    const end = parseLocalWallDate(endRaw);
    if (!Number.isFinite(start.getTime()) || !Number.isFinite(end.getTime()) || end <= start) return;
    if (end.getTime() <= fromMs || start.getTime() >= toMs) return;
    out.push({
      session_id: `wearable-sleep-${dayKey}`,
      start_time: start.toISOString(),
      end_time: end.toISOString(),
      source: "wearable_sleep",
      category: "Sleep",
      app_name: "amazfit",
      window_title: "Sleep",
      site: null,
      task_id: null,
    });
  };

  try {
    const swRes = await fetch(focusDataUrl("sleep_windows.json"), { cache: "no-store" });
    if (swRes.ok) {
      const sw = (await swRes.json()) as SleepWindowsMirror;
      for (const w of sw.windows || []) {
        if (!w?.start || !w?.end) continue;
        pushWindow(w.start, w.end, String(w.date || w.start).slice(0, 10));
      }
      // #region agent log
      agentDebugLog({hypothesisId:'A',location:'plannerClient.ts:sleep_windows',message:'sleep_windows mirror parse',data:{from:from.toISOString(),to:to.toISOString(),rawWindows:(sw.windows||[]).map(w=>({date:w.date,start:w.start,end:w.end,minutes:w.minutes})),out:out.map(s=>({id:s.session_id,start:s.start_time,end:s.end_time,localStart:s.start_time?new Date(s.start_time).toString():null,localEnd:s.end_time?new Date(s.end_time).toString():null}))}});
      // #endregion
    }
  } catch {
    /* ignore */
  }

  if (out.length) return out;

  // Fallback: wearable_day sleep (real start/end, multi windows, or bedtime-anchored).
  try {
    const [wearRes, lifeRes] = await Promise.all([
      fetch(focusDataUrl("wearable_day.json"), { cache: "no-store" }),
      fetch(focusDataUrl("life_today.json"), { cache: "no-store" }),
    ]);
    const wear = wearRes.ok ? ((await wearRes.json()) as Record<string, unknown>) : null;
    const life = lifeRes.ok ? ((await lifeRes.json()) as Record<string, unknown>) : null;
    const day = String(wear?.local_date || life?.date || dayIsoLocal(new Date())).slice(0, 10);
    const sleepObj =
      wear?.payload && typeof wear.payload === "object"
        ? (wear.payload as {
            sleep?: {
              total_min?: number;
              start_min?: number;
              end_min?: number;
              start_iso?: string;
              end_iso?: string;
              windows?: Array<{ start?: string; end?: string; minutes?: number }>;
              naps?: Array<{ start_min?: number; end_min?: number; start?: string; end?: string }>;
            };
          }).sleep
        : null;

    // Explicit multi-windows from Fit/Zepp coerce.
    for (const w of sleepObj?.windows || []) {
      if (w?.start && w?.end) pushWindow(w.start, w.end, day);
    }
    if (out.length) return out;

    if (sleepObj?.start_iso && sleepObj?.end_iso) {
      pushWindow(sleepObj.start_iso, sleepObj.end_iso, day);
      if (out.length) return out;
    }

    // Zepp minute-of-day (start often previous evening).
    if (
      typeof sleepObj?.start_min === "number" &&
      typeof sleepObj?.end_min === "number" &&
      sleepObj.end_min !== sleepObj.start_min
    ) {
      const [y, m, d] = day.split("-").map(Number);
      const end = new Date(y, m - 1, d, 0, 0, 0, 0);
      end.setMinutes(sleepObj.end_min);
      const start = new Date(y, m - 1, d, 0, 0, 0, 0);
      start.setMinutes(sleepObj.start_min);
      if (sleepObj.end_min <= sleepObj.start_min) start.setDate(start.getDate() - 1);
      pushWindow(start.toISOString(), end.toISOString(), day);
      for (const nap of sleepObj.naps || []) {
        if (nap.start && nap.end) {
          pushWindow(nap.start, nap.end, `${day}-nap`);
        } else if (typeof nap.start_min === "number" && typeof nap.end_min === "number") {
          const ns = new Date(y, m - 1, d, 0, 0, 0, 0);
          const ne = new Date(y, m - 1, d, 0, 0, 0, 0);
          ns.setMinutes(nap.start_min);
          ne.setMinutes(nap.end_min);
          if (nap.end_min <= nap.start_min) ns.setDate(ns.getDate() - 1);
          pushWindow(ns.toISOString(), ne.toISOString(), `${day}-nap`);
        }
      }
      if (out.length) return out;
    }

    let mins = 0;
    if (typeof sleepObj?.total_min === "number" && sleepObj.total_min > 0) {
      mins = Math.round(sleepObj.total_min);
    } else if (typeof wear?.sleep_hours === "number" && wear.sleep_hours > 0) {
      mins = Math.round(wear.sleep_hours * 60);
    } else if (typeof life?.sleep_hours === "number" && life.sleep_hours > 0) {
      mins = Math.round(life.sleep_hours * 60);
    }
    if (mins <= 0) return out;
    mins = Math.min(16 * 60, Math.max(1, mins));
    // Duration-only: bedtime-anchored overnight (23:00 → +duration), not wake→00:00 strip.
    const [y, m, d] = day.split("-").map(Number);
    const start = new Date(y, m - 1, d, 23, 0, 0, 0);
    start.setDate(start.getDate() - 1);
    const end = new Date(start.getTime() + mins * 60_000);
    pushWindow(start.toISOString(), end.toISOString(), day);
  } catch {
    /* ignore */
  }
  return out;
}

function mergeSleepIntoOverlay(
  sessions: ActualSession[],
  sleep: ActualSession[],
): ActualSession[] {
  if (!sleep.length) return sessions;
  const have = new Set(
    sessions
      .filter(
        (s) =>
          (s.category || "").toLowerCase() === "sleep" ||
          (s.source || "").toLowerCase() === "wearable_sleep",
      )
      .map((s) => s.session_id),
  );
  const extra = sleep.filter((s) => !have.has(s.session_id));
  return extra.length ? [...sessions, ...extra] : sessions;
}

export async function fetchActualOverlayFull(from: Date, to: Date): Promise<ActualOverlayPayload> {
  const transport = tryPlanTransport();
  const sleepPromise = sleepSessionsFromFocusMirrors(from, to);

  if (transport === "offline") {
    const sleep = await sleepPromise;
    return { sessions: sleep, hour_slices: [] };
  }
  if (transport === "gateway") {
    try {
      // FE timer must exceed native pipe budget so enforcer_cmd_result is not
      // dropped on the timeout race (native 16s → FE 22s). One try — calendar
      // pullOverlay already retries; stacking retries stuck the FE cmd queue.
      const res = await planGateway(
        "plan.overlay",
        { from: from.toISOString(), to: to.toISOString() },
        22000,
        1,
      );
      const overlay = (res.overlay as ActualOverlayPayload) || { sessions: [], hour_slices: [] };
      const sleep = await sleepPromise;
      const merged = mergeSleepIntoOverlay(overlay.sessions ?? [], sleep);
      // #region agent log
      {
        const sess = overlay.sessions ?? [];
        const isSleep = (s: ActualSession) =>
          (s.category || "").toLowerCase() === "sleep" ||
          (s.source || "").toLowerCase() === "wearable_sleep";
        const sleepS = sess.filter(isSleep);
        const deskS = sess.filter((s) => !isSleep(s));
        agentDebugLog({hypothesisId:'B',location:'plannerClient.ts:overlay',message:'plan.overlay merge',data:{transport,overlayTotal:sess.length,overlaySleep:sleepS.length,overlayDesktop:deskS.length,mirrorSleep:sleep.length,mergedTotal:merged.length,sleepFromOverlay:sleepS.map(s=>({id:s.session_id,start:s.start_time,end:s.end_time})),sleepFromMirror:sleep.map(s=>({id:s.session_id,start:s.start_time,end:s.end_time})),deskSample:deskS.slice(0,5).map(s=>({start:s.start_time,end:s.end_time,app:s.app_name,cat:s.category})),hourSlicesNative:(overlay.hour_slices||[]).length}});
      }
      // #endregion
      return {
        sessions: merged,
        hour_slices: overlay.hour_slices ?? [],
      };
    } catch (e) {
      const sleep = await sleepPromise;
      // #region agent log
      agentDebugLog({hypothesisId:'C',location:'plannerClient.ts:overlay-catch',message:'plan.overlay failed; rethrow for calendar retry',data:{err:e instanceof Error?e.message:String(e),mirrorSleep:sleep.length}});
      // #endregion
      // Rethrow so PlannerCalendar pullOverlay retries — soft-returning sleep-only
      // looked "successful" and left the day empty of desktop actuals forever.
      const err = e instanceof Error ? e : new Error(String(e));
      (err as Error & { sleepFallback?: ActualSession[] }).sleepFallback = sleep;
      throw err;
    }
  }
  const params = new URLSearchParams({
    from: from.toISOString(),
    to: to.toISOString(),
  });
  const res = await fetch(resolveApiUrl(`/api/planner/overlay/actual?${params}`), {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(await res.text());
  const data = (await res.json()) as ActualOverlayPayload;
  const sleep = await sleepPromise;
  return {
    sessions: mergeSleepIntoOverlay(data.sessions ?? [], sleep),
    hour_slices: data.hour_slices ?? [],
  };
}

export async function fetchAdherence(day: Date): Promise<AdherenceSummary> {
  const dayKey = dayIsoLocal(day);
  const transport = tryPlanTransport();
  if (transport === "offline") return emptyAdherence(dayKey);
  if (transport === "gateway") {
    try {
      const res = await planGateway("plan.adherence", { day: dayKey });
      return (res.adherence as AdherenceSummary) ?? emptyAdherence(dayKey);
    } catch {
      return emptyAdherence(dayKey);
    }
  }
  const params = new URLSearchParams({ day: day.toISOString() });
  const res = await fetch(resolveApiUrl(`/api/planner/adherence?${params}`), {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

/** N days of adherence ending on `end` (default: today). */
export async function fetchAdherenceRange(days = 7, end?: Date): Promise<AdherenceSummary[]> {
  const transport = tryPlanTransport();
  const endDay = end ? new Date(end) : new Date();
  endDay.setHours(0, 0, 0, 0);

  if (transport === "offline") {
    return Array.from({ length: days }, (_, i) => {
      const d = new Date(endDay);
      d.setDate(d.getDate() - (days - 1 - i));
      return emptyAdherence(dayIsoLocal(d));
    });
  }

  // Focus gateway has plan.adherence (single day) — assemble the strip locally.
  if (transport === "gateway") {
    const results = await Promise.all(
      Array.from({ length: days }, async (_, i) => {
        const d = new Date(endDay);
        d.setDate(d.getDate() - (days - 1 - i));
        try {
          return await fetchAdherence(d);
        } catch {
          return emptyAdherence(dayIsoLocal(d));
        }
      }),
    );
    return results;
  }

  const params = new URLSearchParams({ days: String(days) });
  if (end) params.set("end", end.toISOString());
  const res = await fetch(resolveApiUrl(`/api/planner/adherence/range?${params}`), {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(await res.text());
  const data = (await res.json()) as { days: AdherenceSummary[] };
  return data.days ?? [];
}

export async function generateWeekFromTimetable(timetableId?: number): Promise<{ created: number }> {
  if (isFocusDesktopShell()) focusNeedsStudyApi("Generate week from timetable");
  const res = await fetch(resolveApiUrl("/api/planner/generate-week"), {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({ timetable_id: timetableId ?? null }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export interface PlannerRoutine {
  id: number;
  title: string;
  category: string;
  start_time: string;
  end_time: string | null;
  duration_minutes: number | null;
  days: string[];
  color: string | null;
  enabled: boolean;
  sort_order: number;
}

export async function fetchRoutines(): Promise<PlannerRoutine[]> {
  // Prefer live enforcer list when the pipe is up — plan_blocks.json can lag until
  // routine.upsert/delete republish (and used to skip republish entirely).
  const transport = tryPlanTransport();
  if (transport === "gateway") {
    try {
      const res = await planGateway("routine.list", {}, 4000, 1);
      if (Array.isArray(res.routines)) return res.routines as PlannerRoutine[];
    } catch {
      /* fall through to mirror / HTTP */
    }
  }
  if (isFocusDesktopShell()) {
    try {
      const r = await fetch(focusDataUrl("plan_blocks.json"), { cache: "no-store" });
      if (r.ok) {
        const j = (await r.json()) as { routines?: PlannerRoutine[] };
        if (Array.isArray(j.routines)) return j.routines;
      }
    } catch {
      /* fall through */
    }
  }
  if (transport === "offline") return [];
  const res = await fetch(resolveApiUrl("/api/planner/routines"), { headers: authHeaders() });
  if (!res.ok) throw new Error(await res.text());
  const data = (await res.json()) as { routines: PlannerRoutine[] };
  return data.routines;
}

export async function seedDefaultRoutines(): Promise<PlannerRoutine[]> {
  if (isFocusDesktopShell()) focusNeedsStudyApi("Seed default routines");
  const res = await fetch(resolveApiUrl("/api/planner/routines/seed-defaults"), {
    method: "POST",
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(await res.text());
  const data = (await res.json()) as { routines: PlannerRoutine[] };
  return data.routines;
}

export async function createRoutine(body: {
  title: string;
  category?: string;
  start_time: string;
  end_time?: string;
  days?: string[];
  color?: string;
}): Promise<PlannerRoutine> {
  if (planTransport() === "gateway") {
    const res = await planGateway("routine.upsert", { ...body });
    return res.routine as PlannerRoutine;
  }
  const res = await fetch(resolveApiUrl("/api/planner/routines"), {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await res.text());
  const data = (await res.json()) as { routine: PlannerRoutine };
  return data.routine;
}

export async function updateRoutine(
  id: number,
  body: Partial<{
    title: string;
    category: string;
    start_time: string;
    end_time: string | null;
    duration_minutes: number | null;
    days: string[];
    color: string | null;
    enabled: boolean;
    sort_order: number;
  }>,
): Promise<PlannerRoutine> {
  if (planTransport() === "gateway") {
    const res = await planGateway("routine.upsert", { id, ...body });
    return res.routine as PlannerRoutine;
  }
  const res = await fetch(resolveApiUrl(`/api/planner/routines/${id}`), {
    method: "PATCH",
    headers: authHeaders(),
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await res.text());
  const data = (await res.json()) as { routine: PlannerRoutine };
  return data.routine;
}

export async function deleteRoutine(id: number): Promise<{ blocks_cleared: number }> {
  if (planTransport() === "gateway") {
    const res = await planGateway("routine.delete", { id });
    return { blocks_cleared: Number(res.blocks_cleared ?? 0) };
  }
  const res = await fetch(resolveApiUrl(`/api/planner/routines/${id}`), {
    method: "DELETE",
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(await res.text());
  return { blocks_cleared: 0 };
}

export async function applyRoutines(date?: string): Promise<{ created: number }> {
  if (planTransport() === "gateway") {
    const res = await planGateway("routine.apply", {
      date: date ?? null,
      skip_overlaps: true,
    });
    return { created: Number(res.created ?? 0) };
  }
  let res: Response;
  try {
    res = await fetch(resolveApiUrl("/api/planner/routines/apply"), {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({ date: date ?? null, skip_overlaps: true }),
    });
  } catch {
    throw new Error("Cannot reach API (is the backend running on port 8000?)");
  }
  if (!res.ok) {
    const body = (await res.text()).trim();
    throw new Error(body || `Apply failed (HTTP ${res.status})`);
  }
  return res.json();
}

/** Max days for routine apply / clear range (Today · Week · Month). */
export const MAX_ROUTINE_APPLY_DAYS = 31;

/** Inclusive local YMD list from → to, capped at maxDays. */
export function expandYmdRange(
  fromYmd: string,
  toYmd: string,
  maxDays = MAX_ROUTINE_APPLY_DAYS,
): string[] {
  const [fy, fm, fd] = fromYmd.split("-").map(Number);
  const [ty, tm, td] = toYmd.split("-").map(Number);
  let a = new Date(fy, (fm || 1) - 1, fd || 1);
  let b = new Date(ty, (tm || 1) - 1, td || 1);
  if (a.getTime() > b.getTime()) {
    const tmp = a;
    a = b;
    b = tmp;
  }
  const out: string[] = [];
  const cur = new Date(a);
  while (cur.getTime() <= b.getTime() && out.length < maxDays) {
    const y = cur.getFullYear();
    const m = String(cur.getMonth() + 1).padStart(2, "0");
    const d = String(cur.getDate()).padStart(2, "0");
    out.push(`${y}-${m}-${d}`);
    cur.setDate(cur.getDate() + 1);
  }
  return out;
}

/** Apply enabled routines for each local day (skip overlaps). */
export async function applyRoutinesRange(
  dates: string[],
): Promise<{ created: number; days: number }> {
  const capped = dates.slice(0, MAX_ROUTINE_APPLY_DAYS);
  let created = 0;
  for (const date of capped) {
    const r = await applyRoutines(date);
    created += r.created;
  }
  return { created, days: capped.length };
}

/** Clear planner blocks for each local day in the list. */
export async function clearPlannerRange(
  dates: string[],
): Promise<{ deleted: number; days: number }> {
  const capped = dates.slice(0, MAX_ROUTINE_APPLY_DAYS);
  let deleted = 0;
  for (const date of capped) {
    const r = await clearPlannerDay(date);
    deleted += r.deleted;
  }
  return { deleted, days: capped.length };
}

/** Runs once per local day on login — adds missing routine blocks (skip_overlaps). */
export async function autoApplyRoutinesToday(): Promise<{
  created: number;
  skipped: boolean;
  date?: string;
}> {
  if (planTransport() === "gateway") {
    const res = await planGateway("routine.apply", { skip_overlaps: true });
    return { created: Number(res.created ?? 0), skipped: false };
  }
  const res = await fetch(resolveApiUrl("/api/planner/routines/auto-apply-today"), {
    method: "POST",
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

/** Max calendar days the productivity export API accepts (~1 leap year). */
export const MAX_PRODUCTIVITY_EXPORT_DAYS = 366;

/** Format FastAPI / envelope validation errors for UI (surface field + msg). */
export function formatPlannerApiError(raw: string, status: number): string {
  try {
    const parsed = JSON.parse(raw) as {
      error?: { message?: string; details?: unknown };
      detail?: unknown;
    };
    const base =
      parsed.error?.message ||
      (typeof parsed.detail === "string" ? parsed.detail : null);
    const details =
      parsed.error?.details ??
      (Array.isArray(parsed.detail) ? parsed.detail : null);
    if (Array.isArray(details) && details.length > 0) {
      const bits = details.map((d: unknown) => {
        const row = d as { loc?: unknown[]; msg?: string; message?: string };
        const loc = Array.isArray(row.loc)
          ? row.loc
              .filter((x) => x !== "query" && x !== "body" && x !== "path")
              .join(".")
          : "";
        const msg = row.msg || row.message || String(d);
        return loc ? `${loc}: ${msg}` : msg;
      });
      return `${base || "Validation failed"} — ${bits.join("; ")}`;
    }
    return base || raw || `Request failed (${status})`;
  } catch {
    return raw.trim() || `Request failed (${status})`;
  }
}

function triggerBlobDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

/** Focus shell: enforcer writes behavior/productivity_export.* then native copy / calt-data fetch. */
async function downloadProductivityWeekExportFocus(
  days: number,
  format: "json" | "csv" | "csv_wide",
  options?: {
    include?: string;
    productiveOnly?: boolean;
    skipEmpty?: boolean;
    endDay?: string;
  },
): Promise<void> {
  const r = await enforcerNativeCmd(
    "productivity.export",
    {
      days,
      format,
      include: options?.include,
      productive_only: !!options?.productiveOnly,
      skip_empty: options?.skipEmpty !== false,
      end_day: options?.endDay,
      // Settings exports are for trend/burnout analysis. Avoid shipping a huge
      // raw window-title stream through WebView2; aggregate tables remain.
      analysis_only: true,
    },
    90_000,
  );
  if (!r || r.ok === false) {
    throw new Error(
      (r && typeof r.error === "string" && r.error) ||
        "Export failed (enforcer unreachable or timed out)",
    );
  }
  const exp = (r.export as Record<string, unknown> | undefined) || {};
  const file =
    format === "json"
      ? String(exp.json_file || "productivity_export.json")
      : String(exp.csv_file || "productivity_export.csv");
  const stamp = new Date().toISOString().slice(0, 10).replace(/-/g, "");
  const downloadName =
    typeof exp.download_name === "string" && exp.download_name
      ? exp.download_name
      : format === "json"
        ? `productivity-${days}d-${stamp}.json`
        : format === "csv_wide"
          ? `productivity-${days}d-${stamp}-wide.csv`
          : `productivity-${days}d-${stamp}-long.csv`;

  // Prefer native copy → Downloads. Multi-MB calt-data fetch often fails with "Failed to fetch".
  try {
    const { focusBehaviorFile, isFocusBehaviorFileAvailable } = await import(
      "../lib/focusBehaviorFile"
    );
    if (isFocusBehaviorFileAvailable()) {
      const native = await focusBehaviorFile({
        op: "copy_downloads",
        file,
        downloadName,
      });
      if (native && native.ok) return;
    }
  } catch {
    /* fall through to calt-data */
  }

  let res: Response;
  try {
    res = await fetch(`${focusDataUrl(file)}?t=${Date.now()}`, { cache: "no-store" });
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : "Network error";
    throw new Error(
      `Export file unreachable (${msg}). In Focus desktop, export should save to Downloads — rebuild calt_focus if this persists.`,
    );
  }
  if (!res.ok) {
    throw new Error(`Export file missing (${res.status}). Re-run export.`);
  }
  const blob =
    format === "json"
      ? new Blob([JSON.stringify(await res.json(), null, 2)], {
          type: "application/json",
        })
      : await res.blob();
  triggerBlobDownload(blob, downloadName);
}

/** Last N days of plan + tracked usage — for designing weekly timetables. */
export async function downloadProductivityWeekExport(
  days = 7,
  format: "json" | "csv" | "csv_wide" = "json",
  options?: {
    include?: string;
    productiveOnly?: boolean;
    /** Omit blank days (default true; matches API). Pass false to keep empty rows. */
    skipEmpty?: boolean;
    /** Inclusive end day YYYY-MM-DD (API `end_day`; default today). */
    endDay?: string;
  },
): Promise<void> {
  const clampedDays = Math.max(1, Math.min(MAX_PRODUCTIVITY_EXPORT_DAYS, Math.floor(days) || 1));

  // Focus desktop: SoT is productivity.db via enforcer — never Study :8000.
  if (isFocusDesktopShell()) {
    if (!isFocusEnforcerBridgeAvailable()) {
      throw new Error("Export needs the Focus enforcer (WebView bridge).");
    }
    await downloadProductivityWeekExportFocus(clampedDays, format, options);
    return;
  }

  const params = new URLSearchParams({ days: String(clampedDays), format });
  if (options?.include) params.set("include", options.include);
  if (options?.productiveOnly) params.set("productive_only", "true");
  if (options?.skipEmpty === false) params.set("skip_empty", "false");
  else if (options?.skipEmpty === true) params.set("skip_empty", "true");
  if (options?.endDay && /^\d{4}-\d{2}-\d{2}$/.test(options.endDay)) {
    params.set("end_day", options.endDay);
  }
  let res: Response;
  try {
    res = await fetch(resolveApiUrl(`/api/planner/export/last-7-days?${params}`), {
      headers: authHeaders(),
    });
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : "Network error";
    throw new Error(
      `Export unreachable (${msg}). Is the API running on the backend URL?`,
    );
  }
  if (!res.ok) {
    const raw = await res.text();
    throw new Error(formatPlannerApiError(raw, res.status));
  }
  const stamp = new Date().toISOString().slice(0, 10).replace(/-/g, "");
  let blob: Blob;
  if (format === "json") {
    const data = await res.json();
    blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  } else {
    blob = await res.blob();
  }
  triggerBlobDownload(
    blob,
    format === "json"
      ? `productivity-${clampedDays}d-${stamp}.json`
      : format === "csv_wide"
        ? `productivity-${clampedDays}d-${stamp}-wide.csv`
        : `productivity-${clampedDays}d-${stamp}-long.csv`,
  );
}

/** Days with tracked / plan / wearable signal — for export range calendars. */
export async function fetchExportDayPresence(
  start: string,
  end: string,
): Promise<{ start: string; end: string; days: string[]; count: number }> {
  if (isFocusDesktopShell()) {
    if (!isFocusEnforcerBridgeAvailable()) {
      return { start, end, days: [], count: 0 };
    }
    const r = await enforcerNativeCmd(
      "productivity.export_presence",
      { start, end },
      15_000,
    );
    if (!r || r.ok === false) {
      throw new Error(
        (r && typeof r.error === "string" && r.error) || "Day presence failed",
      );
    }
    const days = Array.isArray(r.days)
      ? (r.days as unknown[]).map((d) => String(d)).filter(Boolean)
      : [];
    return {
      start: typeof r.start === "string" ? r.start : start,
      end: typeof r.end === "string" ? r.end : end,
      days,
      count: typeof r.count === "number" ? r.count : days.length,
    };
  }

  const params = new URLSearchParams({ start, end });
  let res: Response;
  try {
    res = await fetch(resolveApiUrl(`/api/planner/export/day-presence?${params}`), {
      headers: authHeaders(),
    });
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : "Network error";
    throw new Error(`Day presence unreachable (${msg})`);
  }
  if (!res.ok) {
    const raw = await res.text();
    throw new Error(formatPlannerApiError(raw, res.status));
  }
  return res.json();
}

export type ProposedPlannerBlock = {
  title: string;
  category: string;
  start_at: string;
  end_at: string;
  /** study = proposed focus, routine = from templates, existing = already on calendar, break = rest */
  source?: "study" | "routine" | "existing" | "break";
  existing_id?: number;
};

export async function proposeWeekFromExport(body?: {
  days?: number;
  goals?: string;
  week_start?: string;
  range_start?: string;
  horizon_days?: number;
  use_llm?: boolean;
  include_routines?: boolean;
  mode?: "smart" | "review" | "full";
  draft_blocks?: ProposedPlannerBlock[];
}): Promise<{
  week_start: string;
  range_start?: string;
  horizon_days?: number;
  blocks: ProposedPlannerBlock[];
  rationale: string;
  used_llm: boolean;
  goals: string;
  mode?: string;
  load_scale?: number;
  scaled_daily_hours?: number;
  stated_daily_hours?: number;
}> {
  if (isFocusDesktopShell()) focusNeedsStudyApi("Propose week (LLM/rules)");
  let res: Response;
  try {
    res = await fetch(resolveApiUrl("/api/planner/propose-from-export"), {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({
        days: body?.days ?? 7,
        goals: body?.goals ?? null,
        week_start: body?.week_start ?? null,
        range_start: body?.range_start ?? null,
        horizon_days: body?.horizon_days ?? 7,
        use_llm: body?.use_llm ?? true,
        include_routines: body?.include_routines ?? true,
        mode: body?.mode ?? null,
        draft_blocks: body?.draft_blocks ?? null,
      }),
    });
  } catch {
    throw new Error("API unreachable — is the backend running on :8000?");
  }
  if (!res.ok) {
    const raw = await res.text();
    try {
      const parsed = JSON.parse(raw) as { error?: { message?: string }; detail?: string };
      throw new Error(parsed.error?.message || parsed.detail || raw || `Propose failed (${res.status})`);
    } catch (e) {
      if (e instanceof Error && e.message !== raw) throw e;
      throw new Error(raw || `Propose failed (${res.status})`);
    }
  }
  return res.json();
}

export async function applyProposedBlocks(
  blocks: ProposedPlannerBlock[],
): Promise<{ created: number }> {
  const res = await fetch(resolveApiUrl("/api/planner/apply-proposed-blocks"), {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({ blocks }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export type StudyTask = {
  id: string;
  title: string;
  minutes: number;
  allowHosts: string[];
  blockCategories: string[];
};

export type PlanDriftSummary = {
  lines: string[];
  late_count: number;
  skipped_count: number;
  block_count: number;
  summary: string;
};

export type ApplyMyDayResult = {
  ok: boolean;
  error?: string;
  snapshot_blocks?: number;
  routines_created?: number;
  study_created?: number;
  skipped_overlaps?: number;
  sleep?: number;
};

export async function mergeProposeResult(body: {
  api_blocks: ProposedPlannerBlock[];
  range_start?: string;
  horizon_days?: number;
}): Promise<{ blocks: ProposedPlannerBlock[]; rule: string; merged_count: number }> {
  const res = await fetch(resolveApiUrl("/api/planner/merge-propose"), {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({
      api_blocks: body.api_blocks,
      range_start: body.range_start ?? null,
      horizon_days: body.horizon_days ?? 7,
    }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function applyDayRhythm(
  blocks: ProposedPlannerBlock[],
  day?: string,
): Promise<{ blocks: ProposedPlannerBlock[]; rule: string }> {
  const res = await fetch(resolveApiUrl("/api/planner/apply-day-rhythm"), {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({ blocks, day: day ?? null }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function applyMyDay(body?: {
  goals?: string;
  study_tasks?: StudyTask[];
  wake_hm?: string;
  snapshot?: boolean;
}): Promise<ApplyMyDayResult> {
  const res = await fetch(resolveApiUrl("/api/planner/apply-my-day"), {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({
      goals: body?.goals ?? null,
      study_tasks: body?.study_tasks ?? null,
      wake_hm: body?.wake_hm ?? null,
      snapshot: body?.snapshot ?? true,
    }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error((data as { error?: string; detail?: string }).error || (data as { detail?: string }).detail || "Apply my day failed");
  }
  return data as ApplyMyDayResult;
}

export async function revertLastApply(): Promise<{ ok: boolean; restored?: number; error?: string }> {
  const res = await fetch(resolveApiUrl("/api/planner/revert-last-apply"), {
    method: "POST",
    headers: authHeaders(),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error((data as { error?: string }).error || "Revert failed");
  return data;
}

export async function fetchPlanDrift(day?: string): Promise<PlanDriftSummary> {
  const params = day ? `?day=${encodeURIComponent(day)}` : "";
  const res = await fetch(resolveApiUrl(`/api/planner/plan-drift${params}`), {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function fetchMorningOrderRule(day?: string): Promise<{ rule: string }> {
  const params = day ? `?day=${encodeURIComponent(day)}` : "";
  const res = await fetch(resolveApiUrl(`/api/planner/morning-order-rule${params}`), {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export type GoogleCalendarStatus = {
  client_configured: boolean;
  connected: boolean;
  calendar_id: string;
  has_access_token: boolean;
  redirect_uri?: string;
  setup_url?: string;
};

export async function fetchGoogleCalendarStatus(): Promise<GoogleCalendarStatus> {
  if (isFocusDesktopShell()) focusNeedsStudyApi("Google Calendar (sidecar)");
  const res = await fetch(resolveApiUrl("/api/planner/google-calendar/status"), {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function saveGoogleCalendarCredentials(
  clientId: string,
  clientSecret: string,
): Promise<GoogleCalendarStatus & { ok: boolean }> {
  const res = await fetch(resolveApiUrl("/api/planner/google-calendar/credentials"), {
    method: "POST",
    headers: { ...authHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify({ client_id: clientId, client_secret: clientSecret }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error((data as { detail?: string }).detail || "Failed to save credentials");
  }
  return data as GoogleCalendarStatus & { ok: boolean };
}

export async function fetchGoogleCalendarAuthUrl(): Promise<string> {
  const res = await fetch(resolveApiUrl("/api/planner/google-calendar/auth-url"), {
    headers: authHeaders(),
  });
  if (!res.ok) {
    const t = await res.text();
    throw new Error(t || "Auth URL failed — paste Client ID/Secret below");
  }
  const data = (await res.json()) as { url?: string };
  if (!data.url) throw new Error("No auth URL");
  return data.url;
}

export async function syncPlannerToGoogleCalendar(days = 14): Promise<{
  ok: boolean;
  created?: number;
  updated?: number;
  skipped?: number;
  block_count?: number;
  error?: string;
  hint?: string;
  errors?: string[];
}> {
  const res = await fetch(
    resolveApiUrl(`/api/planner/google-calendar/sync?days=${days}`),
    { method: "POST", headers: authHeaders() },
  );
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error((data as { detail?: string }).detail || (await res.text()));
  return data;
}

/** Download ICS (works without Google OAuth — import into Google Calendar). */
export function downloadPlannerIcs(days = 14): void {
  const url = resolveApiUrl(`/api/planner/calendar.ics?days=${days}`);
  const a = document.createElement("a");
  a.href = url;
  a.download = "calt-planner.ics";
  // auth via cookie may not exist — open with fetch blob instead
  void (async () => {
    const res = await fetch(url, { headers: authHeaders() });
    if (!res.ok) throw new Error(await res.text());
    const blob = await res.blob();
    const obj = URL.createObjectURL(blob);
    a.href = obj;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(obj);
  })();
}

export const CATEGORY_COLORS: Record<string, string> = {
  reading: "#8b5cf6",
  study: "#10b981",
  lecture: "#3b82f6",
  break: "#6b7280",
  review: "#f59e0b",
  food: "#f59e0b",
  spiritual: "#a78bfa",
  personal: "#06b6d4",
  default: "#6366f1",
};

export function blockColor(category: string, custom?: string | null): string {
  if (custom) return custom;
  return CATEGORY_COLORS[category.toLowerCase()] ?? CATEGORY_COLORS.default;
}
