import { useCallback, useEffect, useState } from "react";
import { fetchActualOverlay, fetchAdherenceRange, fetchPlannerBlocks } from "../api/plannerClient";
import type { ActualSession, PlannerBlock } from "../api/plannerClient";
import { fetchDesktopTimeline } from "../api/behaviorClient";
import type { DesktopTimeline } from "../api/behaviorClient";
import {
  type AdherenceDay,
  daysEndingOn,
  toDayString,
} from "../components/productivity/planVsActualUtils";

export type FetchState<T> = {
  data: T;
  loading: boolean;
  error: string | null;
  refetch: () => void;
};

function useFetch<T>(
  fetcher: () => Promise<T>,
  deps: unknown[],
  initial: T,
): FetchState<T> {
  const [data, setData] = useState<T>(initial);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  const refetch = useCallback(() => setTick((k) => k + 1), []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetcher()
      .then((result) => {
        if (!cancelled) setData(result);
      })
      .catch((e: unknown) => {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : "Failed to load");
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick]);

  return { data, loading, error, refetch };
}

export function usePlannerBlocks(from: Date, to: Date): FetchState<PlannerBlock[]> {
  const fromMs = from.getTime();
  const toMs = to.getTime();
  return useFetch(
    () => fetchPlannerBlocks(new Date(fromMs), new Date(toMs)),
    [fromMs, toMs],
    [],
  );
}

export function useActualOverlay(
  from: Date,
  to: Date,
  refreshKey = 0,
): FetchState<ActualSession[]> {
  const fromMs = from.getTime();
  const toMs = to.getTime();
  return useFetch(
    () => fetchActualOverlay(new Date(fromMs), new Date(toMs)),
    [fromMs, toMs, refreshKey],
    [],
  );
}

export function useDesktopTimeline(day: string, refreshKey = 0): FetchState<DesktopTimeline | null> {
  return useFetch(
    () => fetchDesktopTimeline(day),
    [day, refreshKey],
    null,
  );
}

function normalizeAdherenceDay(
  date: string,
  raw: Awaited<ReturnType<typeof fetchAdherenceRange>>[number] | null,
): AdherenceDay {
  if (!raw) {
    return {
      date,
      planned: 0,
      actual: 0,
      productive: 0,
      pct: null,
      blockCount: 0,
      noPlan: true,
    };
  }
  return {
    date: raw.day ?? date,
    planned: raw.planned_minutes,
    actual: raw.actual_minutes,
    productive: raw.productive_minutes,
    pct: raw.adherence_pct,
    blockCount: raw.block_count,
    noPlan: raw.block_count === 0,
  };
}

export function useAdherenceRange(days: number, endDay?: Date): FetchState<AdherenceDay[]> {
  const endMs = endDay ? startOfDayMs(endDay) : startOfDayMs(new Date());
  return useFetch(
    async () => {
      const end = new Date(endMs);
      const rows = await fetchAdherenceRange(days, end);
      const byDate = new Map(rows.map((r) => [r.day, r]));
      return daysEndingOn(end, days)
        .map((dateStr) => normalizeAdherenceDay(dateStr, byDate.get(dateStr) ?? null))
        .sort((a, b) => a.date.localeCompare(b.date));
    },
    [days, endMs],
    [],
  );
}

function startOfDayMs(d: Date): number {
  const x = new Date(d);
  x.setHours(0, 0, 0, 0);
  return x.getTime();
}

export { toDayString };
