import { useCallback, useEffect, useMemo, useState, type CSSProperties } from "react";
import { endOfDay, startOfDay } from "date-fns";
import { Check, Loader2, Plus, Trash2 } from "lucide-react";
import {
  deleteDayTask,
  evaluateDayClose,
  setDayTaskDone,
  upsertDayTask,
  type DayLoopSnapshot,
  type DayLoopTask,
} from "../../api/dayLoopClient";
import {
  fetchPlannerBlocks,
  type PlannerBlock,
} from "../../api/plannerClient";
import { isFocusEnforcerBridgeAvailable } from "../../lib/enforcerNativeCmd";
import ActiveWorkSessionEnd from "./ActiveWorkSessionEnd";
import { FocusJarvisPanel } from "./FocusJarvisPanel";
import {
  GOALS_UPDATED_EVENT,
  loadProductivityGoals,
  persistProductivityGoals,
  type ExtraGoal,
} from "./ProductivityGoalsPanel";
import { invalidateFocusStatusBus } from "../../lib/focusStatusBus";
import { useFocusStatus } from "../../hooks/useFocusStatus";
import { isFocusDesktopShell } from "../../utils/focusDesktopShell";
import { cn } from "../../app/components/ui/utils";
import { MORNING_UPDATED_EVENT } from "./ConfirmPlanButton";
import { GlanceBar, RailProgressCell } from "./GlanceBar";
import type { DesktopStats, GoalsStatusResponse } from "../../api/behaviorClient";
import { formatHoursMins } from "../../utils/formatDuration";
import {
  DAY_WRAP_UPDATED_EVENT,
  yesterdayTomorrowFix,
} from "../../lib/dayWrapPrefs";


function pickActiveBlock(blocks: PlannerBlock[], now: Date): PlannerBlock | null {
  const open = blocks.filter(
    (b) => b.status !== "done" && b.status !== "cancelled" && b.status !== "rolled",
  );
  for (const b of open) {
    const start = new Date(b.start_at).getTime();
    const end = new Date(b.end_at).getTime();
    const t = now.getTime();
    if (start <= t && t < end) return b;
  }
  return null;
}

function formatRange(startIso: string, endIso: string): string {
  try {
    const a = new Date(startIso);
    const b = new Date(endIso);
    const opts: Intl.DateTimeFormatOptions = { hour: "numeric", minute: "2-digit" };
    return `${a.toLocaleTimeString([], opts)} – ${b.toLocaleTimeString([], opts)}`;
  } catch {
    return "—";
  }
}

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  } catch {
    return "—";
  }
}

function clamp01(n: number): number {
  return Math.max(0, Math.min(1, n));
}

function WaterFill({
  pct,
  ok,
  variant,
}: {
  pct: number;
  ok: boolean;
  variant: "time" | "tasks";
}) {
  const width = Math.max(0, Math.min(100, pct));
  if (width <= 0) return null;

  const bubbles =
    variant === "time"
      ? [
          { left: "8%", size: 6, dur: "2.8s", delay: "0s" },
          { left: "18%", size: 4, dur: "3.2s", delay: "0.35s" },
          { left: "29%", size: 5.5, dur: "2.5s", delay: "0.8s" },
          { left: "41%", size: 3.5, dur: "3.6s", delay: "0.15s" },
          { left: "52%", size: 7, dur: "2.9s", delay: "1.05s" },
          { left: "63%", size: 4, dur: "3.1s", delay: "0.55s" },
          { left: "74%", size: 5, dur: "2.4s", delay: "1.3s" },
          { left: "84%", size: 3.5, dur: "3.4s", delay: "0.7s" },
          { left: "91%", size: 6, dur: "2.7s", delay: "1.15s" },
        ]
      : [
          { left: "15%", size: 4, dur: "2.6s", delay: "0.2s" },
          { left: "38%", size: 5, dur: "3.1s", delay: "0.65s" },
          { left: "58%", size: 3.5, dur: "2.8s", delay: "1.1s" },
          { left: "78%", size: 4.5, dur: "3.3s", delay: "0.4s" },
        ];

  return (
    <div
      className={cn(
        "day-water",
        variant === "time" ? "day-water--time" : "day-water--tasks",
        ok && "day-water--ok",
      )}
      style={{ width: `${width}%` }}
      aria-hidden
    >
      <div className="day-water__body" />
      <div className="day-water__surface" />
      <div className="day-water__bubbles">
        {bubbles.map((b, i) => (
          <span
            key={i}
            className="day-water__bubble"
            style={
              {
                left: b.left,
                width: b.size,
                height: b.size,
                ["--dur" as string]: b.dur,
                ["--delay" as string]: b.delay,
              } as CSSProperties
            }
          />
        ))}
      </div>
      <div className="day-water__crest" />
    </div>
  );
}

