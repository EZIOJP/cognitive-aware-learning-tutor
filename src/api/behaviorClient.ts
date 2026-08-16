import { resolveApiUrl } from "../utils/resolveBackendUrl";
import { notifyPipeline } from "../utils/dataPipelineBus";
import { llmBodyFieldsForTask, type LlmOverrides } from "./transcriptsClient";

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
  source?: string | null;
  productivity_score: number | null;
  override_productive?: boolean | null;
}

export interface DesktopTimeline {
  date: string;
  intervals: TimelineInterval[];
  total_seconds: number;
}

// ── API calls ─────────────────────────────────────────────────────────────────

/**
 * Browser-tab stats (from Edge SelfTracker → /ws/behavior).
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
  const data = (await res.json()) as TrackerForceSyncResult;
  notifyPipeline("tracker");
  return data;
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
    body: JSON.stringify({ limit, ...llmBodyFieldsForTask("classify", llm) }),
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

export interface ProductivityPolicy {
  productive_categories: string[];
  blocked_categories: string[];
  app_overrides: Record<string, string>;
  threshold: number;
  hard_block_enabled?: boolean;
  daily_goal_minutes?: number;
  hard_block_gaming?: boolean;
  hard_block_exes?: string[];
}

export interface MorningRewardAward {
  points: number;
  label: string;
  granted: boolean;
  granted_at?: string | null;
}

export interface MorningRewards {
  day: string;
  awards: {
    bible?: MorningRewardAward;
    plan?: MorningRewardAward;
  };
  total_points: number;
  bible_points?: number;
  plan_points?: number;
}

export interface MorningPlanWindow {
  start: string;
  end: string;
  start_hhmm: string;
  eod_hhmm: string;
  start_clock: string;
  end_clock: string;
  end_label: string;
  phase: "awaiting_bible" | "before_start" | "open" | "after_eod" | string;
  confirm_available: boolean;
  reason: string;
  bible_completed_at?: string | null;
}

export interface MorningAutoPlan {
  drafted?: boolean;
  day?: string;
  titles?: string[];
  created?: number;
  confirmed?: boolean;
  reason?: string | null;
  drafted_at?: string;
}

/** Read-only MORNING_* / auto-plan flags from server env (Settings display). */
export interface MorningGateConfig {
  gate?: boolean;
  plan_start?: string;
  plan_eod?: string;
  auto_plan?: boolean;
  auto_plan_confirm?: boolean;
}

export interface MorningDailyPractice {
  show?: boolean;
  due_count?: number;
  action?: string;
  label?: string;
  to?: string;
  reason?: string;
}

export interface MorningGate {
  enabled: boolean;
  day: string;
  bible_done: boolean;
  plan_done: boolean;
  plan_confirmed?: boolean;
  blocks_today: number;
  next: "bible" | "plan" | "open";
  allow_paths: string[];
  rewards?: MorningRewards;
  hint?: string;
  plan_window?: MorningPlanWindow;
  bible_url?: string;
  plan_url?: string;
  auto_plan?: MorningAutoPlan | null;
  daily_practice?: MorningDailyPractice | null;
  config?: MorningGateConfig;
}

export interface BrowserGateSection {
  mode?: string;
  mode_label?: string;
  enforce?: boolean;
  block_other?: boolean;
  block_watch_sites?: boolean;
  block_porn?: boolean;
  block_social?: boolean;
  block_keywords?: boolean;
  strict_allowlist?: boolean;
  morning_next?: string;
  daytime_default?: string;
  free_after?: string;
  free_override_active?: boolean;
  allow_free_life?: boolean;
  free_life_allow_domains?: string[];
  note?: string;
  allow_domains?: string[];
  watch_domains?: string[];
  allowed_browsers?: string[];
  known_browsers?: string[];
  browser_installers?: string[];
  bible_url?: string;
  plan_url?: string;
  redirect_url?: string | null;
  redirect_reason?: string | null;
}

export interface RewardDayStatus {
  qualifying_days: number;
  qualifying_days_per_reward: number;
  days_to_next_reward: number;
  earned: number;
  spent: number;
  available: number;
  active_today: boolean;
  confirm_phrase: string;
}

export interface DistractionGate {
  enabled: boolean;
  locked: boolean;
  unlocked: boolean;
  productive_minutes: number;
  daily_goal_minutes: number;
  remaining_minutes: number;
  hard_block_gaming: boolean;
  hard_block_exes: string[];
  day: string;
  bible_minutes?: number;
  chapters_completed_today?: string[];
  chapter_goal?: { done?: number; target?: number; met?: boolean };
  chapter_goal_met?: boolean;
  game_bank_remaining_minutes?: number;
  game_bank_remaining_seconds?: number;
  day_unlimited?: boolean;
  day_pass?: boolean;
  day_pass_status?: {
    week_start?: string;
    limit?: number;
    used?: number;
    remaining?: number;
    already_active_today?: boolean;
    confirm_phrase?: string;
  };
  reward_day?: boolean;
  reward_day_status?: RewardDayStatus;
  unlock_mode?: string;
  morning?: MorningGate;
  /** Day browser mode payload (SelfTracker source of truth). */
  browser?: BrowserGateSection;
  browser_mode?: string;
  /** Present when demo clock module is available (enabled or not). */
  demo?: DemoClockStatus;
}

