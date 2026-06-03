const HUB_BASE =
  (import.meta as { env?: { VITE_API_BASE?: string } }).env?.VITE_API_BASE ||
  "http://localhost:8000";

const TOKEN_KEY = "vocab:auth-token";

function hubHeaders(): HeadersInit {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) headers.Authorization = `Bearer ${token}`;
  return headers;
}

export type HubSegment = {
  label: string;
  startHour: number;
  endHour: number;
  color: string;
  type?: string;
};

export type HubDailyPayload = {
  date: string;
  segments: HubSegment[];
  productive_minutes: number;
  sleep_minutes: number;
  life_score: number;
  time_left_hours: number;
  percent_elapsed: number;
  current_hour: number;
  vocab_events?: number;
  math_attempts?: number;
  stats: Record<string, number>;
};

export type InsightsDailyPayload = {
  date: string;
  life_score: number;
  study_minutes: number;
  productive_minutes: number;
  sleep_minutes: number;
  vocab_events: number;
  math_attempts: number;
  overall_performance: "excellent" | "good" | "needs-improvement";
};

export async function fetchHubDaily(day = "today"): Promise<HubDailyPayload | null> {
  try {
    const res = await fetch(`${HUB_BASE}/api/hub/daily/${day}`, { headers: hubHeaders() });
    if (!res.ok) return null;
    return (await res.json()) as HubDailyPayload;
  } catch {
    return null;
  }
}

export async function fetchInsightsDaily(): Promise<InsightsDailyPayload | null> {
  try {
    const res = await fetch(`${HUB_BASE}/api/insights/daily`, { headers: hubHeaders() });
    if (!res.ok) return null;
    return (await res.json()) as InsightsDailyPayload;
  } catch {
    return null;
  }
}

export type InsightsReviewPayload = {
  comments: string;
  next_steps: string[];
  goals: string[];
  overall_performance: string;
};

export async function fetchInsightsReview(): Promise<InsightsReviewPayload | null> {
  try {
    const res = await fetch(`${HUB_BASE}/api/insights/review`, {
      method: "POST",
      headers: hubHeaders(),
    });
    if (!res.ok) return null;
    return (await res.json()) as InsightsReviewPayload;
  } catch {
    return null;
  }
}

export type DashboardLayoutPayload = {
  widget_state: Record<string, { colSpan: 1 | 2; rowSpan: 1 | 2; hidden: boolean }>;
  widget_order: string[];
  focus_mode?: boolean;
};

export async function fetchDashboardLayout(): Promise<DashboardLayoutPayload | null> {
  try {
    const res = await fetch(`${HUB_BASE}/api/hub/dashboard-layout`, { headers: hubHeaders() });
    if (!res.ok) return null;
    return (await res.json()) as DashboardLayoutPayload;
  } catch {
    return null;
  }
}

export async function saveDashboardLayout(layout: DashboardLayoutPayload): Promise<boolean> {
  try {
    const res = await fetch(`${HUB_BASE}/api/hub/dashboard-layout`, {
      method: "PUT",
      headers: hubHeaders(),
      body: JSON.stringify(layout),
    });
    return res.ok;
  } catch {
    return false;
  }
}

export type LifeDailyApi = {
  date: string;
  empty?: boolean;
  life_score?: number;
  sleep_hours?: number;
  sleep_quality?: number;
  exercise_minutes?: number;
  water_glasses?: number;
  meals_healthy?: number;
  study_minutes?: number;
  tasks_completed?: number;
  deep_work_blocks?: number;
  screen_time_hours?: number;
  social_media_minutes?: number;
  outdoor_minutes?: number;
  mood_score?: number;
  stress_level?: number;
  meditation_minutes?: number;
};

export async function fetchLifeDaily(day = "today"): Promise<LifeDailyApi | null> {
  try {
    const res = await fetch(`${HUB_BASE}/api/life/daily/${day}`, { headers: hubHeaders() });
    if (!res.ok) return null;
    return (await res.json()) as LifeDailyApi;
  } catch {
    return null;
  }
}

export async function putLifeDaily(
  day: string,
  body: Record<string, number>
): Promise<{ life_score: number } | null> {
  try {
    const res = await fetch(`${HUB_BASE}/api/life/daily/${day}`, {
      method: "PUT",
      headers: hubHeaders(),
      body: JSON.stringify(body),
    });
    if (!res.ok) return null;
    const data = await res.json();
    window.dispatchEvent(new CustomEvent("hub:refresh"));
    return { life_score: data.life_score ?? 0 };
  } catch {
    return null;
  }
}

export function formatMinutesAsHours(minutes: number): string {
  const h = Math.floor(Math.max(0, minutes) / 60);
  const m = Math.round(Math.max(0, minutes) % 60);
  return h > 0 ? `${h}h ${m}m` : `${m}m`;
}