function modeTone(mode: string): { glow: string } {
  const m = mode.toUpperCase();
  if (m === "STUDY") return { glow: "text-sky-100" };
  if (m === "FREE") return { glow: "text-emerald-100" };
  if (m === "BEDTIME") return { glow: "text-violet-100" };
  return { glow: "text-foreground" };
}

function formatLeft(ms: number): string {
  if (ms <= 0) return "0m";
  const total = Math.round(ms / 60_000);
  if (total < 60) return `${total}m left`;
  const h = Math.floor(total / 60);
  const m = total % 60;
  return m ? `${h}h ${m}m left` : `${h}h left`;
}

function blockProgress(b: PlannerBlock, now: number): number {
  const a = new Date(b.start_at).getTime();
  const z = new Date(b.end_at).getTime();
  if (!Number.isFinite(a) || !Number.isFinite(z) || z <= a) return 0;
  if (now >= z || b.status === "done") return 100;
  if (now <= a) return 0;
  return Math.round(clamp01((now - a) / (z - a)) * 100);
}

/** Planned work completed (done / remaining vs planned). */
function blockAdherence(b: PlannerBlock): number {
  if (b.status === "done") return 100;
  const planned = Math.max(0, Number(b.planned_minutes) || 0);
  const rem = Math.max(0, Number(b.remaining_minutes ?? planned));
  if (planned <= 0) return 0;
  return Math.round(clamp01((planned - rem) / planned) * 100);
}

function pickRibbonSlots(
  blocks: PlannerBlock[],
  _activeId: string | number | null | undefined,
  now: number,
): { past: PlannerBlock | null; current: PlannerBlock | null; future: PlannerBlock | null; timeLeft: string } {
  const visible = blocks
    .filter((b) => b.status !== "cancelled" && b.status !== "rolled")
    .slice()
    .sort((a, b) => new Date(a.start_at).getTime() - new Date(b.start_at).getTime());

  if (!visible.length) {
    return { past: null, current: null, future: null, timeLeft: "" };
  }

  // Current is only a block whose window contains now. A later block stays in Next.
  const current =
    visible.find((b) => {
      const a = new Date(b.start_at).getTime();
      const z = new Date(b.end_at).getTime();
      return a <= now && now < z;
    }) ?? null;
  let past: PlannerBlock | null = null;
  for (const b of visible) {
    if (new Date(b.end_at).getTime() <= now) past = b;
  }
  const future =
    visible.find((b) => b !== current && new Date(b.start_at).getTime() > now) ?? null;

  const timeLeft = current
    ? formatLeft(new Date(current.end_at).getTime() - now)
    : "";

  return { past, current, future, timeLeft };
}

/**
 * Local midnight → next midnight.
 * The bar is how far through the day you are. The label is what is still left.
 * Filling only the leftover slice made 2h left look like an empty bar.
 */
function localDayRemaining(now: number): { throughPct: number; label: string } {
  const d = new Date(now);
  const start = new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  const span = 24 * 60 * 60 * 1000;
  const elapsed = Math.max(0, Math.min(span, now - start));
  const left = Math.max(0, span - elapsed);
  return {
    throughPct: Math.round(clamp01(elapsed / span) * 100),
    label: formatLeft(left),
  };
}

