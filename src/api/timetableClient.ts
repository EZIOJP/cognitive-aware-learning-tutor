import { resolveApiUrl } from "../utils/resolveBackendUrl";

const TOKEN_KEY = "vocab:auth-token";

function authHeaders(): HeadersInit {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) headers.Authorization = `Bearer ${token}`;
  return headers;
}

export interface TimetableTask {
  id: number;
  title: string;
  description?: string | null;
  sessions: TimetableSession[];
}

export interface TimetableSlot {
  day: string;
  start: string;
  end: string;
  task_index: number;
  title?: string;
}

export interface TimetableSession {
  session_id: string;
  start_time: string | null;
  end_time: string | null;
  source: string;
  category?: string | null;
  productivity_score?: number | null;
}

export interface Timetable {
  id: number;
  name: string;
  created_at: string | null;
  tasks: TimetableTask[];
  slots: TimetableSlot[];
}

export interface TimetableListResponse {
  timetables: Timetable[];
  live_desktop_sessions: TimetableSession[];
  days: string[];
}

export interface SyncTimetablePayload {
  name: string;
  tasks: { title: string; description?: string }[];
  slots?: TimetableSlot[];
  sessions?: TimetableSession[];
  replace?: boolean;
}

export async function fetchTimetables(): Promise<TimetableListResponse> {
  const res = await fetch(resolveApiUrl("/api/timetable"), { headers: authHeaders() });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function fetchTimetableTemplate(): Promise<SyncTimetablePayload> {
  const res = await fetch(resolveApiUrl("/api/timetable/template"), { headers: authHeaders() });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function syncTimetable(payload: SyncTimetablePayload): Promise<{ timetable_id: number }> {
  const res = await fetch(resolveApiUrl("/api/timetable/sync"), {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function importTimetableJson(data: unknown): Promise<{ timetable_id?: number; planner_blocks_created?: number; schedule_type?: string }> {
  const res = await fetch(resolveApiUrl("/api/timetable/import/json"), {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function importTimetableText(
  text: string,
  applyToPlanner = true,
): Promise<{ timetable_id?: number; planner_blocks_created?: number; schedule_type?: string; message?: string }> {
  const res = await fetch(resolveApiUrl("/api/timetable/import/text"), {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({ text, apply_to_planner: applyToPlanner }),
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(err);
  }
  return res.json();
}
