/**
 * Zepp / Amazfit Mini Program ↔ CALT wearable endpoints.
 *
 * Focus desktop shell talks to the permanent :8765 hub (Focus
 * `scripts/run/wearables_hub.py`), not Study `:8000`.
 */
import { resolveApiUrl } from "../utils/resolveBackendUrl";
import { isFocusDesktopShell } from "../utils/focusDesktopShell";

const LS_KEY = "calt:wearables:lastSync";
const TOKEN_KEY = "calt:wearables:token";
const HUB_URL_KEY = "calt:wearables:hubUrl";
const DEFAULT_TOKEN = "calt-local-wearables";
const DEFAULT_HUB_PORT = 8765;

/** Base URL for wearables routes (Focus → :8765 hub; Study browser → :8000 API). */
export function resolveWearablesBaseUrl(): string {
  if (isFocusDesktopShell()) {
    try {
      const stored = localStorage.getItem(HUB_URL_KEY)?.trim();
      if (stored) return stored.replace(/\/$/, "");
    } catch {
      /* ignore */
    }
    const env = import.meta.env.VITE_WEARABLES_HUB_URL;
    if (typeof env === "string" && env.trim()) {
      return env.trim().replace(/\/$/, "");
    }
    return `http://127.0.0.1:${DEFAULT_HUB_PORT}`;
  }
  return resolveApiUrl().replace(/\/$/, "");
}

export function getWearablesHubUrl(): string {
  try {
    return localStorage.getItem(HUB_URL_KEY)?.trim() || `http://127.0.0.1:${DEFAULT_HUB_PORT}`;
  } catch {
    return `http://127.0.0.1:${DEFAULT_HUB_PORT}`;
  }
}

export function setWearablesHubUrl(url: string) {
  try {
    const cleaned = url.trim().replace(/\/$/, "");
    if (cleaned) localStorage.setItem(HUB_URL_KEY, cleaned);
    else localStorage.removeItem(HUB_URL_KEY);
  } catch {
    /* ignore */
  }
}

export type WearableSleep = {
  score?: number;
  total_min?: number;
  deep_min?: number;
  light_min?: number;
  rem_min?: number;
  start_min?: number;
  end_min?: number;
  start_at?: string;
  end_at?: string;
  /** Host/UI flag — manual correction must win over thin watch chunks */
  manual?: boolean | number;
  stages?: Array<{ label?: string; start?: number; stop?: number }>;
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
  sleep_start_min?: number | null;
  sleep_end_min?: number | null;
  /** Local ISO-ish stamp e.g. 2026-10-13T23:00:00 */
  sleep_start_at?: string | null;
  sleep_end_at?: string | null;
  sleep_label?: string | null;
  sleep_deep_label?: string | null;
  /** Nested sleep object when reading raw day mirrors */
  sleep?: Record<string, unknown> | null;
  data_quality?: {
    sleep_ok?: boolean;
    sleep_timed?: boolean;
    sleep_stages?: number;
    hr_series?: number;
    hr_ok?: boolean;
    steps_ok?: boolean;
    collector_ok?: boolean;
    readiness_ok?: boolean;
    training_ok?: boolean;
  } | null;
  steps?: number | null;
  step_target?: number | null;
  calories?: number | null;
  calorie_target?: number | null;
  distance_m?: number | null;
  hr_last?: number | null;
  hr_resting?: number | null;
  hr_avg?: number | null;
  hr_max?: number | null;
  spo2?: number | null;
  stress?: number | null;
  /** ZeppBridge collector promotions (null = missing, not zero). */
  readiness?: number | null;
  training_load?: number | null;
  hybrid_charge?: number | null;
  physical_charge?: number | null;
  mental_charge?: number | null;
  sleep_hrv?: number | null;
  stress_min?: number | null;
  stress_max?: number | null;
  active_minutes?: number | null;
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

export type WearablePing = {
  ok?: boolean;
  at?: string;
  id?: string;
  source?: string;
  message?: string;
  kind?: string;
  local_date?: string;
};

export type WearableSyncStatus = {
  ok: boolean;
  reachable: boolean;
  last_ping?: WearablePing | null;
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
    last_hr_avg?: number | null;
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
    last_ping_at?: string;
    last_ping_id?: string;
    last_ping_source?: string;
    last_ping_message?: string;
    last_raw_path?: string;
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
  categories?: {
    present?: string[];
    count?: number;
    details?: Record<string, unknown>;
    capabilities?: Record<string, unknown> | null;
    source?: string;
    dump?: string;
  };
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

async function fetchWearableStatusFromMirror(): Promise<WearableSyncStatus | null> {
  if (!isFocusDesktopShell()) return null;
  try {
    const { focusDataUrl } = await import("../utils/focusDataUrl");
    const [syncRes, dayRes, pingRes] = await Promise.all([
      fetch(focusDataUrl("wearables_last_sync.json"), { cache: "no-store" }),
      fetch(focusDataUrl("wearable_day.json"), { cache: "no-store" }),
      fetch(focusDataUrl("wearables_ping.json"), { cache: "no-store" }),
    ]);
    const last_sync = syncRes.ok ? ((await syncRes.json()) as WearableSyncStatus["last_sync"]) : null;
    const wearable_day = dayRes.ok ? ((await dayRes.json()) as WearableDay) : null;
    const last_ping = pingRes.ok ? ((await pingRes.json()) as WearablePing) : null;
    return {
      ok: true,
      reachable: true,
      last_sync,
      last_ping,
      wearable_day,
      authentic: {
        watch_ingest: Boolean(last_sync?.last_is_watch),
        wrote_life: Boolean(last_sync?.last_wrote_life),
        verdict: last_sync?.last_is_watch ? "authentic_watch" : "waiting",
      },
      storage: { note: "Focus mirrors via calt-data (enforcer-maintained life pack)" },
    };
  } catch {
    return null;
  }
}

export async function fetchWearableStatus(): Promise<WearableSyncStatus> {
  if (isFocusDesktopShell()) {
    const mirrored = await fetchWearableStatusFromMirror();
    if (mirrored) return mirrored;
  }
  const base = resolveWearablesBaseUrl();
  const res = await fetch(`${base}/api/wearables/zepp/status`, { headers: authHeaders() });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `HTTP ${res.status}`);
  }
  return (await res.json()) as WearableSyncStatus;
}

