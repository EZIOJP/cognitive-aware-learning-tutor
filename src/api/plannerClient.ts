import { resolveApiUrl } from "../utils/resolveBackendUrl";
import { enforcerNativeCmd, isFocusEnforcerBridgeAvailable } from "../lib/enforcerNativeCmd";
import { isFocusDesktopShell } from "../utils/focusDesktopShell";

const TOKEN_KEY = "vocab:auth-token";

/** Focus sole Productivity door — plan mutations go through the enforcer pipe. */
function planTransport(): "gateway" | "http" {
  if (!isFocusDesktopShell()) return "http";
  if (!isFocusEnforcerBridgeAvailable()) {
    throw new Error("enforcer_unreachable");
  }
  return "gateway";
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
): Promise<Record<string, unknown>> {
  const res = await enforcerNativeCmd(op, payload, timeoutMs);
  if (!res) throw new Error("enforcer_unreachable");
  if (res.ok === false) throw new Error(String(res.error || "enforcer_cmd_failed"));
  return res as Record<string, unknown>;
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
  if (planTransport() === "gateway") {
    const res = await planGateway("plan.list", {
      from: from.toISOString(),
      to: to.toISOString(),
    });
    return (res.blocks as PlannerBlock[]) ?? [];
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
  id: number,
  new_start?: string,
): Promise<{ rolled_block: PlannerBlock; new_block: PlannerBlock }> {
  if (planTransport() === "gateway") {
    const payload: Record<string, unknown> = { id };
    if (new_start) payload.new_start = new_start;
    const res = await planGateway("plan.roll_forward", payload);
    return {
      rolled_block: res.rolled_block as PlannerBlock,
      new_block: (res.new_block as PlannerBlock) ?? (res.rolled_block as PlannerBlock),
    };
  }
  const res = await fetch(resolveApiUrl(`/api/planner/blocks/${id}/roll-forward`), {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({ new_start }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function fetchActualOverlay(from: Date, to: Date): Promise<ActualSession[]> {
  const payload = await fetchActualOverlayFull(from, to);
  return payload.sessions;
}

export async function fetchActualOverlayFull(from: Date, to: Date): Promise<ActualOverlayPayload> {
  if (planTransport() === "gateway") {
    const res = await planGateway("plan.overlay", {
      from: from.toISOString(),
      to: to.toISOString(),
    });
    const overlay = (res.overlay as ActualOverlayPayload) || { sessions: [], hour_slices: [] };
    return {
      sessions: overlay.sessions ?? [],
      hour_slices: overlay.hour_slices ?? [],
    };
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
  return {
    sessions: data.sessions ?? [],
    hour_slices: data.hour_slices ?? [],
  };
}

export async function fetchAdherence(day: Date): Promise<AdherenceSummary> {
  if (planTransport() === "gateway") {
    const y = day.getFullYear();
    const m = String(day.getMonth() + 1).padStart(2, "0");
    const d = String(day.getDate()).padStart(2, "0");
    const res = await planGateway("plan.adherence", { day: `${y}-${m}-${d}` });
    return (res.adherence as AdherenceSummary) ?? {
      day: `${y}-${m}-${d}`,
      planned_minutes: 0,
      actual_minutes: 0,
      productive_minutes: 0,
      effective_focus_minutes: 0,
      adherence_pct: null,
      block_count: 0,
      session_count: 0,
    };
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
  if (planTransport() === "gateway") {
    const res = await planGateway("routine.list", {});
    return (res.routines as PlannerRoutine[]) ?? [];
  }
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

export async function deleteRoutine(id: number): Promise<void> {
  if (planTransport() === "gateway") {
    await planGateway("routine.delete", { id });
    return;
  }
  const res = await fetch(resolveApiUrl(`/api/planner/routines/${id}`), {
    method: "DELETE",
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(await res.text());
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

/** Last N days of plan + tracked usage — for designing weekly timetables. */
export async function downloadProductivityWeekExport(
  days = 7,
  format: "json" | "csv" = "json",
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
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download =
    format === "csv"
      ? `productivity-${clampedDays}d-${stamp}.csv`
      : `productivity-${clampedDays}d-${stamp}.json`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

/** Days with tracked / plan / wearable signal — for export range calendars. */
export async function fetchExportDayPresence(
  start: string,
  end: string,
): Promise<{ start: string; end: string; days: string[]; count: number }> {
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
