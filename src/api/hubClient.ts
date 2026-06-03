const HUB_BASE =
  (import.meta as { env?: { VITE_API_BASE?: string } }).env?.VITE_API_BASE ||
  "http://localhost:8000";

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
  stats: Record<string, number>;
};

export async function fetchHubDaily(day = "today"): Promise<HubDailyPayload | null> {
  try {
    const res = await fetch(`${HUB_BASE}/api/hub/daily/${day}`);
    if (!res.ok) return null;
    return (await res.json()) as HubDailyPayload;
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
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) return null;
    const data = await res.json();
    return { life_score: data.life_score ?? 0 };
  } catch {
    return null;
  }
}
