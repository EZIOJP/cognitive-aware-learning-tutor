import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { CalendarDays, GripVertical, Layers, Loader2, Pencil, Plus, Trash2 } from "lucide-react";
import { blockColor, type ProposedPlannerBlock } from "../../api/plannerClient";
import {
  proposedBlocksEqualTimes,
  resolveProposedOverlaps,
} from "./resolveProposedOverlaps";

export type ApplyPlanRange = {
  from: string; // YYYY-MM-DD local (min when days omitted)
  to: string;
  label: string;
  /** Non-contiguous day keys — when set, apply only these days */
  days?: string[];
};

type Props = {
  blocks: ProposedPlannerBlock[];
  rationale?: string | null;
  usedLlm?: boolean;
  proposing?: boolean;
  /** Step-1 planning prompt — used to compare goal hours vs planned */
  goalsText?: string;
  /** Backend may soften daily target after weak on-plan adherence */
  scaledDailyHours?: number | null;
  /** Hide day-strip; calendar lives beside this panel on Plan tab */
  embedded?: boolean;
  onChange: (blocks: ProposedPlannerBlock[]) => void;
  onApply: (range: ApplyPlanRange) => void;
  onDismiss: () => void;
};

const DAY_MIN = 5 * 60;
const DAY_MAX = 23 * 60;
/** Vertical scale — height always matches real duration (no min-height inflate) */
const PX_PER_MIN = 2;
const SNAP = 15;

