import { resolveApiUrl } from "../utils/resolveBackendUrl";
import { llmBodyFields, type LlmOverrides } from "./transcriptsClient";

const TOKEN_KEY = "vocab:auth-token";

function authHeaders(): HeadersInit {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) headers.Authorization = `Bearer ${token}`;
  return headers;
}

// ── Types ─────────────────────────────────────────────────────────────────────

export interface BrowserDomain {
  domain: string;
  seconds: number;
  category?: string;
  productivity_score?: number;
}

export interface BrowserStats {
  connected: boolean;
  events_today: number;
  total_events: number;
  top_category: string;
  avg_productivity_score: number;
  top_domains: BrowserDomain[];
  recent_sites: string[];
  category_breakdown: Record<string, number>;
  date: string | null;
  source: string | null;
}

export interface BrowserSite {
  site: string;
  seconds: number;
  category: string;
  productivity_score: number;
}

export interface AppSession {
  kind?: "app" | "browser";
  exe: string;
  seconds: number;
  category: string;
  productivity_score: number;
  sites?: BrowserSite[];
}

export interface DesktopStats {
  sessions: AppSession[];
  total_seconds: number;
  avg_productivity_score: number;
  source: string;
  date: string;
  tracker_running: boolean;
  last_event_at?: string | null;
}

export interface TrackerHealth {
  tracker_alive: boolean;
  status: "running" | "stale" | "no_data";
  last_event_at: string | null;
  sessions_today: number;
  total_seconds_today: number;
  source: string;
  process_alive?: boolean;
  checkpoint_age_s?: number | null;
  log_age_s?: number | null;
  tracker_process_count?: number;
  hint?: string | null;
}

export interface TimelineInterval {
  session_id: string;
  start_time: string;
  end_time: string;
  duration_seconds: number;
  category: string | null;
  app_name: string | null;
  window_title: string | null;
  site?: string | null;
  productivity_score: number | null;
}

export interface DesktopTimeline {
  date: string;
  intervals: TimelineInterval[];
  total_seconds: number;
}

// ── API calls ─────────────────────────────────────────────────────────────────

/**
 * Browser-tab stats (from Chrome extension → /ws/behavior).
 */
export async function fetchBrowserStats(day?: string): Promise<BrowserStats> {
  const qs = day ? `?day=${day}` : "";
  const res = await fetch(resolveApiUrl(`/api/behavior/stats${qs}`), {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(`behavior/stats: ${res.status}`);
  return res.json();
}

/**
 * Desktop-app stats (from desktop_tracker.py → /ws/behavior).
 */
export async function fetchDesktopStats(day?: string): Promise<DesktopStats> {
  const qs = day ? `?day=${day}` : "";
  const res = await fetch(resolveApiUrl(`/api/behavior/desktop-stats${qs}`), {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(`behavior/desktop-stats: ${res.status}`);
  return res.json();
}

export async function fetchTrackerHealth(): Promise<TrackerHealth> {
  const res = await fetch(resolveApiUrl("/api/behavior/tracker-health"), {
    headers: authHeaders(),
  });
  if (res.status === 404) {
    throw new Error(
      "tracker-health: 404 — restart the API server (close the API cmd window and run run.bat) so new productivity routes load",
    );
  }
  if (!res.ok) throw new Error(`behavior/tracker-health: ${res.status}`);
  return res.json();
}

export async function fetchDesktopTimeline(day?: string): Promise<DesktopTimeline> {
  const qs = day ? `?day=${day}` : "";
  const res = await fetch(resolveApiUrl(`/api/behavior/desktop-timeline${qs}`), {
    headers: authHeaders(),
  });
  if (res.status === 404) {
    throw new Error(
      "desktop-timeline: 404 — restart the API server (close the API cmd window and run run.bat)",
    );
  }
  if (!res.ok) throw new Error(`behavior/desktop-timeline: ${res.status}`);
  return res.json();
}

export interface TrackerForceSyncResult {
  flushed: boolean;
  tracker_running: boolean;
  last_event_at: string | null;
  message: string;
}

export async function forceTrackerSync(): Promise<TrackerForceSyncResult> {
  const res = await fetch(resolveApiUrl("/api/behavior/tracker-force-sync"), {
    method: "POST",
    headers: authHeaders(),
  });
  if (res.status === 404) {
    throw new Error(
      "tracker-force-sync: 404 — restart the API server so new productivity routes load",
    );
  }
  if (!res.ok) throw new Error(`behavior/tracker-force-sync: ${res.status}`);
  return res.json();
}

// ── Classification review API ────────────────────────────────────────────────

export interface ClassificationSuggestion {
  id: number;
  key: string;
  key_type: string;
  suggested_category: string;
  confidence: number;
  sample_titles: string[];
  occurrence_count: number;
  status: string;
  reviewed_at: string | null;
  created_at: string | null;
}

export async function scanClassifications(
  limit = 20,
  llm?: LlmOverrides,
): Promise<{
  suggestions: ClassificationSuggestion[];
  scanned: number;
  created: number;
  llm_error?: string;
}> {
  const res = await fetch(resolveApiUrl("/api/classification/scan"), {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({ limit, ...llmBodyFields(llm) }),
  });
  if (!res.ok) throw new Error(`classification/scan: ${res.status}`);
  return res.json();
}

export async function fetchPendingClassifications(): Promise<{
  suggestions: ClassificationSuggestion[];
}> {
  const res = await fetch(resolveApiUrl("/api/classification/pending"), {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(`classification/pending: ${res.status}`);
  return res.json();
}

export async function previewClassification(id: number): Promise<{
  suggestion: ClassificationSuggestion;
  impact: { count: number; total_minutes: number; date_range: string[] | null; sample: unknown[] };
}> {
  const res = await fetch(resolveApiUrl(`/api/classification/${id}/preview`), {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(`classification/preview: ${res.status}`);
  return res.json();
}

export async function approveClassification(id: number): Promise<{
  status: string;
  affected_rows: number;
}> {
  const res = await fetch(resolveApiUrl(`/api/classification/${id}/approve`), {
    method: "POST",
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(`classification/approve: ${res.status}`);
  return res.json();
}

export async function rejectClassification(
  id: number,
  overrideCategory?: string,
): Promise<{ status: string; affected_rows?: number; category?: string }> {
  const res = await fetch(resolveApiUrl(`/api/classification/${id}/reject`), {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({ override_category: overrideCategory ?? null }),
  });
  if (!res.ok) throw new Error(`classification/reject: ${res.status}`);
  return res.json();
}

export async function editAndApproveClassification(
  id: number,
  category: string,
): Promise<{ status: string; category: string; affected_rows: number }> {
  const res = await fetch(resolveApiUrl(`/api/classification/${id}/edit-and-approve`), {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({ category }),
  });
  if (!res.ok) throw new Error(`classification/edit-and-approve: ${res.status}`);
  return res.json();
}

export async function revertClassification(id: number): Promise<{
  status: string;
  reverted_rows: number;
}> {
  const res = await fetch(resolveApiUrl(`/api/classification/${id}/revert`), {
    method: "POST",
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(`classification/revert: ${res.status}`);
  return res.json();
}
