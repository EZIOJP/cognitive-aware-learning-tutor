/**
 * Zepp / Amazfit Mini Program ↔ CALT wearable endpoints.
 */
import { resolveApiUrl } from "../utils/resolveBackendUrl";

const LS_KEY = "calt:wearables:lastSync";
const TOKEN_KEY = "calt:wearables:token";
const DEFAULT_TOKEN = "calt-local-wearables";

export type WearableSleep = {
  score?: number;
  total_min?: number;
  deep_min?: number;
  start_min?: number;
  end_min?: number;
};

export type WearablePlan = {
  id: number;
  title: string;
  category: string;
  start_at: string;
  end_at: string;
  status: string;
  source?: string;
};

export type LastWearableSync = {
  at: string;
  sleepHours?: number;
  planCount?: number;
  ok: boolean;
  error?: string;
};

export type WearableDay = {
  local_date?: string;
  source?: string;
  synced_at?: string | null;
  sleep_hours?: number | null;
  sleep_score?: number | null;
  sleep_deep_min?: number | null;
  sleep_label?: string | null;
  sleep_deep_label?: string | null;
  steps?: number | null;
  step_target?: number | null;
  calories?: number | null;
  calorie_target?: number | null;
  distance_m?: number | null;
  hr_last?: number | null;
  hr_resting?: number | null;
  spo2?: number | null;
  stress?: number | null;
  pai_today?: number | null;
  pai_total?: number | null;
  stand_hours?: number | null;
  stand_target?: number | null;
  stand_label?: string | null;
  battery_pct?: number | null;
  sitting_min?: number | null;
  sitting_label?: string | null;
  tz_offset_min?: number | null;
  watch_local_date?: string | null;
  captured_at?: string | null;
  last_captured_at?: string | null;
  last_dump_id?: string | null;
  last_chunk_id?: string | null;
  last_checksum?: string | null;
  capabilities?: Record<string, unknown> | null;
  /** Full nested snapshot as posted by the watch mini program */
  payload?: Record<string, unknown> | null;
};

export type WearableSyncStatus = {
  ok: boolean;
  reachable: boolean;
  last_sync: {
    updated_at?: string;
    last_ingest_at?: string;
    last_plans_at?: string;
    last_plan_count?: number;
    last_sleep_hours?: number;
    last_sleep_quality?: number;
    last_steps?: number | null;
    last_step_target?: number | null;
    last_exercise_minutes?: number | null;
    last_calories?: number | null;
    last_distance_m?: number | null;
    last_hr?: number | null;
    last_spo2?: number | null;
    last_stress?: number | null;
    last_pai?: number | null;
    last_stand?: number | null;
    last_sitting_min?: number | null;
    last_sitting_label?: string | null;
    last_sleep_label?: string | null;
    last_tz_offset_min?: number | null;
    last_watch_local_date?: string | null;
    last_captured_at?: string | null;
    last_exercise_label?: string | null;
    last_outdoor_minutes?: number | null;
    last_outdoor_label?: string | null;
    last_chunk_part?: number | null;
    last_chunk_total?: number | null;
    last_battery?: number | null;
    last_source?: string;
    last_is_watch?: boolean;
    last_wrote_life?: boolean;
    last_event?: string;
    last_local_date?: string;
    last_dump_id?: string | null;
    last_chunk_id?: string | null;
    last_event_id?: string | null;
    last_duplicate?: boolean;
    last_manual_dump?: boolean;
  } | null;
  applied_to_life?: {
    date?: string;
    sleep_hours?: number;
    sleep_label?: string | null;
    sleep_quality?: number;
    exercise_minutes?: number;
    exercise_label?: string | null;
    outdoor_minutes?: number;
    outdoor_label?: string | null;
    stress_level?: number;
    life_score?: number;
  } | null;
  wearable_day?: WearableDay | null;
  authentic?: {
    watch_ingest?: boolean;
    wrote_life?: boolean;
    plans_from_watch?: boolean;
    verdict?: string;
  };
  estimates?: {
    steps_to_exercise?: string;
    exercise_from_last_steps?: number | null;
    distance_to_outdoor?: string;
    stress_to_life?: string;
    sleep_quality?: string;
  };
  storage?: Record<string, string>;
};

export function getWearableToken(): string {
  try {
    return localStorage.getItem(TOKEN_KEY) || DEFAULT_TOKEN;
  } catch {
    return DEFAULT_TOKEN;
  }
}