function formatUntilClock(iso: string): string {
  const d = new Date(iso);
  if (!Number.isFinite(d.getTime())) return iso;
  return d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

function BlockRailCell({
  role,
  block,
  now,
  timeLeft,
}: {
  role: "past" | "now" | "next";
  block: PlannerBlock | null;
  now: number;
  timeLeft?: string;
}) {
  const isNow = role === "now";
  const isPast = role === "past";
  const workPct = block && isPast ? blockAdherence(block) : 0;
  const hasWorkSignal =
    !!block && isPast && (block.status === "done" || workPct > 0);
  const elapsed = block && isNow ? blockProgress(block, now) : 0;
  // Past: adherence when known; else schedule-through so the cell still reads as a bar.
  const throughPct = block && isPast ? blockProgress(block, now) : 0;
  const pct = isPast ? (hasWorkSignal ? workPct : throughPct) : isNow ? elapsed : 0;

  const label = isPast
    ? hasWorkSignal
      ? "Past · adherence"
      : "Past block"
    : isNow
      ? "Current · time left"
      : "Next block";
  const primary = !block
    ? "—"
    : isPast
      ? hasWorkSignal
        ? `${workPct}%`
        : formatTime(block.start_at)
      : isNow && timeLeft
        ? timeLeft.replace(/\s*left$/i, "")
        : formatTime(block.start_at);
  const sub = block
    ? block.title || "Untitled"
    : isPast
      ? "No earlier"
      : isNow
        ? "None running"
        : "Nothing next";

  const fillClass = isPast
    ? (hasWorkSignal ? workPct : throughPct) >= 100
      ? "bg-emerald-400/20"
      : "bg-sky-400/16"
    : isNow
      ? "bg-teal-400/18"
      : "bg-white/[0.04]";
  const barClass = isPast
    ? (hasWorkSignal ? workPct : throughPct) >= 100
      ? "bg-emerald-400/70"
      : "bg-sky-400/60"
    : isNow
      ? "bg-teal-300/80"
      : "bg-white/20";

  return (
    <RailProgressCell
      pct={pct}
      fillClass={fillClass}
      barClass={barClass}
      title={block ? `${block.title} · ${formatRange(block.start_at, block.end_at)}` : undefined}
      ariaLabel={
        !block
          ? label
          : isPast
            ? hasWorkSignal
              ? `Past block ${block.title}, ${workPct} percent adherence`
              : `Past block ${block.title}`
            : isNow
              ? `Current block ${block.title}, ${timeLeft || "in progress"}`
              : `Next block ${block.title}`
      }
    >
      <div className="flex items-center gap-1.5 min-w-0">
        <span
          className={cn(
            "text-lg font-semibold tabular-nums leading-none truncate",
            !block
              ? "text-muted-foreground/50"
              : isNow
                ? "text-teal-100"
                : isPast && hasWorkSignal
                  ? workPct >= 100
                    ? "text-emerald-200"
                    : "text-sky-100"
                  : "text-foreground/90",
          )}
        >
          {primary}
        </span>
        {isNow && timeLeft && block ? (
          <span className="text-[10px] tabular-nums text-amber-100/80 shrink-0">left</span>
        ) : null}
      </div>
      <p className="mt-1 text-[10px] uppercase tracking-wider text-muted-foreground truncate">{label}</p>
      <p className="mt-0.5 text-[11px] text-muted-foreground/85 truncate">{sub}</p>
    </RailProgressCell>
  );
}

function DayRemainingBar() {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, []);
  const { throughPct, label } = localDayRemaining(now);
  return (
    <div
      className="relative h-12 border-t border-border/40 bg-black/45 overflow-hidden"
      role="img"
      aria-label={`Day ${throughPct} percent through, ${label}`}
    >
      <div className="pointer-events-none absolute inset-0 z-0" aria-hidden>
        {[25, 50, 75].map((mark) => (
          <div
            key={mark}
            className="absolute top-0 bottom-0 w-px bg-white/10"
            style={{ left: `${mark}%` }}
          />
        ))}
      </div>
      <WaterFill pct={throughPct} ok={throughPct >= 50} variant="time" />
      <div className="relative z-[1] flex h-full items-center justify-between gap-3 px-3.5">
        <span className="text-[10px] uppercase tracking-[0.16em] text-white/80 drop-shadow">
          Day · {throughPct}%
        </span>
        <span className="text-sm font-semibold tabular-nums text-white drop-shadow">{label}</span>
      </div>
    </div>
  );
}

/** Glance-style divided rail: past · now · next (one each). */
function DayBlocksRail({
  blocks,
  activeId,
}: {
  blocks: PlannerBlock[];
  activeId?: string | number | null;
}) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 15_000);
    return () => window.clearInterval(id);
  }, []);

  const { past, current, future, timeLeft } = pickRibbonSlots(blocks, activeId, now);

  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-px bg-white/[0.06] border-t border-white/10">
      <BlockRailCell role="past" block={past} now={now} />
      <BlockRailCell role="now" block={current} now={now} timeLeft={timeLeft} />
      <BlockRailCell role="next" block={future} now={now} />
    </div>
  );
}