function todayKeyLocal(): string {
  const t = new Date();
  const y = t.getFullYear();
  const m = String(t.getMonth() + 1).padStart(2, "0");
  const d = String(t.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

function dayKey(iso: string): string {
  const d = new Date(iso);
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function parseDay(key: string): Date {
  const [y, m, d] = key.split("-").map(Number);
  return new Date(y, m - 1, d);
}

function minutesSinceMidnight(d: Date): number {
  return d.getHours() * 60 + d.getMinutes();
}

function toLocalInput(iso: string): string {
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function fromLocalInput(local: string, durationMin: number): { start_at: string; end_at: string } {
  const start = new Date(local);
  const end = new Date(start.getTime() + Math.max(15, durationMin) * 60_000);
  return { start_at: start.toISOString(), end_at: end.toISOString() };
}

function formatHour(h: number): string {
  if (h === 0 || h === 24) return "12a";
  if (h === 12) return "12p";
  if (h < 12) return `${h}a`;
  return `${h - 12}p`;
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
}

function snapMin(m: number): number {
  return Math.round(m / SNAP) * SNAP;
}

function durationOf(b: ProposedPlannerBlock): number {
  return Math.max(
    15,
    Math.round((new Date(b.end_at).getTime() - new Date(b.start_at).getTime()) / 60_000),
  );
}

function setStartMinutes(
  day: string,
  startM: number,
  durationMin: number,
  axisStart: number,
  axisEnd: number,
): { start_at: string; end_at: string } {
  const base = parseDay(day);
  const clamped = Math.max(axisStart, Math.min(axisEnd - durationMin, snapMin(startM)));
  base.setHours(0, 0, 0, 0);
  base.setMinutes(clamped);
  const end = new Date(base.getTime() + durationMin * 60_000);
  return { start_at: base.toISOString(), end_at: end.toISOString() };
}

const CATEGORIES = [
  "Coding Practice",
  "AI / ML",
  "Study / Reading",
  "Coursework (Browser)",
  "personal",
  "break",
];

function parseGoalHours(text?: string): { daily: number; weekly: number | null } {
  const dailyM = text?.match(/Daily effective-focus target:\s*([\d.]+)\s*h/i);
  const weeklyM = text?.match(/Weekly target:\s*([\d.]+)\s*h/i);
  return {
    daily: dailyM ? Math.max(0.5, Number(dailyM[1]) || 3) : 3,
    weekly: weeklyM ? Math.max(1, Number(weeklyM[1]) || 0) : null,
  };
}

function blockMinutes(b: ProposedPlannerBlock): number {
  return Math.max(
    0,
    Math.round((new Date(b.end_at).getTime() - new Date(b.start_at).getTime()) / 60_000),
  );
}

function assignOverlapLanes(
  items: { index: number; start: number; end: number }[],
): Map<number, { lane: number; laneCount: number }> {
  const sorted = [...items].sort((a, b) => a.start - b.start || b.end - a.end);
  const laneEnds: number[] = [];
  const assigned = new Map<number, number>();
  for (const it of sorted) {
    let lane = laneEnds.findIndex((end) => end <= it.start);
    if (lane < 0) {
      lane = laneEnds.length;
      laneEnds.push(it.end);
    } else {
      laneEnds[lane] = it.end;
    }
    assigned.set(it.index, lane);
  }
  // Per overlapping cluster, compute laneCount
  const result = new Map<number, { lane: number; laneCount: number }>();
  for (const it of items) {
    const lane = assigned.get(it.index) ?? 0;
    let maxLane = lane;
    for (const other of items) {
      if (other.index === it.index) continue;
      if (it.start < other.end && other.start < it.end) {
        maxLane = Math.max(maxLane, assigned.get(other.index) ?? 0);
      }
    }
    result.set(it.index, { lane, laneCount: maxLane + 1 });
  }
  return result;
}

function sourceBadge(source?: string): { label: string; className: string } {
  if (source === "routine")
    return { label: "Routine", className: "bg-amber-500/20 text-amber-200 border-amber-500/30" };
  if (source === "existing")
    return { label: "Calendar", className: "bg-sky-500/20 text-sky-200 border-sky-500/30" };
  if (source === "break")
    return { label: "Break", className: "bg-violet-500/20 text-violet-200 border-violet-500/30" };
  return { label: "Study", className: "bg-emerald-500/20 text-emerald-200 border-emerald-500/30" };
}

export function ProposePlanPreview({
  blocks,
  rationale,
  usedLlm,
  proposing,
  goalsText,
  scaledDailyHours,
  embedded = false,
  onChange,
  onApply,
  onDismiss,
}: Props) {
  const todayKey = todayKeyLocal();
  const days = useMemo(() => {
    const keys = [...new Set(blocks.map((b) => dayKey(b.start_at)))]
      .filter((k) => k >= todayKey)
      .sort();
    return keys.length ? keys : [todayKey];
  }, [blocks, todayKey]);

  const [activeDay, setActiveDay] = useState(() => todayKeyLocal());
  const [selectedIdx, setSelectedIdx] = useState<number | null>(null);
  /** Crosshair + click-to-place only while this is true (Add block). */
  const [placing, setPlacing] = useState(false);

  // Drop past-day blocks from an older proposal still in memory.
  useEffect(() => {
    const kept = blocks.filter((b) => dayKey(b.start_at) >= todayKey);
    const resolved = resolveProposedOverlaps(kept);
    if (!proposedBlocksEqualTimes(resolved, blocks)) onChange(resolved);
  }, [blocks, todayKey, onChange]);
  /** Live drag target minutes — applied via CSS transform; committed on pointerup */
  const dragPreviewRef = useRef<{ index: number; startM: number } | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const gridRef = useRef<HTMLDivElement>(null);
  const blockEls = useRef<Map<number, HTMLDivElement>>(new Map());
  const dragRef = useRef<{
    index: number;
    originY: number;
    originStartM: number;
    duration: number;
    pointerId: number;
    moved: boolean;
  } | null>(null);
  const suppressClickRef = useRef(false);
  const blocksRef = useRef(blocks);
  blocksRef.current = blocks;
  const axisRef = useRef({ axisStart: 8 * 60, axisEnd: 20 * 60, day: "" });
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;

  const day = days.includes(activeDay) ? activeDay : days[0];

  const dayBlocks = useMemo(() => {
    return blocks
      .map((b, index) => ({ b, index }))
      .filter(({ b }) => dayKey(b.start_at) === day)
      .sort((a, c) => new Date(a.b.start_at).getTime() - new Date(c.b.start_at).getTime());
  }, [blocks, day]);

  const laneMap = useMemo(() => {
    return assignOverlapLanes(
      dayBlocks.map(({ b, index }) => ({
        index,
        start: minutesSinceMidnight(new Date(b.start_at)),
        end: Math.max(
          minutesSinceMidnight(new Date(b.start_at)) + 15,
          minutesSinceMidnight(new Date(b.end_at)),
        ),
      })),
    );
  }, [dayBlocks]);

  // Fit the visible window around today's blocks so nothing is "below the fold" empty morning
  const { axisStart, axisEnd } = useMemo(() => {
    if (!dayBlocks.length) {
      return { axisStart: 8 * 60, axisEnd: 20 * 60 };
    }
    let minM = Infinity;
    let maxM = -Infinity;
    for (const { b } of dayBlocks) {
      minM = Math.min(minM, minutesSinceMidnight(new Date(b.start_at)));
      maxM = Math.max(maxM, minutesSinceMidnight(new Date(b.end_at)));
    }
    const pad = 60;
    let start = Math.floor((minM - pad) / 60) * 60;
    let end = Math.ceil((maxM + pad) / 60) * 60;
    start = Math.max(DAY_MIN, start);
    end = Math.min(DAY_MAX, Math.max(start + 3 * 60, end));
    // Keep at least 4 hours visible for drag room
    if (end - start < 4 * 60) {
      end = Math.min(DAY_MAX, start + 4 * 60);
    }
    return { axisStart: start, axisEnd: end };
  }, [dayBlocks]);

  axisRef.current = { axisStart, axisEnd, day };

  const goalHours = useMemo(() => parseGoalHours(goalsText), [goalsText]);
  const dailyTargetH =
    scaledDailyHours != null && scaledDailyHours > 0 ? scaledDailyHours : goalHours.daily;

  /** Per calendar day: scheduled study vs (possibly scaled) daily target — plan filled, not focus met. */
  const perDayPlan = useMemo(() => {
    const dailyMin = dailyTargetH * 60;
    const map = new Map<
      string,
      { plannedMin: number; goalMin: number; unplannedMin: number; status: "met" | "short" | "empty" }
    >();
    for (const d of days) {
      map.set(d, { plannedMin: 0, goalMin: dailyMin, unplannedMin: dailyMin, status: "empty" });
    }
    for (const b of blocks) {
      if (b.source === "routine" || b.source === "existing" || b.source === "break") continue;
      const k = dayKey(b.start_at);
      const row = map.get(k) ?? {
        plannedMin: 0,
        goalMin: dailyMin,
        unplannedMin: dailyMin,
        status: "empty" as const,
      };
      row.plannedMin += blockMinutes(b);
      map.set(k, row);
    }
    for (const [k, row] of map) {
      row.unplannedMin = Math.max(0, row.goalMin - row.plannedMin);
      if (row.plannedMin <= 0) row.status = "empty";
      else if (row.plannedMin + 9 >= row.goalMin) row.status = "met";
      else row.status = "short";
      map.set(k, row);
    }
    return map;
  }, [blocks, days, dailyTargetH]);

  const hoursSummary = useMemo(() => {
    const studyAll = blocks.filter((b) => b.source === "study" || !b.source);
    const plannedMin = studyAll.reduce((a, b) => a + blockMinutes(b), 0);
    const dayRow = perDayPlan.get(day);
    const dayStudy = dayRow?.plannedMin ?? 0;
    const dayGoal = dayRow?.goalMin ?? dailyTargetH * 60;
    const unplanned = dayRow?.unplannedMin ?? Math.max(0, dayGoal - dayStudy);
    return {
      plannedH: plannedMin / 60,
      dayH: dayStudy / 60,
      dayGoalH: dayGoal / 60,
      unplannedH: unplanned / 60,
      dayStatus: dayRow?.status ?? "empty",
      weekGoalH: goalHours.weekly,
    };
  }, [blocks, day, goalHours.weekly, dailyTargetH, perDayPlan]);

  const counts = useMemo(() => {
    const routine = blocks.filter((b) => b.source === "routine").length;
    const existing = blocks.filter((b) => b.source === "existing").length;
    const brk = blocks.filter((b) => b.source === "break").length;
    const study = blocks.length - routine - existing - brk;
    return { routine, existing, study, brk };
  }, [blocks]);

  const timelineH = Math.max(220, (axisEnd - axisStart) * PX_PER_MIN);
  const hours = useMemo(() => {
    const out: number[] = [];
    for (let h = Math.floor(axisStart / 60); h <= Math.ceil(axisEnd / 60); h++) out.push(h);
    return out;
  }, [axisStart, axisEnd]);

  const selected = selectedIdx != null ? blocks[selectedIdx] : null;
  const selectedDuration = selected ? durationOf(selected) : 60;
  const selectedFromCalendar = selected?.source === "existing";

  // Select first block of day when day changes
  useEffect(() => {
    if (!dayBlocks.length) {
      setSelectedIdx(null);
      return;
    }
    setSelectedIdx((prev) => {
      if (prev != null && dayBlocks.some((d) => d.index === prev)) return prev;
      return dayBlocks[0].index;
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps -- only re-pick when day changes
  }, [day]);

  // Scroll selected into view when day/selection changes — not while dragging
  useLayoutEffect(() => {
    if (dragRef.current) return;
    const idx = selectedIdx ?? dayBlocks[0]?.index;
    if (idx == null) return;
    const el = blockEls.current.get(idx);
    el?.scrollIntoView({ block: "nearest", behavior: "auto" });
  }, [day, selectedIdx]);

  /** Turn calendar busy into an editable proposal block so Apply includes it. */
  const promoteExisting = (index: number, list: ProposedPlannerBlock[]) => {
    const b = list[index];
    if (!b || b.source !== "existing") return list;
    return list.map((row, i) =>
      i === index ? { ...row, source: "study" as const, existing_id: undefined } : row,
    );
  };

  const updateAt = (index: number, patch: Partial<ProposedPlannerBlock>) => {
    let next = blocks.map((b, i) => (i === index ? { ...b, ...patch } : b));
    if (blocks[index]?.source === "existing") next = promoteExisting(index, next);
    onChange(next);
  };

  const removeAt = (index: number) => {
    onChange(blocks.filter((_, i) => i !== index));
    setSelectedIdx(null);
  };

  const replaceSelected = () => {
    if (selectedIdx == null) return;
    updateAt(selectedIdx, {
      title: "New study block",
      category: "Study / Reading",
      source: "study",
    });
  };

  const addBlockAt = (startM: number) => {
    const span = setStartMinutes(day, startM, 60, axisStart, axisEnd);
    const next: ProposedPlannerBlock = {
      title: "New study block",
      category: "Study / Reading",
      ...span,
      source: "study",
    };
    const nextBlocks = [...blocks, next];
    onChange(nextBlocks);
    setSelectedIdx(nextBlocks.length - 1);
    setPlacing(false);
  };

  /** Enter place mode — click empty strip time to drop a block. */
  const beginPlaceMode = () => {
    setPlacing(true);
    setSelectedIdx(null);
  };

  const cancelPlaceMode = () => setPlacing(false);

  useEffect(() => {
    if (!placing) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setPlacing(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [placing]);

  const onPointerDownBlock = (e: React.PointerEvent, index: number) => {
    if (placing) {
      // Don't drag while placing — exit place mode and select instead
      setPlacing(false);
      setSelectedIdx(index);
      return;
    }
    if (e.button !== 0) return;
    e.preventDefault();
    e.stopPropagation();
    const target = e.currentTarget as HTMLElement;
    try {
      target.setPointerCapture(e.pointerId);
    } catch {
      /* ignore */
    }
    dragRef.current = {
      index,
      originY: e.clientY,
      originStartM: minutesSinceMidnight(new Date(blocks[index].start_at)),
      duration: durationOf(blocks[index]),
      pointerId: e.pointerId,
      moved: false,
    };
    setSelectedIdx(index);
    dragPreviewRef.current = {
      index,
      startM: minutesSinceMidnight(new Date(blocks[index].start_at)),
    };
    target.style.willChange = "transform";
    target.style.zIndex = "40";
  };

  const onPointerMoveBlock = (e: React.PointerEvent) => {
    const drag = dragRef.current;
    if (!drag || drag.pointerId !== e.pointerId) return;
    const { axisStart: a0, axisEnd: a1 } = axisRef.current;
    const dy = e.clientY - drag.originY;
    if (!drag.moved && Math.abs(dy) < 4) return;
    drag.moved = true;
    suppressClickRef.current = true;
    const nextStart = snapMin(drag.originStartM + dy / PX_PER_MIN);
    const clamped = Math.max(a0, Math.min(a1 - drag.duration, nextStart));
    const prev = dragPreviewRef.current;
    if (prev && prev.index === drag.index && prev.startM === clamped) return;
    dragPreviewRef.current = { index: drag.index, startM: clamped };
    const el = blockEls.current.get(drag.index);
    if (el) {
      const offsetPx = (clamped - drag.originStartM) * PX_PER_MIN;
      el.style.transform = `translate3d(0, ${offsetPx}px, 0)`;
    }
  };

  const onPointerUpBlock = (e: React.PointerEvent) => {
    const drag = dragRef.current;
    const el = drag ? blockEls.current.get(drag.index) : null;
    if (el) {
      el.style.transform = "";
      el.style.willChange = "";
      el.style.zIndex = "";
    }
    try {
      (e.currentTarget as HTMLElement).releasePointerCapture(e.pointerId);
    } catch {
      /* already released */
    }
    if (!drag || drag.pointerId !== e.pointerId) {
      dragPreviewRef.current = null;
      dragRef.current = null;
      return;
    }
    const moved = drag.moved;
    const { axisStart: a0, axisEnd: a1, day: d } = axisRef.current;
    const preview = dragPreviewRef.current;
    const startM = preview?.index === drag.index ? preview.startM : drag.originStartM;
    const idx = drag.index;
    dragRef.current = null;
    dragPreviewRef.current = null;
    if (!moved || startM === drag.originStartM) {
      window.setTimeout(() => {
        suppressClickRef.current = false;
      }, 0);
      return;
    }
    const span = setStartMinutes(d, startM, drag.duration, a0, a1);
    let cur = blocksRef.current;
    cur = promoteExisting(idx, cur);
    onChangeRef.current(cur.map((b, i) => (i === idx ? { ...b, ...span } : b)));
    window.setTimeout(() => {
      suppressClickRef.current = false;
    }, 0);
  };

  const onGridClick = (e: React.MouseEvent) => {
    if (!placing || !gridRef.current || dragRef.current) return;
    // Ignore clicks that bubbled from a block
    if ((e.target as HTMLElement).closest("[data-plan-block]")) return;
    const rect = gridRef.current.getBoundingClientRect();
    const y = e.clientY - rect.top + (scrollRef.current?.scrollTop ?? 0) - 12;
    const startM = snapMin(axisStart + Math.max(0, y) / PX_PER_MIN);
    addBlockAt(startM);
  };

  const dayLabel = parseDay(day).toLocaleDateString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
  });

  const applyable = blocks.filter((b) => b.source !== "existing").length;
  const rangeLabel = `${formatHour(Math.floor(axisStart / 60))}–${formatHour(Math.ceil(axisEnd / 60))}`;
  const todayK = todayKeyLocal();
  const draftDayKeys = useMemo(
    () =>
      [
        ...new Set(
          blocks
            .filter((b) => b.source !== "existing")
            .map((b) => dayKey(b.start_at))
            .filter((k) => k >= todayK),
        ),
      ].sort(),
    [blocks, todayK],
  );

  const fixOverlaps = () => {
    const next = resolveProposedOverlaps(blocks);
    onChange(next);
  };

  const applyAllDrafts = () => {
    if (!draftDayKeys.length) return;
    onApply({
      from: draftDayKeys[0],
      to: draftDayKeys[draftDayKeys.length - 1],
      days: draftDayKeys,
      label:
        draftDayKeys.length === 1
          ? draftDayKeys[0]
          : `${draftDayKeys.length} days (build horizon)`,
    });
  };

  const applyTodayOnly = () => {
    onApply({
      from: todayK,
      to: todayK,
      days: [todayK],
      label: "Today",
    });
  };

  return (
    <div className="bg-white/[0.03] border border-primary/25 rounded-2xl p-5 sm:p-6 space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="font-semibold text-sm flex items-center gap-2">
            <CalendarDays size={16} className="text-primary" />
            {embedded ? "Ready to apply" : "Review & edit plan"}
          </h3>
          <p className="mt-1 text-xs text-muted-foreground leading-relaxed">
            {embedded
              ? "Check the calendar on the right · Apply saves drafts to your planner."
              : "Drag blocks to reschedule · use Add block then click empty time to place · today onward only."}
            {rationale ? (
              <>
                {" "}
                · {usedLlm ? "AI" : "Smart rules"} · {rationale}
              </>
            ) : null}
          </p>
          <div className="mt-2 flex flex-wrap gap-1.5 text-[10px]">
            <span
              className={`rounded-md border px-2 py-0.5 ${
                hoursSummary.dayStatus === "met"
                  ? "border-emerald-500/40 bg-emerald-500/15 text-emerald-200"
                  : hoursSummary.dayStatus === "short"
                    ? "border-amber-500/40 bg-amber-500/15 text-amber-100"
                    : "border-white/20 bg-white/5 text-muted-foreground"
              }`}
              title="Study blocks on the selected day vs your daily focus goal."
            >
              {dayLabel}: {hoursSummary.dayH.toFixed(1)}h / {hoursSummary.dayGoalH}h
              {hoursSummary.dayStatus === "met"
                ? " · met"
                : hoursSummary.unplannedH > 0.05
                  ? ` · ${hoursSummary.unplannedH.toFixed(1)}h short`
                  : ""}
            </span>
            <span className="rounded-md border border-white/15 bg-white/5 px-2 py-0.5 text-muted-foreground">
              {hoursSummary.plannedH.toFixed(1)}h study planned
              {hoursSummary.weekGoalH != null ? ` / ${hoursSummary.weekGoalH}h week` : ""}
            </span>
            <span
              className="rounded-md border border-white/15 bg-white/5 px-2 py-0.5 text-muted-foreground"
              title={`${counts.study} study · ${counts.brk} breaks · ${counts.routine} routines · ${counts.existing} calendar`}
            >
              {counts.study + counts.brk + counts.routine} editable · {counts.existing} calendar
            </span>
          </div>
        </div>
        <div className="flex flex-wrap gap-2 relative">
          <button
            type="button"
            onClick={() => (placing ? cancelPlaceMode() : beginPlaceMode())}
            disabled={embedded}
            className={`inline-flex items-center gap-1 rounded-lg border px-2.5 py-1.5 text-xs transition-colors ${
              placing
                ? "border-primary/50 bg-primary/20 text-foreground ring-1 ring-primary/40"
                : "border-white/10 hover:bg-white/5"
            } disabled:opacity-40`}
            title={
              embedded
                ? "Place blocks from the calendar after Apply, or edit times below"
                : placing
                  ? "Esc to cancel"
                  : "Then click empty time on the day strip"
            }
          >
            <Plus size={12} />
            {placing ? "Cancel place" : "Add block"}
          </button>
          <button
            type="button"
            disabled={proposing || blocks.length === 0}
            onClick={fixOverlaps}
            className="inline-flex items-center gap-1 rounded-lg border border-amber-500/35 bg-amber-500/10 px-2.5 py-1.5 text-xs text-amber-100 hover:bg-amber-500/20 disabled:opacity-50"
            title="Dedupe copies and shift later blocks so nothing stacks"
          >
            <Layers size={12} />
            Fix overlaps
          </button>
          <button
            type="button"
            disabled={proposing || applyable === 0}
            onClick={applyAllDrafts}
            className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-3 py-1.5 text-xs text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
            title={
              draftDayKeys.length
                ? `Apply ${applyable} blocks across ${draftDayKeys.length} day${draftDayKeys.length === 1 ? "" : "s"}`
                : "No drafts to apply"
            }
          >
            {proposing ? <Loader2 size={12} className="animate-spin" /> : <CalendarDays size={12} />}
            Apply plan
            {draftDayKeys.length > 0 ? ` (${draftDayKeys.length}d)` : ""}
          </button>
          {draftDayKeys.length > 1 ? (
            <button
              type="button"
              disabled={proposing || applyable === 0}
              onClick={applyTodayOnly}
              className="rounded-lg border border-white/10 px-2.5 py-1.5 text-xs text-muted-foreground hover:bg-white/5 hover:text-foreground disabled:opacity-50"
            >
              Today only
            </button>
          ) : null}
          <button
            type="button"
            onClick={onDismiss}
            className="rounded-lg border border-white/10 px-2.5 py-1.5 text-xs hover:bg-white/5"
          >
            Dismiss
          </button>
        </div>
      </div>

      {placing ? (
        <div className="rounded-lg border border-primary/35 bg-primary/10 px-3 py-2 text-xs text-foreground/90">
          Click empty time on the day strip to place a 1h study block · Esc or Cancel place to exit
        </div>
      ) : null}

      {days.length > 1 && (
        <div className="flex flex-wrap gap-1.5">
          {days.map((d) => {
            const row = perDayPlan.get(d);
            const plannedH = (row?.plannedMin ?? 0) / 60;
            const status = row?.status ?? "empty";
            const n = blocks.filter((b) => dayKey(b.start_at) === d).length;
            const active = d === day;
            const tone =
              status === "met"
                ? active
                  ? "border-emerald-400 bg-emerald-500/20 text-emerald-100"
                  : "border-emerald-500/35 bg-emerald-500/10 text-emerald-200/90"
                : status === "short"
                  ? active
                    ? "border-amber-400 bg-amber-500/20 text-amber-100"
                    : "border-amber-500/35 bg-amber-500/10 text-amber-100/90"
                  : active
                    ? "border-white/40 bg-white/10 text-foreground"
                    : "border-white/10 bg-black/30 text-muted-foreground hover:bg-white/5";
            return (
              <button
                key={d}
                type="button"
                onClick={() => {
                  setActiveDay(d);
                  setSelectedIdx(null);
                }}
                title={
                  status === "met"
                    ? `Plan filled ${plannedH.toFixed(1)}h (scheduled study — focus met is on-plan productive only)`
                    : status === "short"
                      ? `Scheduled ${plannedH.toFixed(1)}h · still need ${((row?.unplannedMin ?? 0) / 60).toFixed(1)}h on calendar`
                      : "No study planned this day"
                }
                className={`rounded-lg px-2.5 py-1 text-xs border transition-colors ${tone}`}
              >
                {parseDay(d).toLocaleDateString(undefined, {
                  weekday: "short",
                  month: "short",
                  day: "numeric",
                })}
                <span className="ml-1 opacity-80">
                  {plannedH > 0 ? `${plannedH.toFixed(1)}h` : "—"}
                  {status === "short" ? " short" : status === "met" ? " ✓" : ""}
                  <span className="opacity-50"> · {n}</span>
                </span>
              </button>
            );
          })}
        </div>
      )}

      {!embedded && (
      <>
      {/* Always-visible agenda wrapper — no hunting in empty morning hours */}
      <div className="rounded-xl border border-white/10 bg-black/30 p-3 space-y-2">
        <div className="flex items-center justify-between gap-2 text-xs">
          <span className="font-medium text-foreground/90">{dayLabel} agenda</span>
          <span className="text-muted-foreground">
            planned {hoursSummary.dayH.toFixed(1)}h
            {hoursSummary.unplannedH > 0.05
              ? ` · unplanned ${hoursSummary.unplannedH.toFixed(1)}h`
              : hoursSummary.dayStatus === "met"
                ? " · goal met"
                : ""}
            {" · "}
            {dayBlocks.length} block{dayBlocks.length === 1 ? "" : "s"}
          </span>
        </div>
        {dayBlocks.length ? (
          <ul className="space-y-1.5 max-h-40 overflow-y-auto">
            {dayBlocks.map(({ b, index }) => {
              const color = blockColor(b.category);
              const badge = sourceBadge(b.source);
              const active = selectedIdx === index;
              return (
                <li key={`agenda-${index}`}>
                  <button
                    type="button"
                    onClick={() => setSelectedIdx(index)}
                    className={`w-full flex items-center gap-2 rounded-lg border px-2.5 py-2 text-left transition-colors ${
                      active
                        ? "border-primary/50 bg-primary/15"
                        : "border-white/10 bg-black/25 hover:bg-white/[0.04]"
                    }`}
                  >
                    <span
                      className="h-8 w-1 shrink-0 rounded-full"
                      style={{ backgroundColor: color }}
                    />
                    <span className="min-w-0 flex-1">
                      <span className="block text-xs font-medium truncate text-foreground">
                        {b.title}
                      </span>
                      <span className="block text-[10px] text-muted-foreground">
                        {formatTime(b.start_at)} – {formatTime(b.end_at)} · {b.category}
                      </span>
                    </span>
                    <span className={`shrink-0 rounded border px-1.5 py-0.5 text-[9px] ${badge.className}`}>
                      {badge.label}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        ) : (
          <p className="text-xs text-muted-foreground py-2">
            No blocks this day — click Add block, then click empty time on the strip.
          </p>
        )}
      </div>

      <div
        className={
          embedded
            ? "space-y-4"
            : "grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(15rem,19rem)]"
        }
      >
        {!embedded ? (
        <div className="rounded-xl border border-white/10 bg-gradient-to-b from-black/40 to-black/25 overflow-hidden shadow-inner ring-1 ring-white/5 flex flex-col max-h-[min(44rem,72vh)]">
          <div className="sticky top-0 shrink-0 z-20 px-3 py-2 border-b border-white/10 text-xs text-muted-foreground flex justify-between bg-[#16181f]/90 backdrop-blur-sm">
            <span className="font-medium text-foreground/80">Day strip · {dayLabel}</span>
            <span className="tabular-nums">
              {dayBlocks.length} visible · {rangeLabel}
            </span>
          </div>
          <div
            ref={scrollRef}
            className="min-h-0 flex-1 overflow-y-auto overscroll-contain [scrollbar-gutter:stable]"
          >
            <div
              ref={gridRef}
              className={`relative flex pt-3 pb-2 contain-layout ${
                placing ? "cursor-crosshair" : "cursor-default"
              }`}
              style={{ height: timelineH + 20 }}
              onClick={onGridClick}
            >
              <div className="w-11 shrink-0 sticky left-0 z-10 border-r border-white/10 relative text-[10px] text-muted-foreground bg-[#12141a]/95 backdrop-blur-[2px]">
                {hours.map((h) => {
                  const y = (h * 60 - axisStart) * PX_PER_MIN + 12;
                  return (
                    <div
                      key={h}
                      className="absolute right-1.5 tabular-nums leading-none"
                      style={{ top: y }}
                    >
                      {formatHour(h)}
                    </div>
                  );
                })}
              </div>
              <div className="relative flex-1 min-w-0 will-change-contents">
                {hours.map((h) => (
                  <div
                    key={h}
                    className="absolute left-0 right-0 border-t border-white/[0.08] pointer-events-none"
                    style={{ top: (h * 60 - axisStart) * PX_PER_MIN + 12 }}
                  />
                ))}
                {hours.slice(0, -1).map((h) => (
                  <div
                    key={`h-${h}`}
                    className="absolute left-0 right-0 border-t border-dashed border-white/[0.04] pointer-events-none"
                    style={{ top: (h * 60 + 30 - axisStart) * PX_PER_MIN + 12 }}
                  />
                ))}
                {dayBlocks.map(({ b, index }) => {
                  const start = minutesSinceMidnight(new Date(b.start_at));
                  const end = minutesSinceMidnight(new Date(b.end_at));
                  const durMin = Math.max(1, end - start);
                  const top = (start - axisStart) * PX_PER_MIN + 12;
                  // True duration only — min-height would spill into later blocks (e.g. 10m break → 10:40)
                  const height = durMin * PX_PER_MIN;
                  const compact = height < 34;
                  const showMeta = height >= 34;
                  const color = blockColor(b.category);
                  const active = selectedIdx === index;
                  const badge = sourceBadge(b.source);
                  const laneInfo = laneMap.get(index) ?? { lane: 0, laneCount: 1 };
                  const gap = 6;
                  const widthPct = 100 / laneInfo.laneCount;
                  const leftPct = laneInfo.lane * widthPct;
                  return (
                    <div
                      key={`blk-${index}`}
                      data-plan-block
                      ref={(el) => {
                        if (el) blockEls.current.set(index, el);
                        else blockEls.current.delete(index);
                      }}
                      role="button"
                      tabIndex={0}
                      onPointerDown={(e) => onPointerDownBlock(e, index)}
                      onPointerMove={onPointerMoveBlock}
                      onPointerUp={onPointerUpBlock}
                      onPointerCancel={onPointerUpBlock}
                      onClick={(e) => {
                        e.stopPropagation();
                        if (suppressClickRef.current) {
                          e.preventDefault();
                          return;
                        }
                        setSelectedIdx(index);
                      }}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" || e.key === " ") setSelectedIdx(index);
                      }}
                      className={`absolute rounded-md text-left select-none overflow-hidden touch-none ${
                        compact ? "pl-1 pr-1.5 py-0" : "pl-1 pr-2.5 py-1"
                      } ${
                        placing
                          ? "cursor-pointer"
                          : "cursor-grab active:cursor-grabbing"
                      } ${
                        active
                          ? "ring-2 ring-primary z-20 shadow-lg"
                          : "z-10 hover:brightness-110"
                      }`}
                      style={{
                        top,
                        height,
                        left: `calc(${leftPct}% + ${gap / 2}px)`,
                        width: `calc(${widthPct}% - ${gap}px)`,
                        background: `linear-gradient(135deg, ${color}66, ${color}30)`,
                        borderLeft: `3px solid ${color}`,
                      }}
                      title={`${b.title} · ${formatTime(b.start_at)} – ${formatTime(b.end_at)} · ${badge.label}`}
                    >
                      <div className="flex items-center gap-1 h-full min-h-0">
                        {!compact ? (
                          <>
                            <span
                              className="flex w-3.5 shrink-0 items-center justify-center text-foreground/45"
                              aria-hidden
                            >
                              <GripVertical size={12} className="pointer-events-none" />
                            </span>
                            <span
                              className="w-px self-stretch shrink-0 bg-white/15 my-0.5"
                              aria-hidden
                            />
                          </>
                        ) : null}
                        <div className="min-w-0 flex-1 flex flex-col justify-center gap-0.5">
                          <div
                            className={`font-semibold leading-none truncate text-foreground ${
                              compact ? "text-[10px]" : "text-[11px] leading-tight"
                            }`}
                          >
                            {compact
                              ? `${b.title} · ${formatTime(b.start_at)}–${formatTime(b.end_at)}`
                              : b.title}
                          </div>
                          {showMeta ? (
                            <div className="text-[10px] leading-tight text-muted-foreground truncate flex items-center gap-1.5">
                              <span>
                                {formatTime(b.start_at)} – {formatTime(b.end_at)}
                              </span>
                              <span
                                className={`rounded border px-1 py-px text-[9px] ${badge.className}`}
                              >
                                {badge.label}
                              </span>
                            </div>
                          ) : null}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </div>
        ) : null}

        <div className="rounded-xl border border-white/10 bg-black/25 p-4 space-y-3">
          {selected && selectedIdx != null ? (
            <>
              <h4 className="text-xs font-semibold flex items-center gap-1.5 text-muted-foreground">
                <Pencil size={12} />
                Edit block
              </h4>
              <span
                className={`inline-flex rounded border px-1.5 py-0.5 text-[10px] ${sourceBadge(selected.source).className}`}
              >
                {sourceBadge(selected.source).label}
              </span>
              {selectedFromCalendar ? (
                <p className="text-[10px] text-sky-200/90 leading-relaxed">
                  From your calendar — drag or edit to include it when you Apply.
                </p>
              ) : null}
              <label className="block text-xs text-muted-foreground">
                Title
                <input
                  value={selected.title}
                  onChange={(e) => updateAt(selectedIdx, { title: e.target.value })}
                  className="mt-1 w-full rounded-lg border border-white/10 bg-black/40 px-2 py-1.5 text-sm text-foreground"
                />
              </label>
              <label className="block text-xs text-muted-foreground">
                Category
                <select
                  value={selected.category}
                  onChange={(e) => updateAt(selectedIdx, { category: e.target.value })}
                  className="mt-1 w-full rounded-lg border border-white/10 bg-black/40 px-2 py-1.5 text-sm text-foreground"
                >
                  {[selected.category, ...CATEGORIES.filter((c) => c !== selected.category)].map(
                    (c) => (
                      <option key={c} value={c}>
                        {c}
                      </option>
                    ),
                  )}
                </select>
              </label>
              <label className="block text-xs text-muted-foreground">
                Start
                <input
                  type="datetime-local"
                  min={`${todayKey}T00:00`}
                  value={toLocalInput(selected.start_at)}
                  onChange={(e) => {
                    let { start_at, end_at } = fromLocalInput(e.target.value, selectedDuration);
                    const lk = dayKey(start_at);
                    if (lk < todayKey) {
                      const clamped = fromLocalInput(`${todayKey}T09:00`, selectedDuration);
                      start_at = clamped.start_at;
                      end_at = clamped.end_at;
                    }
                    updateAt(selectedIdx, { start_at, end_at });
                    setActiveDay(dayKey(start_at));
                  }}
                  className="mt-1 w-full rounded-lg border border-white/10 bg-black/40 px-2 py-1.5 text-sm text-foreground"
                />
              </label>
              <label className="block text-xs text-muted-foreground">
                Duration (min)
                <input
                  type="number"
                  min={15}
                  max={480}
                  step={15}
                  value={selectedDuration}
                  onChange={(e) => {
                    const mins = Math.max(15, Math.min(480, Number(e.target.value) || 60));
                    const start = new Date(selected.start_at);
                    const end = new Date(start.getTime() + mins * 60_000);
                    updateAt(selectedIdx, { end_at: end.toISOString() });
                  }}
                  className="mt-1 w-full rounded-lg border border-white/10 bg-black/40 px-2 py-1.5 text-sm text-foreground"
                />
              </label>
              <div className="flex flex-col gap-2 pt-1">
                <button
                  type="button"
                  onClick={replaceSelected}
                  className="w-full rounded-lg border border-white/15 px-2 py-1.5 text-xs hover:bg-white/5"
                >
                  Replace with blank study block
                </button>
                <button
                  type="button"
                  onClick={() => removeAt(selectedIdx)}
                  className="w-full inline-flex items-center justify-center gap-1.5 rounded-lg border border-red-500/30 text-red-300 px-2 py-1.5 text-xs hover:bg-red-500/10"
                >
                  <Trash2 size={12} />
                  Remove block
                </button>
              </div>
            </>
          ) : (
            <p className="text-xs text-muted-foreground leading-relaxed">
              {embedded
                ? "Pick a row in the agenda above to edit times or remove a block."
                : "Pick a row in the agenda (always visible above) or a colored block on the day strip."}
            </p>
          )}
        </div>
      </div>
      </>
      )}
    </div>
  );
}
