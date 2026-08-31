/** API helpers for day-status + policy against Cognitive FastAPI or tracker hub. */

export type DayStatus = {
  ok: boolean;
  day?: string;
  browser_mode?: string;
  browser_mode_label?: string;
  morning?: {
    next?: string;
    bible_done?: boolean;
    plan_done?: boolean;
    hint?: string;
    suggested_wake?: {
      suggested_local?: string;
      note?: string;
      writable_alarm?: boolean;
    } | null;
    bible_url?: string;
    plan_url?: string;
  };
  checklist?: Array<{
    id: string;
    label: string;
    done: boolean;
    active?: boolean;
    cta?: string | null;
  }>;
  hard_block?: {
    armed?: boolean;
    locked?: boolean;
    unlocked?: boolean;
    productive_minutes?: number;
    productive_label?: string;
    daily_goal_minutes?: number;
    daily_goal_label?: string;
    remaining_minutes?: number;
    remaining_label?: string;
  };
  tracker?: {
    alive?: boolean;
    status?: string;
    sessions_today?: number;
  };
  tracker_alive?: boolean;
  wearables?: {
    ok?: boolean;
    last_ingest_at?: string;
    sleep_hours?: number;
    sleep_score?: number | null;
    sleep_label?: string | null;
    steps?: number;
    stand_hours?: number;
    sitting_min?: number | null;
    sitting_label?: string | null;
    tz_offset_min?: number | null;
    watch_local_date?: string | null;
    captured_at?: string | null;
    recovery_hint?: {
      label?: string;
      suggested_focus_hours?: number;
      factor?: number;
    };
  };
  productivity?: {
    pulse?: number;
    pulse_label?: string;
    goal_pct?: number;
    goal_met?: boolean;
    productive_label?: string;
    distracting_label?: string;
    focus_quality?: {
      score?: number;
      label?: string;
      switches?: number;
      on_plan_minutes?: number;
    };
    weekly?: {
      avg_pulse?: number;
      goal_met_days?: number;
      top_drain?: string | null;
    };
    alerts?: Array<{
      id?: string;
      label?: string;
      triggered?: boolean;
      current_seconds?: number;
      max_seconds?: number;
    }>;
    study_mode_nudge?: { active?: boolean; until?: string | null };
  };
  comms?: {
    api_up?: boolean;
    web_up?: boolean;
    startup_grace?: boolean;
    extension?: {
      status?: string;
      age_s?: number | null;
      source?: string | null;
      selftracker_status?: string;
      calt_gate_status?: string;
      selftracker_age_s?: number | null;
      calt_gate_age_s?: number | null;
      false_positives?: string[];
      false_negatives?: string[];
    };
    why_rules_idle?: string[];
    current_issue?: { why?: string; how_to_fix?: string; cases?: string[] };
    last_incident?: { ts?: string; kind?: string; why?: string; how_to_fix?: string };
    edge_policy?: {
      may_close_edge?: boolean;
      may_close_candidate?: boolean;
      may_open_new_window?: boolean;
    };
  };
  schema?: number;
  notify?: { title?: string; body?: string };
  limits?: Record<string, string>;
};

export type MobileAlert = {
  title?: string;
  body?: string;
  fingerprint?: string;
  ts?: string;
};

function trimBase(base: string): string {
  return base.trim().replace(/\/+$/, "");
}

export async function fetchDayStatus(
  baseUrl: string,
  opts: { jwt?: string; wearableKey?: string; preferHub?: boolean } = {},
): Promise<DayStatus> {
  const base = trimBase(baseUrl);
  if (!base) throw new Error("Set server URL in Settings");

  const headers: Record<string, string> = { Accept: "application/json" };
  if (opts.jwt) headers.Authorization = `Bearer ${opts.jwt}`;
  if (opts.wearableKey) headers["X-CALT-Wearable-Key"] = opts.wearableKey;

  const paths = opts.preferHub
    ? ["/api/hub/day-status", "/api/behavior/day-status"]
    : ["/api/behavior/day-status", "/api/hub/day-status"];

  let lastErr = "unreachable";
  for (const path of paths) {
    try {
      const res = await fetch(`${base}${path}`, { headers });
      if (!res.ok) {
        lastErr = `${path} HTTP ${res.status}`;
        continue;
      }
      const data = (await res.json()) as DayStatus;
      if (data && data.ok) return data;
      lastErr = `${path} bad payload`;
    } catch (e) {
      lastErr = e instanceof Error ? e.message : String(e);
    }
  }
  throw new Error(lastErr);
}

export async function fetchMobileAlerts(
  baseUrl: string,
  jwt: string,
  drain = true,
): Promise<MobileAlert[]> {
  const base = trimBase(baseUrl);
  const res = await fetch(
    `${base}/api/behavior/mobile-alerts?drain=${drain ? "true" : "false"}`,
    {
      headers: {
        Accept: "application/json",
        Authorization: `Bearer ${jwt}`,
      },
    },
  );
  if (!res.ok) return [];
  const data = await res.json();
  return Array.isArray(data?.alerts) ? data.alerts : [];
}

export async function setHardBlockArmed(
  baseUrl: string,
  jwt: string,
  armed: boolean,
): Promise<void> {
  const base = trimBase(baseUrl);
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    Accept: "application/json",
  };
  if (jwt && jwt !== "solo") headers.Authorization = `Bearer ${jwt}`;
  const res = await fetch(`${base}/api/behavior/policy`, {
    method: "PUT",
    headers,
    body: JSON.stringify({ hard_block_enabled: armed }),
  });
  if (!res.ok) {
    const t = await res.text();
    throw new Error(t || `HTTP ${res.status}`);
  }
}

export async function confirmMorningPlan(baseUrl: string, jwt: string): Promise<void> {
  const base = trimBase(baseUrl);
  const headers: Record<string, string> = { Accept: "application/json" };
  if (jwt && jwt !== "solo") headers.Authorization = `Bearer ${jwt}`;
  const res = await fetch(`${base}/api/behavior/morning-plan/confirm`, {
    method: "POST",
    headers,
  });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const j = await res.json();
      detail = j.detail || detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
}