type Props = {
  day: Date;
  refreshKey?: number;
  desktop: DesktopStats | null;
  rangeLabel?: string;
  sleepHours?: number | null;
  sleepScore?: number | null;
  goalsStatus?: GoalsStatusResponse | null;
};

/**
 * Home: SoftLand mode + glance + past/now/next blocks + tasks.
 */
export default function HomeModeBoard({
  day,
  refreshKey = 0,
  desktop,
  rangeLabel = "today",
  sleepHours = null,
  sleepScore = null,
  goalsStatus = null,
}: Props) {
  const focus = isFocusDesktopShell();
  const status = useFocusStatus();
  const [loop, setLoop] = useState<DayLoopSnapshot | null>(null);
  const [modeLabel, setModeLabel] = useState("—");
  const [active, setActive] = useState<PlannerBlock | null>(null);
  const [dayBlocks, setDayBlocks] = useState<PlannerBlock[]>([]);
  const [loading, setLoading] = useState(false);
  const [hint, setHint] = useState<string | null>(null);
  const [newTitle, setNewTitle] = useState("");
  const [extraGoals, setExtraGoals] = useState<ExtraGoal[]>(
    () => loadProductivityGoals().extraGoals,
  );
  const [previewTasks, setPreviewTasks] = useState<
    { id: number; title: string; done: boolean }[]
  >(() => {
    try {
      const raw = localStorage.getItem("calt-home-preview-tasks");
      if (raw) {
        const parsed = JSON.parse(raw) as { id: number; title: string; done: boolean }[];
        if (Array.isArray(parsed) && parsed.length) return parsed;
      }
    } catch {
      /* ignore */
    }
    return [
      { id: 1, title: "Deep work block", done: false },
      { id: 2, title: "Plan check-in", done: false },
      { id: 3, title: "Evening wrap-up", done: false },
    ];
  });
  // SoftLand + day-loop from shared bus (no per-panel pipe poll).
  useEffect(() => {
    if (!focus) return;
    if (status.dayLoop) setLoop(status.dayLoop);
    const j = status.softland;
    if (!j) return;
    if (j.runtime?.bedtime_active) setModeLabel("BEDTIME");
    else if (j.runtime?.free_until) setModeLabel("FREE");
    else if (j.softland_enabled) setModeLabel("STUDY");
    else setModeLabel("OFF");
  }, [focus, status.updatedAt, status.dayLoop, status.softland]);

  const refreshPlan = useCallback(async () => {
    if (!focus) return;
    setLoading(true);
    try {
      const blocks = await fetchPlannerBlocks(startOfDay(day), endOfDay(day)).catch(
        () => [] as PlannerBlock[],
      );
      const list = Array.isArray(blocks) ? blocks : [];
      setDayBlocks(list);
      setActive(pickActiveBlock(list, new Date()));
    } finally {
      setLoading(false);
    }
  }, [day, focus]);

  useEffect(() => {
    void refreshPlan();
    const t = window.setInterval(() => void refreshPlan(), 45_000);
    const onMorning = () => {
      invalidateFocusStatusBus({ pipe: true });
      void refreshPlan();
    };
    window.addEventListener(MORNING_UPDATED_EVENT, onMorning);
    return () => {
      window.clearInterval(t);
      window.removeEventListener(MORNING_UPDATED_EVENT, onMorning);
    };
  }, [refreshPlan, refreshKey]);

  useEffect(() => {
    const sync = () => setExtraGoals(loadProductivityGoals().extraGoals);
    sync();
    window.addEventListener(GOALS_UPDATED_EVENT, sync);
    return () => window.removeEventListener(GOALS_UPDATED_EVENT, sync);
  }, []);

  const [morningFix, setMorningFix] = useState(() => yesterdayTomorrowFix());
  useEffect(() => {
    const sync = () => setMorningFix(yesterdayTomorrowFix());
    sync();
    window.addEventListener(DAY_WRAP_UPDATED_EVENT, sync as EventListener);
    return () => window.removeEventListener(DAY_WRAP_UPDATED_EVENT, sync as EventListener);
  }, [refreshKey]);

  const persistPreviewTasks = (next: { id: number; title: string; done: boolean }[]) => {
    setPreviewTasks(next);
    try {
      localStorage.setItem("calt-home-preview-tasks", JSON.stringify(next));
    } catch {
      /* ignore */
    }
  };

  const goalName = useMemo(() => {
    if (active?.title) return active.title;
    const openTask = (loop?.tasks || []).find((t) => !t.done);
    if (openTask) return openTask.title;
    return "No goal block running";
  }, [active, loop?.tasks]);

  async function toggleTask(t: DayLoopTask) {
    await setDayTaskDone(t.id, !t.done);
    invalidateFocusStatusBus({ pipe: true });
    await evaluateDayClose();
    invalidateFocusStatusBus({ pipe: true });
  }

  async function removeTask(id: number) {
    await deleteDayTask(id);
    invalidateFocusStatusBus({ pipe: true });
  }

  function toggleExtraGoal(id: string) {
    const next = loadProductivityGoals();
    next.extraGoals = next.extraGoals.map((g) =>
      g.id === id ? { ...g, done: !g.done } : g,
    );
    persistProductivityGoals(next);
    setExtraGoals(next.extraGoals);
  }

  function removeExtraGoal(id: string) {
    const next = loadProductivityGoals();
    next.extraGoals = next.extraGoals.filter((g) => g.id !== id);
    persistProductivityGoals(next);
    setExtraGoals(next.extraGoals);
  }

  if (!focus) return null;

  const tasks = loop?.tasks || [];
  const tone = modeTone(modeLabel);
  // Prefer the best available source. `??` alone is wrong: a stale loop with
  // tracked_productive_minutes: 0 would hide a live day_rollup of 15+.
  const trackedCandidates: number[] = [];
  if (typeof loop?.tracked_productive_minutes === "number" && Number.isFinite(loop.tracked_productive_minutes)) {
    trackedCandidates.push(Math.max(0, Math.floor(loop.tracked_productive_minutes)));
  }
  if (typeof status.dayRollup?.productive_minutes === "number" && Number.isFinite(status.dayRollup.productive_minutes)) {
    trackedCandidates.push(Math.max(0, Math.floor(status.dayRollup.productive_minutes)));
  } else if (
    typeof status.dayRollup?.productive_seconds === "number" &&
    Number.isFinite(status.dayRollup.productive_seconds)
  ) {
    trackedCandidates.push(Math.max(0, Math.floor(status.dayRollup.productive_seconds / 60)));
  }
  if (desktop && Number.isFinite(desktop.productive_seconds)) {
    trackedCandidates.push(Math.max(0, Math.round(desktop.productive_seconds / 60)));
  }
  const trackedMin = trackedCandidates.length ? Math.max(...trackedCandidates) : null;
  const trackedLabel =
    trackedMin != null && Number.isFinite(trackedMin) ? formatHoursMins(trackedMin) : "—";
  const modeDetail = active
    ? `${goalName} · ${formatRange(active.start_at, active.end_at)}${
        active.category ? ` · ${active.category}` : ""
      }`
    : goalName;

  const previewing = !loop && !isFocusEnforcerBridgeAvailable();
  const checklist = previewing ? previewTasks : tasks;

  async function onChecklistToggle(id: number, done: boolean) {
    if (previewing) {
      persistPreviewTasks(
        previewTasks.map((t) => (t.id === id ? { ...t, done: !done } : t)),
      );
      return;
    }
    const t = tasks.find((x) => x.id === id);
    if (t) await toggleTask(t);
  }

  async function addTask() {
    const title = newTitle.trim();
    if (!title) return;
    if (previewing || !isFocusEnforcerBridgeAvailable()) {
      const id = Date.now();
      persistPreviewTasks([...previewTasks, { id, title, done: false }]);
      setNewTitle("");
      return;
    }
    await upsertDayTask({ title, done: false });
    setNewTitle("");
    invalidateFocusStatusBus({ pipe: true });
  }

  const openExtras = extraGoals.filter((g) => g.title.trim());
  const cardTotal = checklist.length + openExtras.length;
  const cardDone =
    checklist.filter((t) => t.done).length + openExtras.filter((g) => g.done).length;
  const cardPct = cardTotal ? Math.round((cardDone / cardTotal) * 100) : 0;
  const softlandGoalMin = Number(
    (status.softland?.goals as { daily_focus_minutes?: number } | undefined)?.daily_focus_minutes,
  );
  const dailyFocusMin =
    (typeof status.dayRollup?.daily_focus_minutes === "number" &&
    status.dayRollup.daily_focus_minutes > 0
      ? status.dayRollup.daily_focus_minutes
      : Number.isFinite(softlandGoalMin) && softlandGoalMin > 0
        ? softlandGoalMin
        : 0) || 0;
  const trackedForGoal = trackedMin ?? 0;

  return (
    <div className="space-y-5">
      {morningFix ? (
        <div className="rounded-xl border border-amber-500/25 bg-amber-500/[0.07] px-4 py-2.5">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-amber-200/90">
            Yesterday’s one fix
          </p>
          <p className="mt-0.5 text-[13px] text-foreground/90 leading-snug">{morningFix.fix}</p>
        </div>
      ) : null}
      {/* Mode card first: SoftLand mode + glance + blocks + tasks */}
      <section className="focus-panel focus-panel--hero">
        <div className="flex items-start justify-between gap-4 px-5 pt-5 pb-4">
          <div className="min-w-0">
            <p className="focus-kicker mb-2">Today</p>
            <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
              <h2 className={cn("focus-mode-title", tone.glow)}>
                {modeLabel}
              </h2>
              {loop?.free_until ? (
                <span className="text-sm text-[color:var(--focus-teal-bright,#8fd6cc)]">
                  until {formatUntilClock(loop.free_until)}
                </span>
              ) : status.dayRollup?.goal_met ? (
                <span className="text-sm text-[color:var(--focus-teal-bright,#8fd6cc)]">goal met</span>
              ) : null}
              {loading ? <Loader2 className="size-3.5 animate-spin text-muted-foreground" /> : null}
            </div>
            <p className="mt-2 text-[15px] text-foreground/85 truncate" title={modeDetail}>
              {modeDetail}
            </p>
            <p className="mt-1 text-[12px] text-muted-foreground">
              {loop?.plan_confirmed ? "Plan locked" : "Plan open"}
              {dailyFocusMin > 0 ? ` · goal ${dailyFocusMin}m` : ""}
            </p>
            {!loop?.free_until &&
            !status.dayRollup?.goal_met &&
            dailyFocusMin > 0 &&
            trackedForGoal < dailyFocusMin ? (
              <p className="mt-1 text-[11px] text-muted-foreground/90">
                Goal free at {dailyFocusMin}m tracked · now {trackedForGoal}m
              </p>
            ) : null}
            {hint ? (
              <p className="mt-1.5 text-[11px] text-amber-100/90">{hint}</p>
            ) : null}
          </div>
          <div className="shrink-0 text-right pt-1">
            <p className="focus-kicker">
              Tracked · {rangeLabel}
            </p>
            <p className="mt-1.5 text-2xl font-semibold tabular-nums tracking-tight text-foreground leading-none">
              {trackedLabel}
            </p>
          </div>
        </div>

        <DayBlocksRail blocks={dayBlocks} activeId={active?.id} />

        <GlanceBar
          variant="rail"
          hideTracked
          desktop={desktop}
          rangeLabel={rangeLabel}
          sleepHours={sleepHours}
          sleepScore={sleepScore}
          goalsStatus={goalsStatus}
        />

        <DayRemainingBar />

        <div className="relative overflow-hidden border-t border-border/30">
          <div className="pointer-events-none absolute inset-0 bg-black/20" aria-hidden />
          <div
            className="pointer-events-none absolute inset-y-0 left-0 bg-gradient-to-r from-emerald-500/55 via-emerald-400/40 to-emerald-300/25 shadow-[inset_-3px_0_0_0_rgba(167,243,208,0.9)] transition-[width] duration-500"
            style={{ width: `${cardPct}%` }}
            role="progressbar"
            aria-valuenow={cardPct}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label={`Goals ${cardDone} of ${cardTotal}`}
          />
          <div className="relative z-[1] px-3 py-2.5">
          {isFocusEnforcerBridgeAvailable() ? (
            <div className="flex justify-end mb-1.5">
              <button
                type="button"
                className="rounded-md border border-amber-400/30 bg-amber-500/15 px-2 py-0.5 text-[10px] text-amber-50 hover:bg-amber-500/25"
                onClick={() =>
                    void evaluateDayClose().then((r) => {
                    setHint(
                      r.granted
                        ? `1h free until ${r.free_until || "soon"}`
                        : r.reason === "daily_goal_pending"
                          ? "Plan dual-gate OK, but daily focus goal still open — YouTube stays locked."
                          : "Dual gate not met yet (checkboxes + ≥50% planned time).",
                    );
                    invalidateFocusStatusBus({ pipe: true });
                  })
                }
              >
                Check unlock
              </button>
            </div>
          ) : null}

          <div className="mb-1.5 flex items-center justify-between gap-2">
            <p className="text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
              Goals · todos
            </p>
            <span className="text-[10px] tabular-nums text-muted-foreground">
              {cardDone}/{cardTotal}
              {cardTotal ? ` · ${cardPct}%` : ""}
            </span>
          </div>

          <ul className="divide-y divide-white/10 rounded-lg border border-white/10 overflow-hidden">
            {checklist.map((t) => (
              <li key={t.id} className="flex items-center gap-2 px-2.5 py-1.5">
                <button
                  type="button"
                  className={cn(
                    "size-4 rounded-[3px] border flex items-center justify-center shrink-0 transition-colors",
                    t.done
                      ? "border-emerald-400/40 bg-emerald-500/15"
                      : "border-border/60 hover:border-foreground/40",
                  )}
                  onClick={() => void onChecklistToggle(t.id, t.done)}
                  aria-label={t.done ? "Mark incomplete" : "Mark done"}
                >
                  {t.done ? <Check className="size-2.5 text-emerald-300" /> : null}
                </button>
                <span
                  className={`flex-1 text-[13px] leading-snug ${t.done ? "line-through text-muted-foreground" : "text-foreground/90"}`}
                >
                  {t.title}
                </span>
                {!previewing && isFocusEnforcerBridgeAvailable() ? (
                  <button
                    type="button"
                    className="text-muted-foreground hover:text-rose-300"
                    onClick={() => void removeTask(t.id)}
                    aria-label="Delete task"
                  >
                    <Trash2 className="size-3" />
                  </button>
                ) : null}
              </li>
            ))}
            {openExtras.map((g) => (
              <li key={g.id} className="flex items-center gap-2 px-2.5 py-1.5">
                <button
                  type="button"
                  className={cn(
                    "size-4 rounded-[3px] border flex items-center justify-center shrink-0 transition-colors",
                    g.done
                      ? "border-sky-400/40 bg-sky-500/15"
                      : "border-border/60 hover:border-foreground/40",
                  )}
                  onClick={() => toggleExtraGoal(g.id)}
                  aria-label={g.done ? "Mark incomplete" : "Mark done"}
                >
                  {g.done ? <Check className="size-2.5 text-sky-300" /> : null}
                </button>
                <span
                  className={`flex-1 text-[13px] leading-snug ${g.done ? "line-through text-muted-foreground" : "text-foreground/90"}`}
                >
                  {g.title}
                </span>
                <span className="text-[9px] uppercase tracking-wider text-sky-200/50 shrink-0">
                  side
                </span>
                <button
                  type="button"
                  className="text-muted-foreground hover:text-rose-300 shrink-0"
                  onClick={() => removeExtraGoal(g.id)}
                  aria-label="Remove side todo"
                >
                  <Trash2 className="size-3" />
                </button>
              </li>
            ))}
            {!checklist.length && !openExtras.length ? (
              <li className="px-2.5 py-2 text-[11px] text-muted-foreground">
                No todos yet — add a day-loop task or Plan → Goals side todos.
              </li>
            ) : null}
          </ul>

          <div className="mt-2 flex gap-2">
            <input
              className="flex-1 rounded-lg border border-border/40 bg-black/30 px-2.5 py-1.5 text-[13px]"
              placeholder="Add goal todo…"
              value={newTitle}
              onChange={(e) => setNewTitle(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") void addTask();
              }}
            />
            <button
              type="button"
              className="inline-flex items-center gap-1 rounded-lg border border-border/40 bg-white/5 px-2.5 py-1.5 text-[11px] hover:bg-white/10"
              onClick={() => void addTask()}
              title="Add day-loop task (dual-gate checklist)"
            >
              <Plus className="size-3.5" /> Add
            </button>
          </div>
          </div>
        </div>
      </section>

      <FocusJarvisPanel variant="home" />

      {/* Plan-first: no short/dynamic session create — end leftover only */}
      <ActiveWorkSessionEnd />
    </div>
  );
}