export function setWearableToken(t: string) {
  try {
    localStorage.setItem(TOKEN_KEY, t.trim() || DEFAULT_TOKEN);
  } catch {
    /* ignore */
  }
}

function authHeaders(): HeadersInit {
  return {
    Authorization: `Bearer ${getWearableToken()}`,
    "Content-Type": "application/json",
  };
}

export function loadLastWearableSync(): LastWearableSync | null {
  try {
    const raw = localStorage.getItem(LS_KEY);
    return raw ? (JSON.parse(raw) as LastWearableSync) : null;
  } catch {
    return null;
  }
}

function saveLast(s: LastWearableSync) {
  try {
    localStorage.setItem(LS_KEY, JSON.stringify(s));
  } catch {
    /* ignore */
  }
}

export async function fetchWearableStatus(): Promise<WearableSyncStatus> {
  const base = resolveApiUrl().replace(/\/$/, "");
  const res = await fetch(`${base}/api/wearables/zepp/status`, { headers: authHeaders() });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `HTTP ${res.status}`);
  }
  return (await res.json()) as WearableSyncStatus;
}

export async function fetchWearableDay(localDate: string): Promise<WearableDay | null> {
  const base = resolveApiUrl().replace(/\/$/, "");
  const day = localDate.slice(0, 10);
  const res = await fetch(`${base}/api/wearables/zepp/day/${encodeURIComponent(day)}`, {
    headers: authHeaders(),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `HTTP ${res.status}`);
  }
  const data = (await res.json()) as { ok?: boolean; day?: WearableDay | null };
  return data.day ?? null;
}

/** Manual test from the web UI (same contract as the watch Side Service). */
export async function postWearableIngest(payload: {
  sleep?: WearableSleep;
  activity?: { steps?: number; target?: number };
  heart?: { last?: number; resting?: number };
  localDate?: string;
  source?: string;
}) {
  const base = resolveApiUrl().replace(/\/$/, "");
  const res = await fetch(`${base}/api/wearables/zepp`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({
      schema: 2,
      source: payload.source || "web_test",
      local_date: payload.localDate || new Date().toISOString().slice(0, 10),
      tz_offset_min: -new Date().getTimezoneOffset(),
      captured_at: new Date().toISOString(),
      sleep: payload.sleep,
      activity: payload.activity,
      heart: payload.heart,
    }),
  });
  if (!res.ok) throw new Error(await res.text());
  const data = await res.json();
  saveLast({
    at: new Date().toISOString(),
    sleepHours: data?.sleep?.sleep_hours,
    ok: true,
  });
  return data;
}

/** @deprecated use postWearableIngest */
export async function postWearableSleep(sleep: WearableSleep, localDate?: string) {
  return postWearableIngest({ sleep, localDate });
}

export async function fetchWearablePlans(
  horizonHours = 24,
  client: "web_test" | "mini_program" = "web_test",
): Promise<WearablePlan[]> {
  const base = resolveApiUrl().replace(/\/$/, "");
  const res = await fetch(
    `${base}/api/wearables/zepp/plans?horizon_hours=${horizonHours}&client=${client}`,
    { headers: authHeaders() },
  );
  if (!res.ok) throw new Error(await res.text());
  const data = await res.json();
  const plans = (data.plans || []) as WearablePlan[];
  const prev = loadLastWearableSync();
  saveLast({
    at: new Date().toISOString(),
    sleepHours: prev?.sleepHours,
    planCount: plans.length,
    ok: true,
  });
  return plans;
}

/** PC-side path check: health + plans (does not claim watch authenticity). */
export async function pingWearableWithPlans(horizonHours = 24): Promise<{
  healthOk: boolean;
  planCount: number;
  plans: WearablePlan[];
  authentic_watch: boolean;
}> {
  const base = resolveApiUrl().replace(/\/$/, "");
  const healthRes = await fetch(`${base}/api/wearables/zepp/health`, {
    headers: authHeaders(),
  });
  const healthOk = healthRes.ok;
  const plansRes = await fetch(
    `${base}/api/wearables/zepp/plans?horizon_hours=${horizonHours}&client=web_test`,
    { headers: authHeaders() },
  );
  if (!plansRes.ok) throw new Error(await plansRes.text());
  const data = await plansRes.json();
  const plans = (data.plans || []) as WearablePlan[];
  return {
    healthOk,
    planCount: plans.length,
    plans,
    authentic_watch: false,
  };
}
