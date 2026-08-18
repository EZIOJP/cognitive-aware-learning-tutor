import { useEffect, useMemo, useRef, useState, type PointerEvent as ReactPointerEvent } from "react";
import { addDays, endOfDay, format, startOfDay } from "date-fns";
import {
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ChevronUp,
  Pencil,
  Plus,
  Trash2,
} from "lucide-react";
import {
  blockColor,
  type PlannerBlock,
  type ProposedPlannerBlock,
} from "../../api/plannerClient";
import { draftCoveredBySavedBlocks, parseApiDate } from "./planVsActualUtils";
import { formatHoursMins } from "../../utils/formatDuration";
import {
  hasRoutineDrag,
  readRoutineDragData,
  type RoutineDragPayload,
} from "./routineDrag";

const SNAP_MIN = 15;
const CATEGORIES = [
  "Coding Practice",
  "AI / ML",
  "Study / Reading",
  "Coursework (Browser)",
  "personal",
  "break",
  "reading",
  "study",
  "lecture",
  "review",
];

type AgendaItem = {
  key: string;
  title: string;
  start: Date;
  end: Date;
  category: string;
  color: string | null;
  isDraft: boolean;
  status?: string;
  block?: PlannerBlock;
  /** Index into the full draftBlocks array (when isDraft) */
  draftIndex?: number;
};

type Props = {
  day: Date;
  blocks: PlannerBlock[];
  draftBlocks?: ProposedPlannerBlock[] | null;
  loading?: boolean;
  error?: string | null;
  onDayChange: (day: Date) => void;
  onAdd: (at: Date) => void;
  /** Place a dragged daily routine at this hour (copy — routine list unchanged). */
  onPlaceRoutine?: (at: Date, routine: RoutineDragPayload) => Promise<void> | void;
  onUpdateSaved: (
    id: number,
    patch: { title?: string; category?: string; start_at?: string; end_at?: string },
  ) => Promise<void>;
  onDeleteSaved: (id: number) => Promise<void>;
  onChangeDrafts?: (blocks: ProposedPlannerBlock[]) => void;
};

