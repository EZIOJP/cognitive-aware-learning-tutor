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
  remaining_minutes: number;
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
}

export interface AdherenceSummary {
  day: string;
  planned_minutes: number;
  actual_minutes: number;
  productive_minutes: number;
  effective_focus_minutes: number;
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
  const params = new URLSearchParams({
    from: from.toISOString(),
    to: to.toISOString(),
  });
  const res = await fetch(resolveApiUrl(`/api/planner/overlay/actual?${params}`), {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(await res.text());
  const data = (await res.json()) as { sessions: ActualSession[] };
  return data.sessions;
}

export async function fetchAdherence(day: Date): Promise<AdherenceSummary> {
  const params = new URLSearchParams({ day: day.toISOString() });
  const res = await fetch(resolveApiUrl(`/api/planner/adherence?${params}`), {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
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
  body: Partial<{ title: string; category: string; start_time: string; end_time: string; enabled: boolean }>,
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
  const res = await fetch(resolveApiUrl("/api/planner/routines/apply"), {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({ date: date ?? null }),
  });
  if (!res.ok) throw new Error(await res.text());
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