export interface DemoClockStatus {
  enabled: boolean;
  now_iso?: string | null;
  day?: string | null;
  real_now_iso?: string;
  real_day?: string;
  read_only?: boolean;
  note?: string;
}

export interface DemoRealDay {
  day: string;
  events: number;
  sources: string[];
}

export interface DemoClockPayload extends DemoClockStatus {
  real_days?: DemoRealDay[];
}

export async function fetchDemoClock(): Promise<DemoClockPayload> {
  const res = await fetch(resolveApiUrl("/api/behavior/demo-clock"), {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(`behavior/demo-clock: ${res.status}`);
  return res.json();
}

export async function setDemoClock(body: {
  enabled: boolean;
  now_iso?: string | null;
}): Promise<DemoClockStatus> {
  const res = await fetch(resolveApiUrl("/api/behavior/demo-clock"), {
    method: "PUT",
    headers: authHeaders(),
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(detail || `behavior/demo-clock: ${res.status}`);
  }
  return res.json();
}

export async function clearDemoClock(): Promise<DemoClockStatus> {
  const res = await fetch(resolveApiUrl("/api/behavior/demo-clock"), {
    method: "DELETE",
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(`behavior/demo-clock: ${res.status}`);
  return res.json();
}

export async function fetchProductivityPolicy(): Promise<ProductivityPolicy> {
  const res = await fetch(resolveApiUrl("/api/behavior/policy"), { headers: authHeaders() });
  if (!res.ok) throw new Error(`behavior/policy: ${res.status}`);
  return res.json();
}

export async function fetchDistractionGate(): Promise<DistractionGate> {
  const res = await fetch(resolveApiUrl("/api/behavior/distraction-gate"), {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(`behavior/distraction-gate: ${res.status}`);
  return res.json();
}

export async function confirmMorningPlan(opts?: {
  goals?: string;
}): Promise<{
  ok: boolean;
  morning?: MorningGate;
}> {
  const res = await fetch(resolveApiUrl("/api/behavior/morning-plan/confirm"), {
    method: "POST",
    headers: { ...authHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify({ goals: opts?.goals ?? "" }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || `morning-plan/confirm: ${res.status}`);
  }
  return res.json();
}

export async function draftMorningAutoPlan(opts?: {
  addMore?: boolean;
}): Promise<{
  ok: boolean;
  auto_plan?: MorningAutoPlan | null;
  morning?: MorningGate;
  draft?: {
    skipped?: boolean;
    reason?: string | null;
    created?: number;
    titles?: string[];
    ask?: string;
  };
}> {
  const res = await fetch(resolveApiUrl("/api/behavior/morning-plan/auto-draft"), {
    method: "POST",
    headers: { ...authHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify({ add_more: Boolean(opts?.addMore) }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || `morning-plan/auto-draft: ${res.status}`);
  }
  return res.json();
}

export async function saveProductivityPolicy(
  body: Partial<ProductivityPolicy>,
): Promise<ProductivityPolicy> {
  const res = await fetch(resolveApiUrl("/api/behavior/policy"), {
    method: "PUT",
    headers: authHeaders(),
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function fetchCategoryScores(): Promise<{ scores: Record<string, number> }> {
  const res = await fetch(resolveApiUrl("/api/behavior/category-scores"), {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(`category-scores: ${res.status}`);
  return res.json();
}

export async function saveCategoryScores(
  scores: Record<string, number>,
): Promise<{ updated: number; scores: Record<string, number> }> {
  const res = await fetch(resolveApiUrl("/api/behavior/category-scores"), {
    method: "PUT",
    headers: authHeaders(),
    body: JSON.stringify({ scores }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function patchTrackedSession(
  sessionId: string,
  body: { category?: string; override_productive?: boolean | null },
): Promise<{ session: Record<string, unknown> }> {
  const res = await fetch(resolveApiUrl(`/api/behavior/tracked-sessions/${encodeURIComponent(sessionId)}`), {
    method: "PATCH",
    headers: authHeaders(),
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

/** Lecture Notes / quiz / vocab / math (active focused tab) → study minutes. */
export async function postStudyPresence(body: {
  path: string;
  focused?: boolean;
  client?: string;
  title?: string;
  notes_loaded?: boolean;
  reading?: boolean;
  document_id?: string;
}): Promise<{ ok: boolean; credited_seconds?: number; reason?: string; lane?: string }> {
  const res = await fetch(resolveApiUrl("/api/behavior/study-presence"), {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
