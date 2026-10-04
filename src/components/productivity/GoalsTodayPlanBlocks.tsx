import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { CalendarDays, Loader2, RefreshCw, Trash2 } from "lucide-react";
import {
  applyRoutines,
  blockColor,
  deletePlannerBlock,
  fetchPlannerBlocks,
  type PlannerBlock,
  type StudyTask,
} from "../../api/plannerClient";
import { fetchDayLoopMirror } from "../../api/focusMirrors";
import { cn } from "../../app/components/ui/utils";
import {
  isFreeCategory,
  isStudyFocusCategory,
  isTrimmableStudyBlock,
  studyMinutesFromBlocks,
  syncStudyHoursToFocusGoal,
} from "./fillFocusStudyGaps";

function todayYmd(): string {
  const t = new Date();
  const y = t.getFullYear();
  const m = String(t.getMonth() + 1).padStart(2, "0");
  const d = String(t.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

function formatHm(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  } catch {
    return "—";
  }
}

function blockMinutes(b: PlannerBlock): number {
  const a = new Date(b.start_at).getTime();
  const e = new Date(b.end_at).getTime();
  if (!Number.isFinite(a) || !Number.isFinite(e) || e <= a) return Math.max(0, b.planned_minutes || 0);
  return Math.max(0, Math.round((e - a) / 60_000));
}

/** Day window for strip: 05:00–23:00 local (matches typical Focus day). */
const STRIP_START_MIN = 5 * 60;
const STRIP_END_MIN = 23 * 60;
const STRIP_SPAN = STRIP_END_MIN - STRIP_START_MIN;

function minuteOfDay(iso: string): number {
  const d = new Date(iso);
  return d.getHours() * 60 + d.getMinutes();
}

function canRemoveBlock(b: PlannerBlock): boolean {
  // Study/work focus blocks can always be removed from Goals.
  // Routines (food/spiritual/personal/free) stay — edit those on Routines/Calendar.
  if (b.status === "done") return false;
  return isStudyFocusCategory(b.category || "") || isTrimmableStudyBlock(b);
}

type Props = {
  /** Daily focus target in hours (from Goals hero). */
  focusHours: number;
  /** Optional study task titles/minutes used when packing focus blocks. */
  studyTasks?: StudyTask[];
  refreshKey?: number;
  onChanged?: () => void;
  /** Prefer parent tab switch — avoid react-router Link (Focus uses `react-router` HashRouter). */
  onOpenCalendar?: () => void;
};

/**
 * Goals step: see today's plan + sync study hours to the daily focus goal
 * (fill free gaps when under; trim surplus study when over / goal lowered).
 */
export function GoalsTodayPlanBlocks({
  focusHours,
  studyTasks,
  refreshKey = 0,
  onChanged,
  onOpenCalendar,
}: Props) {
  const [blocks, setBlocks] = useState<PlannerBlock[]>([]);
  const [loading, setLoading] = useState(true);
  const [applying, setApplying] = useState(false);
  const [removingId, setRemovingId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const prevFocusRef = useRef<number | null>(null);
  const syncingRef = useRef(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const day = new Date();
      const start = new Date(day);
      start.setHours(0, 0, 0, 0);
      const end = new Date(day);
      end.setHours(23, 59, 59, 999);
      const list = await fetchPlannerBlocks(start, end);
      setBlocks(
        list
          .filter((b) => b.status !== "cancelled" && b.status !== "rolled")
          .sort((a, b) => new Date(a.start_at).getTime() - new Date(b.start_at).getTime()),
      );
    } catch (e: unknown) {
      setBlocks([]);
      setError(e instanceof Error ? e.message : "Could not load plan blocks");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load, refreshKey]);

  const goalMins = Math.round(Math.max(0, focusHours) * 60);
  const studyMins = useMemo(() => studyMinutesFromBlocks(blocks), [blocks]);
  const totalMins = useMemo(
    () => blocks.reduce((n, b) => n + blockMinutes(b), 0),
    [blocks],
  );

  const studyHoursPlanned = studyMins / 60;
  const pct = goalMins > 0 ? Math.min(100, Math.round((studyMins / goalMins) * 100)) : 0;
  const shortfallH = Math.max(0, (goalMins - studyMins) / 60);
  const surplusH = Math.max(0, (studyMins - goalMins) / 60);

  const runSync = useCallback(
    async (opts?: { withRoutines?: boolean }) => {
      if (syncingRef.current) return;
      syncingRef.current = true;
      setApplying(true);
      setError(null);
      setStatus(null);
      try {
        let routinesCreated = 0;
        if (opts?.withRoutines) {
          const routines = await applyRoutines(todayYmd());
          routinesCreated = routines.created;
        }
        const day = new Date();
        const start = new Date(day);
        start.setHours(0, 0, 0, 0);
        const end = new Date(day);
        end.setHours(23, 59, 59, 999);
        const latest = await fetchPlannerBlocks(start, end);
        let wakeHm: string | null = null;
        let bedtimeHm: string | null = null;
        try {
          const loop = await fetchDayLoopMirror();
          const w = loop?.wake_hm;
          const b = loop?.bedtime_hm;
          wakeHm = typeof w === "string" ? w : null;
          bedtimeHm = typeof b === "string" ? b : null;
        } catch {
          /* defaults inside sync */
        }
        const fill = await syncStudyHoursToFocusGoal({
          focusHours,
          blocks: latest,
          wakeHm,
          bedtimeHm,
          studyTasks,
        });
        await load();
        onChanged?.();

        const bits: string[] = [];
        if (routinesCreated > 0) bits.push(`${routinesCreated} routine`);
        if (fill.created > 0) {
          bits.push(
            `${fill.created} study block${fill.created === 1 ? "" : "s"} (+${(fill.minutesAdded / 60).toFixed(1)}h)`,
          );
        }
        if (fill.deleted > 0) {
          bits.push(
            `removed ${fill.deleted} study (+${(fill.minutesRemoved / 60).toFixed(1)}h trimmed)`,
          );
        }

        if (bits.length === 0) {
          const have = studyMinutesFromBlocks(latest);
          const goal = Math.round(Math.max(0, focusHours) * 60);
          if (Math.abs(goal - have) < 25) {
            setStatus("Study hours match today's focus goal.");
          } else if (have > goal) {
            setStatus(
              `${((have - goal) / 60).toFixed(1)}h over — remove a study block below, or lower goal further.`,
            );
          } else {
            setStatus("No free gaps left for study — clear a slot or edit on Calendar.");
          }
        } else {
          const still =
            fill.shortfallAfter >= 25
              ? ` · still ${(fill.shortfallAfter / 60).toFixed(1)}h short`
              : fill.minutesRemoved > 0
                ? " · matched goal"
                : " · goal covered";
          setStatus(`Synced ${bits.join(" · ")}${still}.`);
        }
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : "Sync failed");
      } finally {
        setApplying(false);
        syncingRef.current = false;
      }
    },
    [focusHours, studyTasks, load, onChanged],
  );

  // When daily focus drops below planned study, trim surplus study blocks automatically.
  useEffect(() => {
    const prev = prevFocusRef.current;
    prevFocusRef.current = focusHours;
    if (prev == null) return;
    if (focusHours >= prev - 0.05) return;
    if (loading || blocks.length === 0) return;
    const have = studyMinutesFromBlocks(blocks);
    const goal = Math.round(Math.max(0, focusHours) * 60);
    if (have - goal < 25) return;
    const t = window.setTimeout(() => {
      void runSync({ withRoutines: false });
    }, 350);
    return () => window.clearTimeout(t);
  }, [focusHours, loading, blocks, runSync]);

  const handleRemove = async (b: PlannerBlock) => {
    if (!canRemoveBlock(b)) return;
    setRemovingId(b.id);
    setError(null);
    setStatus(null);
    try {
      await deletePlannerBlock(b.id);
      await load();
      onChanged?.();
      setStatus(`Removed “${b.title}”.`);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Could not remove block");
    } finally {
      setRemovingId(null);
    }
  };

  return (
    <section className="goals-today-plan space-y-2.5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h4 className="text-xs font-semibold text-foreground flex items-center gap-1.5">
          <CalendarDays size={13} className="text-sky-300" aria-hidden />
          Today&apos;s plan
        </h4>
        <div className="flex items-center gap-2">
          <button
            type="button"
            disabled={applying || loading}
            onClick={() => void runSync({ withRoutines: true })}
            title="Apply routines, then add or trim study blocks so planned study matches daily focus hours"
            className="inline-flex items-center gap-1 rounded-lg bg-amber-600/80 hover:bg-amber-600 px-2.5 py-1 text-[11px] font-medium text-amber-50 disabled:opacity-50"
          >
            {applying ? <Loader2 size={12} className="animate-spin" /> : <RefreshCw size={12} />}
            Apply study hours
          </button>
          <button
            type="button"
            onClick={() => {
              if (onOpenCalendar) {
                onOpenCalendar();
                return;
              }
              window.location.hash = "#/productivity?tab=calendar";
            }}
            className="text-[11px] text-sky-300/90 hover:text-sky-200 hover:underline"
          >
            Calendar
          </button>
        </div>
      </div>

      <div className="rounded-lg border border-white/8 bg-black/30 px-2.5 py-2 space-y-1.5">
        <div className="flex items-baseline justify-between gap-2 text-[11px]">
          <span className="text-muted-foreground">
            Study{" "}
            <span className="text-foreground/90 tabular-nums font-medium">
              {studyHoursPlanned.toFixed(1)}h
            </span>
            <span className="text-muted-foreground"> / {focusHours.toFixed(1)}h focus</span>
          </span>
          {shortfallH > 0.05 ? (
            <span className="text-amber-200/85 tabular-nums">{shortfallH.toFixed(1)}h short</span>
          ) : surplusH > 0.05 ? (
            <span className="text-sky-200/85 tabular-nums">{surplusH.toFixed(1)}h over</span>
          ) : goalMins > 0 && studyMins > 0 ? (
            <span className="text-emerald-300/90">Matches goal</span>
          ) : null}
        </div>
        <div className="h-1.5 rounded-full bg-white/8 overflow-hidden" aria-hidden>
          <div
            className={cn(
              "h-full rounded-full transition-[width] duration-300",
              pct >= 100 ? "bg-emerald-400" : "bg-sky-400",
            )}
            style={{ width: `${Math.min(100, pct)}%` }}
          />
        </div>
        <p className="text-[10px] text-muted-foreground">
          Study/work blocks count toward focus · {blocks.length} block
          {blocks.length === 1 ? "" : "s"}
          {totalMins !== studyMins ? ` · ${(totalMins / 60).toFixed(1)}h including routines` : ""}
          {surplusH > 0.05
            ? " · lower focus or remove study below"
            : shortfallH > 0.05
              ? " · Apply to fill free gaps"
              : ""}
        </p>
      </div>

      {/* Compact day strip */}
      <div
        className="relative h-7 rounded-md border border-white/8 bg-black/40 overflow-hidden"
        aria-hidden={blocks.length === 0}
      >
        {blocks.map((b) => {
          const s = Math.max(STRIP_START_MIN, Math.min(STRIP_END_MIN, minuteOfDay(b.start_at)));
          const e = Math.max(s + 5, Math.min(STRIP_END_MIN, minuteOfDay(b.end_at)));
          const left = ((s - STRIP_START_MIN) / STRIP_SPAN) * 100;
          const width = ((e - s) / STRIP_SPAN) * 100;
          const study = isStudyFocusCategory(b.category || "");
          return (
            <div
              key={b.id}
              title={`${b.title} ${formatHm(b.start_at)}–${formatHm(b.end_at)}`}
              className={cn(
                "absolute top-0.5 bottom-0.5 rounded-sm opacity-90",
                !study && "opacity-40",
              )}
              style={{
                left: `${left}%`,
                width: `${Math.max(width, 0.8)}%`,
                backgroundColor: blockColor(b.category || "study", b.color),
              }}
            />
          );
        })}
        {loading && blocks.length === 0 ? (
          <div className="absolute inset-0 flex items-center justify-center text-[10px] text-muted-foreground">
            <Loader2 size={12} className="animate-spin mr-1" /> Loading…
          </div>
        ) : null}
        {!loading && blocks.length === 0 ? (
          <div className="absolute inset-0 flex items-center justify-center text-[10px] text-muted-foreground px-2 text-center">
            No blocks yet — Apply study hours or edit on Calendar
          </div>
        ) : null}
      </div>
      <div className="flex justify-between text-[9px] text-muted-foreground tabular-nums px-0.5">
        <span>5am</span>
        <span>noon</span>
        <span>11pm</span>
      </div>

      {blocks.length > 0 ? (
        <ul className="max-h-44 overflow-y-auto space-y-1 pr-0.5">
          {blocks.map((b) => {
            const study = isStudyFocusCategory(b.category || "");
            const removable = canRemoveBlock(b);
            return (
              <li
                key={b.id}
                className="flex items-center gap-2 rounded-md px-1.5 py-1 text-[11px] hover:bg-white/[0.03] group"
              >
                <span
                  className="h-2 w-2 rounded-full shrink-0"
                  style={{ backgroundColor: blockColor(b.category || "study", b.color) }}
                />
                <span className="tabular-nums text-muted-foreground shrink-0 w-[7.5rem]">
                  {formatHm(b.start_at)}–{formatHm(b.end_at)}
                </span>
                <span className="truncate text-foreground/90 flex-1 min-w-0">{b.title}</span>
                <span className="text-[10px] text-muted-foreground shrink-0">
                  {study ? "study" : isFreeCategory(b.category || "") ? "free" : "routine"}
                </span>
                {removable ? (
                  <button
                    type="button"
                    disabled={removingId === b.id || applying}
                    onClick={() => void handleRemove(b)}
                    title="Remove this study block from today"
                    aria-label={`Remove ${b.title}`}
                    className="shrink-0 p-1 rounded text-muted-foreground hover:text-rose-300 opacity-70 group-hover:opacity-100 disabled:opacity-40"
                  >
                    {removingId === b.id ? (
                      <Loader2 size={12} className="animate-spin" />
                    ) : (
                      <Trash2 size={12} />
                    )}
                  </button>
                ) : (
                  <span className="w-6 shrink-0" aria-hidden />
                )}
              </li>
            );
          })}
        </ul>
      ) : null}

      {status ? <p className="text-[11px] text-emerald-200/90">{status}</p> : null}
      {error ? <p className="text-[11px] text-rose-300">{error}</p> : null}
    </section>
  );
}