function toLocalInput(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function shiftTimes(start: Date, end: Date, deltaMin: number): { start: Date; end: Date } {
  const ms = deltaMin * 60_000;
  return { start: new Date(start.getTime() + ms), end: new Date(end.getTime() + ms) };
}

function durationMin(start: Date, end: Date): number {
  return Math.max(1, Math.round((end.getTime() - start.getTime()) / 60_000));
}

/** Pack overlapping intervals into side-by-side lanes (calendar-style). */
function assignOverlapLanes(items: AgendaItem[]): Map<string, { lane: number; laneCount: number }> {
  const layout = new Map<string, { lane: number; laneCount: number }>();
  if (!items.length) return layout;

  const sorted = [...items].sort((a, b) => {
    const ds = a.start.getTime() - b.start.getTime();
    if (ds !== 0) return ds;
    return b.end.getTime() - a.end.getTime();
  });

  type Active = { key: string; end: number; lane: number };
  const active: Active[] = [];
  const clusters: string[][] = [];
  let cluster: string[] = [];
  const lanesByKey = new Map<string, number>();

  for (const ev of sorted) {
    const startMs = ev.start.getTime();
    const endMs = ev.end.getTime();
    for (let i = active.length - 1; i >= 0; i--) {
      if (active[i].end <= startMs) active.splice(i, 1);
    }
    if (active.length === 0 && cluster.length) {
      clusters.push(cluster);
      cluster = [];
    }
    const used = new Set(active.map((a) => a.lane));
    let lane = 0;
    while (used.has(lane)) lane += 1;
    active.push({ key: ev.key, end: endMs, lane });
    lanesByKey.set(ev.key, lane);
    cluster.push(ev.key);
  }
  if (cluster.length) clusters.push(cluster);

  for (const keys of clusters) {
    const maxLane = Math.max(0, ...keys.map((k) => lanesByKey.get(k) ?? 0));
    const laneCount = maxLane + 1;
    for (const k of keys) {
      layout.set(k, { lane: lanesByKey.get(k) ?? 0, laneCount });
    }
  }
  return layout;
}

export function PlanningDayAgenda({
  day,
  blocks,
  draftBlocks,
  loading,
  error,
  onDayChange,
  onAdd,
  onPlaceRoutine,
  onUpdateSaved,
  onDeleteSaved,
  onChangeDrafts,
}: Props) {
  const from = startOfDay(day);
  const to = endOfDay(day);
  const dayKey = format(from, "yyyy-MM-dd");
  const [expandedKey, setExpandedKey] = useState<string | null>(null);
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [editCategory, setEditCategory] = useState("");
  const [editStart, setEditStart] = useState("");
  const [editEnd, setEditEnd] = useState("");
  const [editError, setEditError] = useState<string | null>(null);
  const [dropHour, setDropHour] = useState<number | null>(null);
  const suppressSlotClick = useRef(false);
  const [blockDrag, setBlockDrag] = useState<{
    key: string;
    pointerId: number;
    originClientY: number;
    originStartM: number;
    durationM: number;
    previewStartM: number;
  } | null>(null);
  const blockDragRef = useRef(blockDrag);
  blockDragRef.current = blockDrag;

  const items: AgendaItem[] = useMemo(() => {
    const dayStart = startOfDay(day);
    const dayEnd = endOfDay(day);
    const saved = blocks.filter((b) => b.status !== "rolled");
    const drafts = draftBlocks ?? [];

    const savedItems: AgendaItem[] = saved
      .map((b) => {
        const start = parseApiDate(b.start_at);
        const end = parseApiDate(b.end_at);
        return {
          block: b,
          start,
          end,
          title: b.title,
          category: b.category,
          color: b.color,
          isDraft: false,
          status: b.status,
          key: `b-${b.id}`,
        };
      })
      .filter((x) => x.start < dayEnd && x.end > dayStart);

    const draftItems: AgendaItem[] = drafts
      .map((b, draftIndex) => {
        if (b.source === "existing") return null;
        if (draftCoveredBySavedBlocks(b, saved)) return null;
        const start = parseApiDate(b.start_at);
        const end = parseApiDate(b.end_at);
        if (!(start < dayEnd && end > dayStart)) return null;
        return {
          start,
          end,
          title: b.title,
          category: b.category,
          color: null as string | null,
          isDraft: true,
          draftIndex,
          key: `d-${draftIndex}`,
        };
      })
      .filter((x): x is NonNullable<typeof x> => x != null);

    return [...savedItems, ...draftItems].sort((a, b) => a.start.getTime() - b.start.getTime());
  }, [blocks, draftBlocks, dayKey, day]);

  const draftCount = items.filter((i) => i.isDraft).length;
  const drafts = draftBlocks ?? [];
  const scrollRef = useRef<HTMLDivElement>(null);
  const laneLayout = useMemo(() => assignOverlapLanes(items), [items]);

  /** Full day strip: 12 AM → 12 AM (next) */
  const AXIS_START = 0;
  const AXIS_END = 24 * 60;
  const PX_PER_MIN = 1.35;
  const timelineH = (AXIS_END - AXIS_START) * PX_PER_MIN;
  const hours = Array.from({ length: 25 }, (_, i) => i);

  /** Scroll so morning (~6 AM) or first block is in view */
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const first = items[0];
    const targetMin = first
      ? Math.max(0, first.start.getHours() * 60 + first.start.getMinutes() - 30)
      : 6 * 60;
    el.scrollTop = targetMin * PX_PER_MIN;
  }, [dayKey]); // eslint-disable-line react-hooks/exhaustive-deps -- intentional on day change only

  const minutesSinceMidnight = (d: Date) => d.getHours() * 60 + d.getMinutes();

  const formatHourLabel = (h: number) => {
    if (h === 0 || h === 24) return "12 AM";
    if (h === 12) return "12 PM";
    if (h < 12) return `${h} AM`;
    return `${h - 12} PM`;
  };

  const openEdit = (ev: AgendaItem) => {
    setExpandedKey(ev.key);
    setEditTitle(ev.title);
    setEditCategory(ev.category);
    setEditStart(toLocalInput(ev.start));
    setEditEnd(toLocalInput(ev.end));
    setEditError(null);
  };

  const closeEdit = () => {
    setExpandedKey(null);
    setEditError(null);
  };

  const runBusy = async (key: string, fn: () => Promise<void>) => {
    setBusyKey(key);
    setEditError(null);
    try {
      await fn();
    } catch (e) {
      setEditError(e instanceof Error ? e.message : "Update failed");
    } finally {
      setBusyKey(null);
    }
  };

  const patchDraft = (draftIndex: number, patch: Partial<ProposedPlannerBlock>) => {
    if (!onChangeDrafts) return;
    const next = drafts.map((b, i) => (i === draftIndex ? { ...b, ...patch } : b));
    onChangeDrafts(next);
  };

  const removeDraft = (draftIndex: number) => {
    if (!onChangeDrafts) return;
    onChangeDrafts(drafts.filter((_, i) => i !== draftIndex));
    closeEdit();
  };

  const moveItem = async (ev: AgendaItem, deltaMin: number) => {
    const { start, end } = shiftTimes(ev.start, ev.end, deltaMin);
    await runBusy(ev.key, async () => {
      if (ev.isDraft && ev.draftIndex != null) {
        patchDraft(ev.draftIndex, {
          start_at: start.toISOString(),
          end_at: end.toISOString(),
        });
        if (expandedKey === ev.key) {
          setEditStart(toLocalInput(start));
          setEditEnd(toLocalInput(end));
        }
      } else if (ev.block) {
        await onUpdateSaved(ev.block.id, {
          start_at: start.toISOString(),
          end_at: end.toISOString(),
        });
      }
    });
  };

  const saveEdit = async (ev: AgendaItem) => {
    const start = new Date(editStart);
    const end = new Date(editEnd);
    if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) {
      setEditError("Invalid start or end time");
      return;
    }
    if (end <= start) {
      setEditError("End must be after start");
      return;
    }
    await runBusy(ev.key, async () => {
      if (ev.isDraft && ev.draftIndex != null) {
        patchDraft(ev.draftIndex, {
          title: editTitle.trim() || ev.title,
          category: editCategory || ev.category,
          start_at: start.toISOString(),
          end_at: end.toISOString(),
        });
        closeEdit();
      } else if (ev.block) {
        await onUpdateSaved(ev.block.id, {
          title: editTitle.trim() || ev.title,
          category: editCategory || ev.category,
          start_at: start.toISOString(),
          end_at: end.toISOString(),
        });
        closeEdit();
      }
    });
  };

  const deleteItem = async (ev: AgendaItem) => {
    await runBusy(ev.key, async () => {
      if (ev.isDraft && ev.draftIndex != null) {
        removeDraft(ev.draftIndex);
      } else if (ev.block) {
        await onDeleteSaved(ev.block.id);
        closeEdit();
      }
    });
  };

  const snapPreviewStart = (originStartM: number, durationM: number, clientY: number, originClientY: number) => {
    const dy = clientY - originClientY;
    const rawDelta = Math.round(dy / PX_PER_MIN / SNAP_MIN) * SNAP_MIN;
    return Math.max(AXIS_START, Math.min(AXIS_END - durationM, originStartM + rawDelta));
  };

  const beginBlockDrag = (e: ReactPointerEvent, ev: AgendaItem, startM: number, endClamped: number) => {
    if (expandedKey === ev.key || busyKey === ev.key) return;
    e.preventDefault();
    e.stopPropagation();
    const durationM = Math.max(SNAP_MIN, endClamped - startM);
    const target = e.currentTarget as HTMLElement;
    target.setPointerCapture(e.pointerId);
    setBlockDrag({
      key: ev.key,
      pointerId: e.pointerId,
      originClientY: e.clientY,
      originStartM: startM,
      durationM,
      previewStartM: startM,
    });
  };

  const onBlockDragMove = (e: ReactPointerEvent) => {
    const d = blockDragRef.current;
    if (!d || e.pointerId !== d.pointerId) return;
    const previewStartM = snapPreviewStart(d.originStartM, d.durationM, e.clientY, d.originClientY);
    if (previewStartM !== d.previewStartM) {
      setBlockDrag({ ...d, previewStartM });
    }
  };

  const endBlockDrag = async (e: ReactPointerEvent, ev: AgendaItem) => {
    const d = blockDragRef.current;
    if (!d || e.pointerId !== d.pointerId || d.key !== ev.key) return;
    try {
      (e.currentTarget as HTMLElement).releasePointerCapture(e.pointerId);
    } catch {
      /* ignore */
    }
    const delta = d.previewStartM - d.originStartM;
    setBlockDrag(null);
    if (delta !== 0) await moveItem(ev, delta);
  };

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="inline-flex items-center gap-0.5 rounded-lg border border-white/10 bg-black/30 p-0.5">
          <button
            type="button"
            aria-label="Previous day"
            onClick={() => onDayChange(addDays(from, -1))}
            className="rounded-md p-1.5 text-muted-foreground hover:bg-white/10 hover:text-foreground"
          >
            <ChevronLeft size={14} />
          </button>
          <button
            type="button"
            onClick={() => onDayChange(startOfDay(new Date()))}
            className="min-w-[7.5rem] rounded-md px-2 py-1 text-center text-xs font-medium text-foreground hover:bg-white/5"
          >
            {format(day, "EEE MMM d")}
          </button>
          <button
            type="button"
            aria-label="Next day"
            onClick={() => onDayChange(addDays(from, 1))}
            className="rounded-md p-1.5 text-muted-foreground hover:bg-white/10 hover:text-foreground"
          >
            <ChevronRight size={14} />
          </button>
        </div>
        <div className="flex items-center gap-2">
          {draftCount > 0 ? (
            <span className="text-[10px] tabular-nums text-primary">
              {draftCount} draft{draftCount === 1 ? "" : "s"}
            </span>
          ) : null}
          <button
            type="button"
            onClick={() => {
              const last = items[items.length - 1];
              const base = last ? new Date(last.end.getTime() + 5 * 60_000) : new Date(from);
              if (!last) base.setHours(9, 0, 0, 0);
              onAdd(base);
            }}
            className="inline-flex items-center gap-1 rounded-lg border border-primary/35 bg-primary/15 px-2.5 py-1.5 text-xs text-primary hover:bg-primary/25"
          >
            <Plus size={12} /> Add block
          </button>
        </div>
      </div>

      <p className="text-[10px] text-muted-foreground">
        Full day 12 AM–12 AM · drag color bar to move · drop a routine on an hour · tap to edit · ↑↓{" "}
        {SNAP_MIN}m · trash deletes
      </p>

      {error ? <p className="text-xs text-red-400">{error}</p> : null}
      {loading ? <p className="text-xs text-muted-foreground">Loading…</p> : null}

      <div className="rounded-xl border border-white/10 bg-black/30 overflow-hidden">
        <div
          ref={scrollRef}
          className="max-h-[min(42rem,70vh)] overflow-y-auto overscroll-contain"
        >
          <div className="relative flex" style={{ height: timelineH + 16 }}>
            {/* Hour gutter */}
            <div className="relative w-14 shrink-0 border-r border-white/10 bg-[#12141a]/90">
              {hours.map((h) => {
                const y = h * 60 * PX_PER_MIN + 8;
                return (
                  <div
                    key={h}
                    className="absolute right-1.5 -translate-y-1/2 text-[10px] tabular-nums leading-none text-muted-foreground"
                    style={{ top: y }}
                  >
                    {formatHourLabel(h)}
                  </div>
                );
              })}
            </div>

            {/* Day lane */}
            <div className="relative min-w-0 flex-1">
              {hours.slice(0, 24).map((h) => {
                const y = h * 60 * PX_PER_MIN + 8;
                const isDropTarget = dropHour === h;
                return (
                  <button
                    key={`slot-${h}`}
                    type="button"
                    title={`Add block at ${formatHourLabel(h)} · drop a routine here`}
                    onClick={() => {
                      if (suppressSlotClick.current) {
                        suppressSlotClick.current = false;
                        return;
                      }
                      const at = new Date(from);
                      at.setHours(h, 0, 0, 0);
                      onAdd(at);
                    }}
                    onDragEnter={(e) => {
                      if (!onPlaceRoutine || !hasRoutineDrag(e.dataTransfer)) return;
                      e.preventDefault();
                      setDropHour(h);
                    }}
                    onDragOver={(e) => {
                      if (!onPlaceRoutine || !hasRoutineDrag(e.dataTransfer)) return;
                      e.preventDefault();
                      e.dataTransfer.dropEffect = "copy";
                      if (dropHour !== h) setDropHour(h);
                    }}
                    onDragLeave={() => {
                      setDropHour((cur) => (cur === h ? null : cur));
                    }}
                    onDrop={(e) => {
                      e.preventDefault();
                      setDropHour(null);
                      if (!onPlaceRoutine) return;
                      const payload = readRoutineDragData(e.dataTransfer);
                      if (!payload) return;
                      suppressSlotClick.current = true;
                      const at = new Date(from);
                      at.setHours(h, 0, 0, 0);
                      void onPlaceRoutine(at, payload);
                    }}
                    className={`absolute left-0 right-0 border-t border-white/[0.08] transition-colors duration-150 ${
                      isDropTarget
                        ? "bg-primary/15 ring-1 ring-inset ring-primary/40"
                        : "hover:bg-primary/5"
                    }`}
                    style={{ top: y, height: 60 * PX_PER_MIN }}
                    aria-label={`Add at ${formatHourLabel(h)}`}
                  />
                );
              })}
              {/* Half-hour ticks */}
              {hours.slice(0, 24).map((h) => (
                <div
                  key={`half-${h}`}
                  className="pointer-events-none absolute left-0 right-0 border-t border-dashed border-white/[0.04]"
                  style={{ top: (h * 60 + 30) * PX_PER_MIN + 8 }}
                />
              ))}

              {items.map((ev) => {
                const color = blockColor(ev.category, ev.color);
                const mins = durationMin(ev.start, ev.end);
                const startM = Math.max(AXIS_START, Math.min(AXIS_END - 1, minutesSinceMidnight(ev.start)));
                const endM = Math.max(startM + 5, Math.min(AXIS_END, minutesSinceMidnight(ev.end) || AXIS_END));
                // Cross-midnight end = 0 → treat as end of day if after start
                const endClamped =
                  minutesSinceMidnight(ev.end) === 0 && endM <= startM ? AXIS_END : endM;
                const dragging = blockDrag?.key === ev.key;
                const displayStartM = dragging ? blockDrag.previewStartM : startM;
                const top = (displayStartM - AXIS_START) * PX_PER_MIN + 8;
                const height = Math.max(36, (endClamped - startM) * PX_PER_MIN - 3);
                const open = expandedKey === ev.key;
                const busy = busyKey === ev.key;
                const compact = height < 52;
                const { lane, laneCount } = laneLayout.get(ev.key) ?? { lane: 0, laneCount: 1 };
                const gapPx = 4;
                const insetPx = 6;
                const colW = `calc((100% - ${insetPx * 2}px - ${(laneCount - 1) * gapPx}px) / ${laneCount})`;
                const leftStyle = `calc(${insetPx}px + ${lane} * (${colW} + ${gapPx}px))`;
                const previewLabelStart = dragging
                  ? (() => {
                      const d = new Date(from);
                      d.setHours(0, 0, 0, 0);
                      d.setMinutes(displayStartM);
                      return d;
                    })()
                  : ev.start;
                const previewLabelEnd = dragging
                  ? (() => {
                      const d = new Date(previewLabelStart);
                      d.setMinutes(d.getMinutes() + mins);
                      return d;
                    })()
                  : ev.end;

                return (
                  <div
                    key={ev.key}
                    className={`absolute z-10 overflow-hidden rounded-lg border shadow-[0_1px_0_rgba(255,255,255,0.04)_inset] ${
                      ev.isDraft
                        ? "border-dashed border-primary/50 bg-primary/[0.12]"
                        : "border-white/14 bg-[#161922]/92"
                    } ${
                      open
                        ? "z-30 ring-2 ring-primary/45 shadow-lg shadow-black/40"
                        : dragging
                          ? "z-40 border-primary/50 bg-[#1a1e28] shadow-lg shadow-black/50 opacity-95"
                          : "hover:border-white/22 hover:bg-[#1a1e28]"
                    }`}
                    style={{
                      top,
                      left: open ? insetPx : leftStyle,
                      width: open ? `calc(100% - ${insetPx * 2}px)` : colW,
                      height: open ? "auto" : height,
                      minHeight: open ? undefined : height,
                      transition: dragging ? "none" : "top 120ms ease-out",
                    }}
                  >
                    <div
                      role="slider"
                      aria-label={`Drag to move ${ev.title}`}
                      aria-valuemin={AXIS_START}
                      aria-valuemax={AXIS_END - Math.max(SNAP_MIN, endClamped - startM)}
                      aria-valuenow={displayStartM}
                      title="Drag to move"
                      tabIndex={0}
                      onPointerDown={(e) => beginBlockDrag(e, ev, startM, endClamped)}
                      onPointerMove={onBlockDragMove}
                      onPointerUp={(e) => void endBlockDrag(e, ev)}
                      onPointerCancel={(e) => void endBlockDrag(e, ev)}
                      className={`absolute inset-y-0 left-0 z-20 w-3 touch-none select-none ${
                        open || busy ? "pointer-events-none" : "cursor-grab active:cursor-grabbing"
                      }`}
                    >
                      <span
                        className="pointer-events-none absolute inset-y-0 left-0 w-[3px] rounded-l-sm"
                        style={{ backgroundColor: color }}
                        aria-hidden
                      />
                    </div>
                    <div className={`flex h-full min-h-[36px] flex-col gap-0.5 pl-2.5 pr-1 ${compact && !open ? "py-1" : "py-1.5"}`}>
                      <div className="flex min-h-0 flex-1 items-start gap-0.5">
                        <button
                          type="button"
                          onClick={() => (open ? closeEdit() : openEdit(ev))}
                          className="flex min-w-0 flex-1 flex-col rounded-md px-1 text-left hover:bg-white/[0.04]"
                        >
                          <span
                            className={`block truncate font-semibold tracking-tight text-foreground/95 ${
                              compact && !open ? "text-[11px] leading-snug" : "text-[13px] leading-tight"
                            }`}
                          >
                            {ev.title}
                          </span>
                          <span
                            className={`mt-0.5 block truncate tabular-nums text-white/55 ${
                              compact && !open ? "text-[9px] leading-none" : "text-[10px] leading-tight"
                            }`}
                          >
                            {format(previewLabelStart, "h:mm a")}–{format(previewLabelEnd, "h:mm a")}
                            {!compact || open ? ` · ${formatHoursMins(mins)}` : ""}
                            {ev.isDraft
                              ? " · draft"
                              : ev.status === "in_progress"
                                ? " · live"
                                : ev.status === "done"
                                  ? " · done"
                                  : ""}
                          </span>
                        </button>
                        <div className="flex shrink-0 items-center gap-0.5 opacity-70 hover:opacity-100">
                          <button
                            type="button"
                            title="Edit"
                            onClick={() => (open ? closeEdit() : openEdit(ev))}
                            className="rounded p-0.5 text-white/50 hover:bg-white/10 hover:text-white"
                          >
                            <Pencil size={11} />
                          </button>
                          <div className="flex flex-col">
                            <button
                              type="button"
                              title={`Move earlier (${SNAP_MIN}m)`}
                              disabled={busy}
                              onClick={() => void moveItem(ev, -SNAP_MIN)}
                              className="rounded p-0.5 text-white/45 hover:bg-white/10 hover:text-white disabled:opacity-40"
                            >
                              <ChevronUp size={11} />
                            </button>
                            <button
                              type="button"
                              title={`Move later (${SNAP_MIN}m)`}
                              disabled={busy}
                              onClick={() => void moveItem(ev, SNAP_MIN)}
                              className="rounded p-0.5 text-white/45 hover:bg-white/10 hover:text-white disabled:opacity-40"
                            >
                              <ChevronDown size={11} />
                            </button>
                          </div>
                          <button
                            type="button"
                            title="Delete"
                            disabled={busy}
                            onClick={() => void deleteItem(ev)}
                            className="rounded p-0.5 text-white/45 hover:bg-red-500/20 hover:text-red-300 disabled:opacity-40"
                          >
                            <Trash2 size={11} />
                          </button>
                        </div>
                      </div>

                      {open && (
                        <div className="mt-1 space-y-2 border-t border-white/10 pt-2 px-1 pb-1">
                          {editError ? <p className="text-[11px] text-red-400">{editError}</p> : null}
                          <label className="block text-[11px] text-muted-foreground">
                            Title
                            <input
                              value={editTitle}
                              onChange={(e) => setEditTitle(e.target.value)}
                              className="mt-1 w-full rounded-lg border border-white/10 bg-background px-2 py-1.5 text-sm text-foreground"
                            />
                          </label>
                          <label className="block text-[11px] text-muted-foreground">
                            Category
                            <select
                              value={editCategory}
                              onChange={(e) => setEditCategory(e.target.value)}
                              className="mt-1 w-full rounded-lg border border-white/10 bg-background px-2 py-1.5 text-sm text-foreground"
                            >
                              {[editCategory, ...CATEGORIES.filter((c) => c !== editCategory)].map(
                                (c) => (
                                  <option key={c} value={c}>
                                    {c}
                                  </option>
                                ),
                              )}
                            </select>
                          </label>
                          <div className="grid grid-cols-2 gap-2">
                            <label className="block text-[11px] text-muted-foreground">
                              Start
                              <input
                                type="datetime-local"
                                value={editStart}
                                onChange={(e) => setEditStart(e.target.value)}
                                className="mt-1 w-full rounded-lg border border-white/10 bg-background px-2 py-1.5 text-sm text-foreground"
                              />
                            </label>
                            <label className="block text-[11px] text-muted-foreground">
                              End
                              <input
                                type="datetime-local"
                                value={editEnd}
                                onChange={(e) => setEditEnd(e.target.value)}
                                className="mt-1 w-full rounded-lg border border-white/10 bg-background px-2 py-1.5 text-sm text-foreground"
                              />
                            </label>
                          </div>
                          <div className="flex flex-wrap gap-2 pt-1">
                            <button
                              type="button"
                              disabled={busy}
                              onClick={() => void saveEdit(ev)}
                              className="rounded-lg bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
                            >
                              {busy ? "Saving…" : "Save"}
                            </button>
                            <button
                              type="button"
                              onClick={closeEdit}
                              className="rounded-lg border border-white/10 px-3 py-1.5 text-xs hover:bg-white/5"
                            >
                              Cancel
                            </button>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
