import { resolveApiUrl } from "../utils/resolveBackendUrl";
import { formatHoursMins } from "../utils/formatDuration";
import { isFocusDesktopShell } from "../utils/focusDesktopShell";

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
  /** Overnight sleep: arc runs bedtime → 24 and 0 → wake */
  crossesMidnight?: boolean;
};

export type HubDailyPayload = {
  date: string;
  segments: HubSegment[];
  productive_minutes: number;
  productive_label?: string;
  sleep_minutes: number;
  sleep_label?: string;
  sleep_score?: number | null;
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
  study_label?: string;
  productive_minutes: number;
  productive_label?: string;
  sleep_minutes: number;
  sleep_label?: string;
  vocab_events: number;
  math_attempts: number;
  overall_performance: "excellent" | "good" | "needs-improvement";
};

function localDateKeyNow(): string {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function hourOfLocalIso(iso: string): number | null {
  const t = Date.parse(iso);
  if (!Number.isFinite(t)) return null;
  const d = new Date(t);
  return d.getHours() + d.getMinutes() / 60 + d.getSeconds() / 3600;
}

/** Focus shell: synthesize hub daily from enforcer mirrors (no Study :8000). */
async function fetchHubDailyFromFocusMirrors(day: string): Promise<HubDailyPayload | null> {
  const { focusDataUrl } = await import("../utils/focusDataUrl");
  const dateKey = day === "today" ? localDateKeyNow() : String(day).slice(0, 10);
  const isToday = dateKey === localDateKeyNow();

  const [life, rollupRes, sleepRes, wearRes] = await Promise.all([
    fetchLifeDailyFromMirror(day === "today" ? "today" : dateKey).catch(() => null),
    fetch(focusDataUrl("day_rollup.json"), { cache: "no-store" }).catch(() => null),
    fetch(focusDataUrl("sleep_windows.json"), { cache: "no-store" }).catch(() => null),
    fetch(
      focusDataUrl(isToday ? "wearable_day.json" : `wearable_days/${dateKey}.json`),
      { cache: "no-store" },
    ).catch(() => null),
  ]);

  const rollup = rollupRes?.ok
    ? ((await rollupRes.json()) as {
        local_date?: string;
        productive_minutes?: number;
      })
    : null;
  const sleepPack = sleepRes?.ok
    ? ((await sleepRes.json()) as {
        windows?: Array<{ date?: string; start?: string; end?: string; minutes?: number }>;
      })
    : null;
  const wear = wearRes?.ok
    ? ((await wearRes.json()) as {
        sleep_hours?: number | null;
        sleep_score?: number | null;
        steps?: number | null;
      })
    : null;

  const segments: HubSegment[] = [];
  const win = (sleepPack?.windows || []).find((w) => String(w.date || "").slice(0, 10) === dateKey);
  if (win?.start && win?.end) {
    const startH = hourOfLocalIso(win.start);
    const endH = hourOfLocalIso(win.end);
    const mins =
      typeof win.minutes === "number" && win.minutes > 0
        ? win.minutes
        : startH != null && endH != null
          ? Math.max(1, Math.round(((endH - startH + 24) % 24) * 60))
          : 0;
    if (startH != null && endH != null && mins >= 12) {
      const crosses = endH < startH || String(win.start).slice(0, 10) !== String(win.end).slice(0, 10);
      segments.push({
        label: "Sleep",
        type: "sleep",
        startHour: startH,
        endHour: endH,
        color: "#6366f1",
        crossesMidnight: crosses,
      });
    }
  }

  const productive =
    rollup && (!rollup.local_date || rollup.local_date === dateKey)
      ? Math.max(0, Math.floor(Number(rollup.productive_minutes) || 0))
      : Math.max(0, Math.floor(Number(life?.study_minutes) || 0));

  const sleepHours =
    presentPositive(wear?.sleep_hours) ??
    presentPositive(life?.sleep_hours) ??
    (typeof win?.minutes === "number" ? win.minutes / 60 : 0);
  const sleepMinutes = Math.max(0, Math.round(sleepHours * 60));

  const now = new Date();
  const currentHour = isToday
    ? now.getHours() + now.getMinutes() / 60 + now.getSeconds() / 3600
    : 24;
  const timeLeft = Math.max(0, 24 - currentHour);
  const percentElapsed = Math.round((Math.min(24, currentHour) / 24) * 1000) / 10;

  return {
    date: dateKey,
    segments,
    productive_minutes: productive,
    productive_label: formatHoursMins(productive),
    sleep_minutes: sleepMinutes,
    sleep_label: sleepMinutes > 0 ? formatHoursMins(sleepMinutes) : undefined,
    sleep_score: wear?.sleep_score ?? life?.sleep_quality ?? null,
    life_score: typeof life?.life_score === "number" ? life.life_score : 0,
    time_left_hours: Math.round(timeLeft * 10) / 10,
    percent_elapsed: percentElapsed,
    current_hour: currentHour,
    stats: {
      tracker_productive_minutes: productive,
      steps: Number(wear?.steps) || 0,
    },
  };
}

function presentPositive(n: number | null | undefined): number | null {
  return typeof n === "number" && Number.isFinite(n) && n > 0 ? n : null;
}

export async function fetchHubDaily(day = "today"): Promise<HubDailyPayload | null> {
  try {
    if (isFocusDesktopShell()) {
      return await fetchHubDailyFromFocusMirrors(day);
    }
    const res = await fetch(`${resolveApiUrl()}/api/hub/daily/${day}`, { headers: hubHeaders() });
    if (!res.ok) return null;
    return (await res.json()) as HubDailyPayload;
  } catch {
    return null;
  }
}

export async function fetchInsightsDaily(): Promise<InsightsDailyPayload | null> {
  try {
    const res = await fetch(`${resolveApiUrl()}/api/insights/daily`, { headers: hubHeaders() });
    if (!res.ok) return null;
    return (await res.json()) as InsightsDailyPayload;
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
    const res = await fetch(`${resolveApiUrl()}/api/hub/dashboard-layout`, { headers: hubHeaders() });
    if (!res.ok) return null;
    return (await res.json()) as DashboardLayoutPayload;
  } catch {
    return null;
  }
}

export async function saveDashboardLayout(layout: DashboardLayoutPayload): Promise<boolean> {
  try {
    const res = await fetch(`${resolveApiUrl()}/api/hub/dashboard-layout`, {
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

async function fetchLifeDailyFromMirror(day: string): Promise<LifeDailyApi | null> {
  const { focusDataUrl } = await import("../utils/focusDataUrl");
  const key = day === "today" ? "today" : String(day).slice(0, 10);
  // Prefer enforcer-packed 14-day history (one file) when asking for a dated row.
  if (key !== "today") {
    try {
      const packRes = await fetch(focusDataUrl("life_history_14.json"), { cache: "no-store" });
      if (packRes.ok) {
        const pack = (await packRes.json()) as { days?: LifeDailyApi[] };
        const hit = (pack.days || []).find((d) => String(d?.date || "").slice(0, 10) === key);
        if (hit) return hit;
      }
    } catch {
      /* fall through to per-day file */
    }
  }
  const name = key === "today" ? "life_today.json" : `life_days/${key}.json`;
  const mr = await fetch(focusDataUrl(name), { cache: "no-store" });
  if (!mr.ok) return null;
  return (await mr.json()) as LifeDailyApi;
}

/** Focus shell: one mirror read for the Life Score trend (enforcer-maintained). */
export async function fetchLifeHistory14(): Promise<LifeDailyApi[]> {
  if (!isFocusDesktopShell()) {
    const today = new Date();
    const pad = (n: number) => String(n).padStart(2, "0");
    const keyOf = (d: Date) =>
      `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
    const days: string[] = [];
    for (let i = 13; i >= 0; i--) {
      const dt = new Date(today);
      dt.setDate(dt.getDate() - i);
      days.push(keyOf(dt));
    }
    const rows = await Promise.all(days.map((d) => fetchLifeDaily(d)));
    return days.map((d, i) => rows[i] || { date: d, empty: true });
  }
  try {
    const { focusDataUrl } = await import("../utils/focusDataUrl");
    const res = await fetch(focusDataUrl("life_history_14.json"), { cache: "no-store" });
    if (res.ok) {
      const pack = (await res.json()) as { days?: LifeDailyApi[] };
      if (Array.isArray(pack.days) && pack.days.length) return pack.days;
    }
  } catch {
    /* fall through */
  }
  // Legacy: parallel per-day mirrors (still no hub).
  const today = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  const days: string[] = [];
  for (let i = 13; i >= 0; i--) {
    const dt = new Date(today);
    dt.setDate(dt.getDate() - i);
    days.push(`${dt.getFullYear()}-${pad(dt.getMonth() + 1)}-${pad(dt.getDate())}`);
  }
  const rows = await Promise.all(days.map((d) => fetchLifeDailyFromMirror(d).catch(() => null)));
  return days.map((d, i) => rows[i] || { date: d, empty: true });
}

export async function fetchLifeDaily(day = "today"): Promise<LifeDailyApi | null> {
  try {
    if (isFocusDesktopShell()) {
      // Mirrors first — enforcer maintains life_*; hub is ingest-only.
      const mirrored = await fetchLifeDailyFromMirror(day).catch(() => null);
      if (mirrored) return mirrored;
      return null;
    }
    const res = await fetch(`${resolveApiUrl()}/api/life/daily/${day}`, { headers: hubHeaders() });
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
    const res = await fetch(`${resolveApiUrl()}/api/life/daily/${day}`, {
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
  return formatHoursMins(minutes);
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
    const res = await fetch(`${resolveApiUrl()}/api/hub/features/catalog`, { headers: hubHeaders() });
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
    const res = await fetch(`${resolveApiUrl()}/api/hub/plugins`, { headers: hubHeaders() });
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
    const res = await fetch(`${resolveApiUrl()}/api/hub/plugins`, {
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
    const res = await fetch(`${resolveApiUrl()}/api/hub/metrics`, { headers: hubHeaders() });
    if (!res.ok) return [];
    const data = await res.json();
    return data.metrics ?? [];
  } catch {
    return [];
  }
}

export async function fetchCustomFeatures(): Promise<HubCustomFeature[]> {
  try {
    const res = await fetch(`${resolveApiUrl()}/api/hub/features/custom`, { headers: hubHeaders() });
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
    const res = await fetch(`${resolveApiUrl()}/api/hub/features/custom`, {
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
  const res = await fetch(`${resolveApiUrl()}/api/hub/features/custom/${encodeURIComponent(featureId)}`, {
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
    const res = await fetch(`${resolveApiUrl()}/api/hub/features/custom/${encodeURIComponent(featureId)}`, {
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
  const res = await fetch(`${resolveApiUrl()}/api/hub/export?format=${format}`, {
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

export async function rebuildHubDaily(day?: string): Promise<boolean> {
  try {
    const q = day ? `?day=${encodeURIComponent(day)}` : "";
    const res = await fetch(`${resolveApiUrl()}/api/hub/daily/rebuild${q}`, {
      method: "POST",
      headers: hubHeaders(),
    });
    if (res.ok) {
      window.dispatchEvent(new CustomEvent("hub:refresh"));
    }
    return res.ok;
  } catch {
    return false;
  }
}

export async function postHubReading(
  slug: string,
  value: number,
  clientEventId?: string
): Promise<boolean> {
  try {
    const res = await fetch(`${resolveApiUrl()}/api/hub/readings`, {
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