/** Watch / Test PC → hub writes wearables_ping.json + PC tray toast. */
export async function postWearablePing(message = "Focus UI ping"): Promise<WearablePing> {
  const base = resolveWearablesBaseUrl();
  const res = await fetch(`${base}/api/wearables/zepp/ping`, {
    method: "POST",
    headers: {
      ...authHeaders(),
      "X-CALT-Wearable-Key": getWearableToken(),
    },
    body: JSON.stringify({
      source: "calt_focus_ui",
      message,
    }),
  });
  if (!res.ok) throw new Error(await res.text());
  const data = (await res.json()) as { ok?: boolean; ping?: WearablePing };
  return data.ping || { ok: !!data.ok, message };
}

export async function fetchWearableDay(localDate: string): Promise<WearableDay | null> {
  const day = localDate.slice(0, 10);
  if (isFocusDesktopShell()) {
    try {
      const { focusDataUrl } = await import("../utils/focusDataUrl");
      const today = new Date();
      const todayKey = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`;
      const path =
        day === todayKey ? "wearable_day.json" : `wearable_days/${day}.json`;
      const res = await fetch(focusDataUrl(path), { cache: "no-store" });
      if (res.ok) {
        const j = (await res.json()) as WearableDay;
        if (j && typeof j === "object") return j;
      }
      if (day === todayKey) {
        const alt = await fetch(focusDataUrl(`wearable_days/${day}.json`), { cache: "no-store" });
        if (alt.ok) return (await alt.json()) as WearableDay;
      }
      return null;
    } catch {
      return null;
    }
  }
  const base = resolveWearablesBaseUrl();
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
  dumpId?: string;
}) {
  const base = resolveWearablesBaseUrl();
  const day = payload.localDate || new Date().toISOString().slice(0, 10);
  const dumpId = payload.dumpId || `manual_${day}_${Date.now()}`;
  const res = await fetch(`${base}/api/wearables/zepp`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({
      schema: 2,
      source: payload.source || "calt_manual",
      local_date: day,
      tz_offset_min: -new Date().getTimezoneOffset(),
      captured_at: new Date().toISOString(),
      dump_id: dumpId,
      chunk_id: `${dumpId}_1`,
      checksum: `manual_${dumpId}`,
      sleep: payload.sleep,
      activity: payload.activity,
      heart: payload.heart,
      meta: { manual_correction: true, app: "calt_focus_ui" },
    }),
  });
  if (!res.ok) throw new Error(await res.text());
  const data = await res.json();
  saveLast({
    at: new Date().toISOString(),
    sleepHours: data?.sleep_hours ?? data?.sleep?.sleep_hours,
    ok: true,
  });
  return data;
}

function parseHmToMin(s: string): number | null {
  const m = /^(\d{1,2}):(\d{2})$/.exec(s.trim());
  if (!m) return null;
  const h = Number(m[1]);
  const mm = Number(m[2]);
  if (!Number.isFinite(h) || !Number.isFinite(mm) || h > 23 || mm > 59) return null;
  return h * 60 + mm;
}

function shiftDateKey(day: string, delta: number): string {
  const [y, mo, d] = day.slice(0, 10).split("-").map(Number);
  const dt = new Date(y, mo - 1, d);
  dt.setDate(dt.getDate() + delta);
  return `${dt.getFullYear()}-${String(dt.getMonth() + 1).padStart(2, "0")}-${String(dt.getDate()).padStart(2, "0")}`;
}

/** Correct sleep for a day via sync_host (keeps steps/HR; marks sleep.manual). */
export async function postManualSleepCorrection(args: {
  localDate: string;
  bedtime?: string;
  wake?: string;
  hours?: number;
  score?: number;
  deepMin?: number;
}) {
  const day = args.localDate.slice(0, 10);
  const bed = args.bedtime ? parseHmToMin(args.bedtime) : null;
  const wake = args.wake ? parseHmToMin(args.wake) : null;
  let totalMin: number | null = null;
  let startMin: number | null = null;
  let endMin: number | null = null;
  let startAt: string | undefined;
  let endAt: string | undefined;

  if (bed != null && wake != null) {
    startMin = bed;
    endMin = wake;
    totalMin = wake > bed ? wake - bed : wake + 1440 - bed;
    if (totalMin <= 0 || totalMin > 16 * 60) {
      throw new Error("Sleep window must be between 0 and 16 hours");
    }
    const startDay = wake > bed ? day : shiftDateKey(day, -1);
    startAt = `${startDay}T${String(Math.floor(bed / 60)).padStart(2, "0")}:${String(bed % 60).padStart(2, "0")}:00`;
    endAt = `${day}T${String(Math.floor(wake / 60)).padStart(2, "0")}:${String(wake % 60).padStart(2, "0")}:00`;
  } else if (args.hours != null && Number.isFinite(args.hours) && args.hours > 0) {
    totalMin = Math.round(args.hours * 60);
    if (totalMin > 16 * 60) throw new Error("Sleep hours max 16");
  } else {
    throw new Error("Set bedtime + wake, or hours");
  }

  const sleep: WearableSleep = {
    manual: 1,
    total_min: totalMin,
    score: args.score != null && Number.isFinite(args.score) ? Math.round(args.score) : undefined,
    deep_min:
      args.deepMin != null && Number.isFinite(args.deepMin) ? Math.round(args.deepMin) : undefined,
    start_min: startMin ?? undefined,
    end_min: endMin ?? undefined,
    start_at: startAt,
    end_at: endAt,
    // Single asleep block so Health shows a dated window without fake stages.
    stages:
      startMin != null && endMin != null
        ? [
            {
              label: "asleep",
              start: startMin,
              stop: endMin > startMin ? endMin : endMin + 1440,
            },
          ]
        : undefined,
  };

  return postWearableIngest({
    localDate: day,
    source: "calt_manual",
    sleep,
  });
}

/** @deprecated use postWearableIngest */
export async function postWearableSleep(sleep: WearableSleep, localDate?: string) {
  return postWearableIngest({ sleep, localDate });
}

export async function fetchWearablePlans(
  horizonHours = 24,
  client: "web_test" | "mini_program" = "web_test",
): Promise<WearablePlan[]> {
  const base = resolveWearablesBaseUrl();
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
  const base = resolveWearablesBaseUrl();
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
