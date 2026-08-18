/** Shutdown ritual state — local-first carry-forward for next morning. */

const LS_KEY = "productivity:shutdown:v1";
export const SHUTDOWN_UPDATED_EVENT = "productivity:shutdown-updated";

export type ShutdownRecord = {
  date: string;
  reflection: string;
  carriedTitles: string[];
  droppedCount: number;
  completedAt: string;
};

export function loadLastShutdown(): ShutdownRecord | null {
  try {
    const raw = localStorage.getItem(LS_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as ShutdownRecord;
    if (!parsed?.date) return null;
    return parsed;
  } catch {
    return null;
  }
}

export function saveShutdown(record: ShutdownRecord): void {
  localStorage.setItem(LS_KEY, JSON.stringify(record));
  window.dispatchEvent(new CustomEvent(SHUTDOWN_UPDATED_EVENT, { detail: record }));
}

export function shutdownDoneForDay(dayIso: string): boolean {
  const last = loadLastShutdown();
  return last?.date === dayIso;
}

/** Titles rolled forward at last shutdown — shown on next morning plan. */
export function carriedTitlesForMorning(): string[] {
  const last = loadLastShutdown();
  if (!last?.carriedTitles?.length) return [];
  return last.carriedTitles.filter((t) => t.trim());
}

export function formatShutdownDayLabel(iso: string): string {
  try {
    const d = new Date(`${iso}T12:00:00`);
    return d.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });
  } catch {
    return iso;
  }
}