/** Maps backend plugin_id → frontend PluginDef.id (math-tutor → core). */
export const BACKEND_PLUGIN_TO_FRONTEND: Record<string, string[]> = {
  core: ["core"],
  "math-tutor": ["math-tutor"],
  "gre-vocab": ["gre-vocab"],
  "life-tracker": ["life-tracker"],
  eeg: ["eeg"],
  "focus-mirror": ["focus-mirror"],
  nutrinode: ["nutrinode"],
};

export type HubPluginRow = {
  plugin_id: string;
  enabled: boolean;
  config?: Record<string, unknown>;
  kind?: string;
  is_core?: boolean;
};

export type HubMetricRow = {
  slug: string;
  label: string;
  unit: string | null;
  source_type: string;
  feature_id: string | null;
  is_system: boolean;
  is_custom: boolean;
  user_owned: boolean;
};

export type HubCustomFeature = {
  feature_id: string;
  name: string;
  description: string | null;
  enabled: boolean;
  config: Record<string, unknown>;
  metrics: HubMetricRow[];
  created_at: string | null;
};

export type HubCatalogFeature = {
  plugin_id: string;
  name: string;
  description: string;
  kind: string;
  is_core: boolean;
  default_enabled: boolean;
  frontend_ids: string[];
  metrics: { slug: string; label: string; unit: string; source_type: string }[];
};

export async function fetchFeaturesCatalog(): Promise<HubCatalogFeature[]> {
  try {
    const res = await fetch(`${HUB_BASE}/api/hub/features/catalog`, { headers: hubHeaders() });
    if (!res.ok) return [];
    const data = await res.json();
    return data.features ?? [];
  } catch {
    return [];
  }
}

export async function fetchHubPluginsState(): Promise<{
  plugins: HubPluginRow[];
  custom_features: HubCustomFeature[];
} | null> {
  try {
    const res = await fetch(`${HUB_BASE}/api/hub/plugins`, { headers: hubHeaders() });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export async function setHubPlugin(
  pluginId: string,
  enabled: boolean,
  config?: Record<string, unknown>
): Promise<boolean> {
  try {
    const res = await fetch(`${HUB_BASE}/api/hub/plugins`, {
      method: "PUT",
      headers: hubHeaders(),
      body: JSON.stringify({ plugin_id: pluginId, enabled, config }),
    });
    return res.ok;
  } catch {
    return false;
  }
}

export async function fetchHubMetrics(): Promise<HubMetricRow[]> {
  try {
    const res = await fetch(`${HUB_BASE}/api/hub/metrics`, { headers: hubHeaders() });
    if (!res.ok) return [];
    const data = await res.json();
    return data.metrics ?? [];
  } catch {
    return [];
  }
}

export async function fetchCustomFeatures(): Promise<HubCustomFeature[]> {
  try {
    const res = await fetch(`${HUB_BASE}/api/hub/features/custom`, { headers: hubHeaders() });
    if (!res.ok) return [];
    const data = await res.json();
    return data.features ?? [];
  } catch {
    return [];
  }
}

export async function createCustomFeature(body: {
  name: string;
  description?: string;
  feature_slug: string;
  metrics: { label: string; slug: string; unit?: string; source_type?: string }[];
}): Promise<HubCustomFeature | null> {
  try {
    const res = await fetch(`${HUB_BASE}/api/hub/features/custom`, {
      method: "POST",
      headers: hubHeaders(),
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || err.error?.message || `HTTP ${res.status}`);
    }
    return await res.json();
  } catch (e) {
    throw e;
  }
}

export async function patchCustomFeature(
  featureId: string,
  body: { name?: string; description?: string | null; enabled?: boolean }
): Promise<HubCustomFeature | null> {
  const res = await fetch(`${HUB_BASE}/api/hub/features/custom/${encodeURIComponent(featureId)}`, {
    method: "PATCH",
    headers: hubHeaders(),
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || err.error?.message || `HTTP ${res.status}`);
  }
  return (await res.json()) as HubCustomFeature;
}

export async function deleteCustomFeature(featureId: string): Promise<boolean> {
  try {
    const res = await fetch(`${HUB_BASE}/api/hub/features/custom/${encodeURIComponent(featureId)}`, {
      method: "DELETE",
      headers: hubHeaders(),
    });
    return res.ok;
  } catch {
    return false;
  }
}

export async function downloadHubExport(format: "json" | "csv" = "json"): Promise<void> {
  const token = localStorage.getItem(TOKEN_KEY);
  const res = await fetch(`${HUB_BASE}/api/hub/export?format=${format}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw new Error(`Export failed (${res.status})`);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = format === "csv" ? "hub_export.csv" : "hub_export.json";
  a.click();
  URL.revokeObjectURL(url);
}

export async function postHubReading(
  slug: string,
  value: number,
  clientEventId?: string
): Promise<boolean> {
  try {
    const res = await fetch(`${HUB_BASE}/api/hub/readings`, {
      method: "POST",
      headers: hubHeaders(),
      body: JSON.stringify({
        readings: [
          {
            slug,
            value_numeric: value,
            client_event_id: clientEventId ?? `web-${slug}-${Date.now()}`,
          },
        ],
      }),
    });
    return res.ok;
  } catch {
    return false;
  }
}
