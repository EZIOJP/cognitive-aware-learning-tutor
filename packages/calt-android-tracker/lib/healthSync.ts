/**
 * Health Connect → CALT wearables ingest.
 *
 * Native Health Connect needs a dev/APK build (`npx expo prebuild`).
 * Expo Go: use `postHealthRecords` with records collected elsewhere, or CALT Sync.
 */

import { Platform } from "react-native";
import { loadSettings } from "./settings";

export type HcRecord = {
  type: string;
  count?: number;
  steps?: number;
  value?: number;
  bpm?: number;
  percentage?: number;
  duration_min?: number;
  minutes?: number;
  score?: number;
  rmssd_ms?: number;
  kcal?: number;
  meters?: number;
  title?: string;
  exercise_type?: string;
  local_date?: string;
  start?: string;
  end?: string;
};

function todayLocal(): string {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

export async function postHealthRecords(
  records: HcRecord[],
  opts?: { localDate?: string; baseUrl?: string; wearableKey?: string }
): Promise<{ ok: boolean; categories?: { present?: string[]; count?: number }; detail?: string }> {
  const s = await loadSettings();
  const base = (opts?.baseUrl || s.baseUrl || "").replace(/\/$/, "").replace(":8765", ":8000");
  const key = opts?.wearableKey || s.wearableKey || "calt-local-wearables";
  const res = await fetch(`${base}/api/wearables/zepp`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${key}`,
      "X-CALT-Wearable-Key": key,
    },
    body: JSON.stringify({
      source: "health_connect",
      local_date: opts?.localDate || todayLocal(),
      health_connect_records: records,
    }),
  });
  const data = (await res.json().catch(() => ({}))) as {
    ok?: boolean;
    detail?: string;
    categories?: { present?: string[]; count?: number };
  };
  if (!res.ok) {
    return { ok: false, detail: data.detail || `HTTP ${res.status}` };
  }
  return { ok: true, categories: data.categories };
}

/** Best-effort native read. Returns null when module / permissions unavailable. */
export async function readHealthConnectToday(): Promise<HcRecord[] | null> {
  if (Platform.OS !== "android") return null;
  try {
    // Optional native module — only present after prebuild + react-native-health-connect.
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const HC = require("react-native-health-connect");
    if (!HC?.initialize || !HC?.readRecords) return null;
    await HC.initialize();
    const granted = await HC.requestPermission([
      { accessType: "read", recordType: "Steps" },
      { accessType: "read", recordType: "SleepSession" },
      { accessType: "read", recordType: "HeartRate" },
      { accessType: "read", recordType: "RestingHeartRate" },
      { accessType: "read", recordType: "OxygenSaturation" },
      { accessType: "read", recordType: "ActiveCaloriesBurned" },
      { accessType: "read", recordType: "Distance" },
      { accessType: "read", recordType: "ExerciseSession" },
    ]);
    if (!granted) return null;

    const day = todayLocal();
    const start = `${day}T00:00:00.000Z`;
    const end = new Date().toISOString();
    const timeRange = { operator: "between", startTime: start, endTime: end };
    const out: HcRecord[] = [];

    const pull = async (recordType: string, map: (r: Record<string, unknown>) => HcRecord | null) => {
      try {
        const result = await HC.readRecords(recordType, { timeRangeFilter: timeRange });
        const rows = (result?.records || result || []) as Record<string, unknown>[];
        for (const row of rows) {
          const mapped = map(row);
          if (mapped) out.push({ ...mapped, local_date: day });
        }
      } catch {
        /* type unsupported on device */
      }
    };

    await pull("Steps", (r) => ({
      type: "Steps",
      count: Number(r.count ?? r.COUNT ?? 0) || undefined,
    }));
    await pull("SleepSession", (r) => {
      const startT = String(r.startTime || "");
      const endT = String(r.endTime || "");
      let duration_min: number | undefined;
      try {
        duration_min = Math.max(
          0,
          Math.round((Date.parse(endT) - Date.parse(startT)) / 60000)
        );
      } catch {
        duration_min = undefined;
      }
      return { type: "SleepSession", duration_min, start: startT, end: endT };
    });
    await pull("HeartRate", (r) => {
      const samples = (r.samples as { beatsPerMinute?: number }[]) || [];
      const last = samples[samples.length - 1]?.beatsPerMinute ?? r.beatsPerMinute;
      return last != null ? { type: "HeartRate", bpm: Number(last) } : null;
    });
    await pull("RestingHeartRate", (r) =>
      r.beatsPerMinute != null
        ? { type: "RestingHeartRate", bpm: Number(r.beatsPerMinute) }
        : null
    );
    await pull("OxygenSaturation", (r) =>
      r.percentage != null
        ? { type: "OxygenSaturation", percentage: Number(r.percentage) }
        : null
    );
    await pull("ActiveCaloriesBurned", (r) =>
      r.energy != null || r.kilocalories != null
        ? {
            type: "ActiveCaloriesBurned",
            kcal: Number(
              (r.energy as { inKilocalories?: number })?.inKilocalories ?? r.kilocalories
            ),
          }
        : null
    );
    await pull("Distance", (r) => {
      const m =
        (r.distance as { inMeters?: number })?.inMeters ??
        r.meters ??
        (r.distance != null ? Number(r.distance) : undefined);
      return m != null ? { type: "Distance", meters: Number(m) } : null;
    });
    await pull("ExerciseSession", (r) => {
      const startT = String(r.startTime || "");
      const endT = String(r.endTime || "");
      let duration_min: number | undefined;
      try {
        duration_min = Math.max(
          0,
          Math.round((Date.parse(endT) - Date.parse(startT)) / 60000)
        );
      } catch {
        duration_min = undefined;
      }
      return {
        type: "ExerciseSession",
        title: String(r.title || r.exerciseType || "workout"),
        duration_min,
        start: startT,
        end: endT,
      };
    });

    return out.length ? out : [];
  } catch {
    return null;
  }
}

export async function syncHealthConnectToPc(): Promise<{
  ok: boolean;
  detail: string;
  count?: number;
  categories?: string[];
}> {
  const records = await readHealthConnectToday();
  if (records === null) {
    return {
      ok: false,
      detail:
        "Health Connect native module unavailable. Use a prebuild APK, or keep CALT Sync on the watch.",
    };
  }
  if (!records.length) {
    return {
      ok: false,
      detail: "No Health Connect samples for today (check Zepp → Health Connect sharing).",
    };
  }
  const res = await postHealthRecords(records);
  if (!res.ok) return { ok: false, detail: res.detail || "ingest failed" };
  return {
    ok: true,
    detail: `Synced ${records.length} record(s)`,
    count: records.length,
    categories: res.categories?.present,
  };
}
