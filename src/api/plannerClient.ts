import { resolveApiUrl } from "../utils/resolveBackendUrl";

const TOKEN_KEY = "vocab:auth-token";

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
  const res = await fetch(resolveApiUrl(`/api/planner/blocks/${id}`), {
    method: "DELETE",
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(await res.text());
}

export async function startPlannerBlock(id: number): Promise<PlannerBlock> {
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
  const res = await fetch(resolveApiUrl("/api/planner/routines"), { headers: authHeaders() });
  if (!res.ok) throw new Error(await res.text());
  const data = (await res.json()) as { routines: PlannerRoutine[] };
  return data.routines;
}

export async function seedDefaultRoutines(): Promise<PlannerRoutine[]> {
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
  const res = await fetch(resolveApiUrl(`/api/planner/routines/${id}`), {
    method: "DELETE",
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(await res.text());
}

export async function applyRoutines(date?: string): Promise<{ created: number }> {
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
  const res = await fetch(resolveApiUrl("/api/planner/routines/auto-apply-today"), {
    method: "POST",
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

/** Last N days of plan + tracked usage — for designing weekly timetables. */
export async function downloadProductivityWeekExport(
  days = 7,
  format: "json" | "csv" = "json",
  options?: {
    include?: string;
    productiveOnly?: boolean;
  },
): Promise<void> {
  const params = new URLSearchParams({ days: String(days), format });
  if (options?.include) params.set("include", options.include);
  if (options?.productiveOnly) params.set("productive_only", "true");
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
    let detail = await res.text();
    try {
      const parsed = JSON.parse(detail) as { error?: { message?: string }; detail?: string };
      detail = parsed.error?.message || parsed.detail || detail;
    } catch {
      /* keep raw */
    }
    throw new Error(detail || `Export failed (${res.status})`);
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
      ? `productivity-${days}d-${stamp}.csv`
      : `productivity-${days}d-${stamp}.json`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
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

export type GoogleCalendarStatus = {
  client_configured: boolean;
  connected: boolean;
  calendar_id: string;
  has_access_token: boolean;
  redirect_uri?: string;
  setup_url?: string;
};

export async function fetchGoogleCalendarStatus(): Promise<GoogleCalendarStatus> {
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
