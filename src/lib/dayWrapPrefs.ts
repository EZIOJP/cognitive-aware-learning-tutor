/**
 * End-of-day wrap — local close stamp + tomorrow's one fix (Focus-only, no Study API).
 */

const LS_KEY = "calt.focus.day_wrap.v1";
export const DAY_WRAP_UPDATED_EVENT = "calt-focus-day-wrap";

export type DayWrapRecord = {
  date: string;
  closed: boolean;
  closed_at: string | null;
  note: string;
  /** Plain-language one-liner pinned for tomorrow morning. */
  tomorrow_fix: string;
  /** Consecutive evenings closed (incl. this one when sealed). */
  close_streak: number;
};

type Store = {
  last: DayWrapRecord | null;
  /** ISO dates closed, newest first, capped. */
  closed_days: string[];
};

function emptyRecord(date: string): DayWrapRecord {
  return {
    date,
    closed: false,
    closed_at: null,
    note: "",
    tomorrow_fix: "",
    close_streak: 0,
  };
}

function loadStore(): Store {
  try {
    const raw = localStorage.getItem(LS_KEY);
    if (!raw) return { last: null, closed_days: [] };
    const j = JSON.parse(raw) as Partial<Store>;
    return {
      last: j.last && typeof j.last === "object" ? (j.last as DayWrapRecord) : null,
      closed_days: Array.isArray(j.closed_days)
        ? j.closed_days.filter((d) => typeof d === "string")
        : [],
    };
  } catch {
    return { last: null, closed_days: [] };
  }
}

function saveStore(store: Store): void {
  localStorage.setItem(LS_KEY, JSON.stringify(store));
  try {
    window.dispatchEvent(new CustomEvent(DAY_WRAP_UPDATED_EVENT, { detail: store.last }));
  } catch {
    /* ignore */
  }
}

function streakFrom(closedDays: string[], todayIso: string): number {
  const set = new Set(closedDays);
  let n = 0;
  const d = new Date(`${todayIso}T12:00:00`);
  for (;;) {
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, "0");
    const day = String(d.getDate()).padStart(2, "0");
    const iso = `${y}-${m}-${day}`;
    if (!set.has(iso)) break;
    n += 1;
    d.setDate(d.getDate() - 1);
    if (n > 60) break;
  }
  return n;
}

export function loadDayWrap(dateIso: string): DayWrapRecord {
  const store = loadStore();
  if (store.last?.date === dateIso) {
    return {
      ...store.last,
      close_streak: streakFrom(store.closed_days, dateIso),
    };
  }
  return {
    ...emptyRecord(dateIso),
    close_streak: streakFrom(store.closed_days, dateIso),
  };
}

export function saveDayWrap(
  dateIso: string,
  patch: Partial<Omit<DayWrapRecord, "date" | "close_streak">>,
): DayWrapRecord {
  const store = loadStore();
  const prev =
    store.last?.date === dateIso ? store.last : emptyRecord(dateIso);
  const next: DayWrapRecord = {
    ...prev,
    ...patch,
    date: dateIso,
    close_streak: 0,
  };

  let closedDays = [...store.closed_days];
  if (next.closed) {
    closedDays = [dateIso, ...closedDays.filter((d) => d !== dateIso)].slice(0, 90);
  } else {
    closedDays = closedDays.filter((d) => d !== dateIso);
  }
  next.close_streak = streakFrom(closedDays, dateIso);
  saveStore({ last: next, closed_days: closedDays });
  return next;
}

/** Fix line from yesterday — for morning Home cue. */
export function yesterdayTomorrowFix(): { date: string; fix: string } | null {
  const store = loadStore();
  const last = store.last;
  if (!last?.tomorrow_fix?.trim()) return null;
  const today = new Date();
  const y = new Date(today);
  y.setDate(y.getDate() - 1);
  const p = (n: number) => String(n).padStart(2, "0");
  const yIso = `${y.getFullYear()}-${p(y.getMonth() + 1)}-${p(y.getDate())}`;
  if (last.date !== yIso) return null;
  return { date: last.date, fix: last.tomorrow_fix.trim() };
}
