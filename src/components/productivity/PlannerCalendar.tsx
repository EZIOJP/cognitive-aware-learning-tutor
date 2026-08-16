import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import {
  Calendar as BigCalendar,
  dateFnsLocalizer,
  type EventProps,
  type SlotInfo,
  type View,
  Views,
} from "react-big-calendar";
import withDragAndDrop from "react-big-calendar/lib/addons/dragAndDrop";
import { format, getDay, parse, startOfWeek, endOfWeek, startOfDay, endOfDay, startOfMonth, endOfMonth } from "date-fns";
import { enUS } from "date-fns/locale";
import {
  blockColor,
  completePlannerBlock,
  createPlannerBlock,
  deletePlannerBlock,
  fetchActualOverlayFull,
  fetchPlannerBlocks,
  rollForwardPlannerBlock,
  startPlannerBlock,
  updatePlannerBlock,
  type ActualSession,
  type PlannerBlock,
  type ProposedPlannerBlock,
} from "../../api/plannerClient";
import {
  mergeForCalendar,
  stackActualByHour,
  mergedIntervalLabel,
  parseApiDate,
  actualStackTimeSpan,
  eventsOverlapForFocus,
  draftCoveredBySavedBlocks,
  intervalsInHour,
  intervalDisplayName,
  fmtDurationMinutes,
  type MergedInterval,
} from "./planVsActualUtils";
import type { HourSlice, SessionSegment } from "./hourSliceTypes";
import { planBlocksToHourSegs, type PlanHourSeg } from "./planHourSegments";
import { HourSliceProvider } from "./HourSliceProvider";
import { DayGridActualLayer } from "./DayGridActualLayer";
import { ActualStackEvent } from "./ActualStackEvent";
import { ActualFocusPanel, type EventAnchorRect } from "./ActualFocusPanel";
import { CalendarFocusContext } from "./calendarFocusContext";
import { Settings2 } from "lucide-react";
import { Popover, PopoverContent, PopoverTrigger } from "../../app/components/ui/popover";
import { PlannerBlockActions } from "./PlannerBlockActions";
import { PlannerBlockForm } from "./PlannerBlockForm";
import { PlanningDayAgenda } from "./PlanningDayAgenda";
import { PlannerCalendarToolbar } from "./PlannerCalendarToolbar";
import type { NavRange } from "./miniCalendarUtils";
import "react-big-calendar/lib/css/react-big-calendar.css";
import "react-big-calendar/lib/addons/dragAndDrop/styles.css";

const locales = { "en-US": enUS };
const localizer = dateFnsLocalizer({
  format,
  parse,
  startOfWeek,
  getDay,
  locales,
});

const DnDCalendar = withDragAndDrop(BigCalendar);

type HourStretch = "compact" | "normal" | "tall" | "xlo";

const HOUR_STRETCH_HEIGHT: Record<HourStretch, number> = {
  compact: 0.85,
  normal: 1,
  tall: 1.45,
  xlo: 1.9,
};

type CalendarEvent = {
  id: number;
  title: string;
  start: Date;
  end: Date;
  resource: PlannerBlock;
  isActual?: boolean;
  isStack?: boolean;
  isDraft?: boolean;
  actualStack?: import("./planVsActualUtils").MergedInterval[];
  stackTotalSeconds?: number;
};

export function calendarLayerVisibility({
  planned,
  actual,
  planningOnly,
}: {
  planned: boolean;
  actual: boolean;
  planningOnly: boolean;
}) {
  return {
    // The dedicated Planning agenda must always render its editable schedule.
    showPlanned: planningOnly || planned,
    showActual: !planningOnly && actual,
    // Planning-only loads wearable sleep; the calendar loads the overlay only on demand.
    loadOverlay: planningOnly || actual,
  };
}

function EventChip(props: EventProps<CalendarEvent>) {
  if (props.event.isActual) {
    return <ActualStackEvent {...props} />;
  }
  const status = props.event.resource.status;
  return (
    <div className="text-[11px] leading-tight px-0.5 overflow-hidden h-full flex flex-col justify-between gap-0.5">
      <div className="min-w-0">
        <div className="font-medium truncate">{props.event.title}</div>
        {props.event.isDraft ? (
          <div className="opacity-80">draft</div>
        ) : status === "in_progress" ? (
          <div className="opacity-80">in progress</div>
        ) : status === "done" ? (
          <div className="opacity-80 text-emerald-200/90">done</div>
        ) : null}
      </div>
      {!props.event.isDraft && status !== "done" && status !== "rolled" ? (
        <div className="text-[9px] font-semibold uppercase tracking-wide text-emerald-200/90 truncate">
          Tap · mark done
        </div>
      ) : null}
    </div>
  );
}

function eventTitle(block: PlannerBlock): string {
  if (block.status === "done") return `${block.title} (done)`;
  if (block.status === "rolled") return `${block.title} (rolled)`;
  return `${block.title} (${block.remaining_minutes}m left)`;
}

/** Parse RBC gutter labels like "7:00 AM" / "19:00" into a Date on `day`. */
function hourFromGutterLabel(label: string, day: Date): Date | null {
  const raw = label.replace(/\u202f/g, " ").trim();
  const m = raw.match(/^(\d{1,2})(?::(\d{2}))?\s*(AM|PM)?$/i);
  if (!m) return null;
  let hour = Number(m[1]);
  const minute = Number(m[2] || 0);
  const ap = (m[3] || "").toUpperCase();
  if (ap === "PM" && hour < 12) hour += 12;
  if (ap === "AM" && hour === 12) hour = 0;
  if (!ap && hour === 24) hour = 0;
  if (hour < 0 || hour > 23 || minute < 0 || minute > 59) return null;
  const out = startOfDay(day);
  out.setHours(hour, minute, 0, 0);
  return out;
}

function emptyActualResource(
  title: string,
  start: string,
  end: string,
  category = "actual",
): PlannerBlock {
  return {
    id: -1,
    title,
    category,
    start_at: start,
    end_at: end,
    planned_minutes: 0,
    remaining_minutes: 0,
    status: "done",
    rolled_from_id: null,
    roll_count: 0,
    task_id: null,
    color: null,
    created_at: null,
  };
}

/** Title for hourPeek panel: activity identity + duration, not the hour slot label. */
function hourPeekTitle(
  items: MergedInterval[],
  hourStart: Date,
  explicitTitle?: string,
): string {
  const names = [...new Set(items.map((i) => intervalDisplayName(i)))];
  // Pure hour / overflow with multiple apps — hour label is meaningful
  if (names.length > 1) {
    return (
      explicitTitle ??
      `${format(hourStart, "h a")} · ${items.length ? "what you did" : "nothing tracked"}`
    );
  }
  if (items.length === 1) return mergedIntervalLabel(items[0]);
  if (items.length > 1 && names.length === 1) {
    const totalSec = items.reduce((n, i) => n + i.duration_seconds, 0);
    return `${names[0]} · ${fmtDurationMinutes(Math.round(totalSec / 60))}`;
  }
  return (
    explicitTitle ??
    `${format(hourStart, "h a")} · ${items.length ? "what you did" : "nothing tracked"}`
  );
}

function hourPeekSpan(
  items: MergedInterval[],
  hourStart: Date,
  segment?: Pick<SessionSegment, "start_min" | "end_min"> | null,
): { start: Date; end: Date } {
  // Prefer real session/merge times so header matches body rows + total
  if (items.length > 0) return actualStackTimeSpan(items);
  // 2D segment click with unresolved items: use painted segment bounds
  if (segment) {
    return {
      start: new Date(hourStart.getTime() + segment.start_min * 60_000),
      end: new Date(hourStart.getTime() + Math.max(segment.start_min + 1, segment.end_min) * 60_000),
    };
  }
  const end = new Date(hourStart);
  end.setHours(end.getHours() + 1);
  return { start: hourStart, end };
}

type HourPeekEntry = {
  items: MergedInterval[];
  title?: string;
  segment?: Pick<SessionSegment, "start_min" | "end_min" | "app_or_label" | "category"> | null;
};

type HourPeekState = {
  hourStart: Date;
  items: MergedInterval[];
  title?: string;
  segment?: Pick<SessionSegment, "start_min" | "end_min" | "app_or_label" | "category"> | null;
  /** Overlapping 2D chips (incl. overflow-hidden) — ← → cycles these */
  cycleGroup: HourPeekEntry[];
  cycleIndex: number;
};

function segsMinuteOverlap(
  a: Pick<SessionSegment, "start_min" | "end_min">,
  b: Pick<SessionSegment, "start_min" | "end_min">,
): boolean {
  return a.start_min < b.end_min && b.start_min < a.end_min;
}

function resolveSegmentPeekItems(
  mergedActuals: MergedInterval[],
  sessionIds: string[],
  hourStart: Date,
  segment?: Pick<SessionSegment, "start_min" | "end_min" | "app_or_label" | "category"> | null,
): MergedInterval[] {
  const idSet = new Set(sessionIds.map(String).filter(Boolean));
  const matched = mergedActuals.filter(
    (m) =>
      idSet.size > 0 &&
      ((m.session_id && idSet.has(String(m.session_id))) ||
        m.children.some((c) => c.session_id && idSet.has(String(c.session_id)))),
  );
  // Never fall back to "everything in this hour" — that mixes apps (e.g. Cursor + Netflix).
  let items = matched;
  if (items.length === 0 && segment) {
    const label = (segment.app_or_label || "").toLowerCase();
    items = intervalsInHour(mergedActuals, hourStart).filter(
      (m) => intervalDisplayName(m).toLowerCase() === label || (m.app_name || "").toLowerCase().includes(label),
    );
  }
  if (items.length === 0 && segment) {
    const start = new Date(hourStart.getTime() + segment.start_min * 60_000);
    const end = new Date(hourStart.getTime() + Math.max(segment.start_min + 1, segment.end_min) * 60_000);
    items = [
      {
        session_id: sessionIds[0] ?? null,
        start_time: start.toISOString(),
        end_time: end.toISOString(),
        app_name: segment.app_or_label,
        category: segment.category,
        window_title: null,
        site: null,
        productivity_score: null,
        duration_seconds: Math.round((end.getTime() - start.getTime()) / 1000),
        merged_count: Math.max(1, sessionIds.length),
        children: [],
      },
    ];
  }
  return items;
}

function segmentCycleKey(seg: {
  session_group_id?: string;
  start_min: number;
  end_min: number;
  app_or_label: string;
}): string {
  return `${seg.session_group_id ?? ""}:${seg.start_min}:${seg.end_min}:${seg.app_or_label}`;
}

/** All hour chips that overlap the clicked one (shown + overflow-hidden). */
function buildSegmentCycleGroup(
  hourSlices: HourSlice[],
  hourStart: Date,
  mergedActuals: MergedInterval[],
  focus: SessionSegment | null,
  fallbackSessionIds: string[],
): { group: HourPeekEntry[]; index: number } {
  const hour = hourStart.getHours();
  const dayKey = format(hourStart, "yyyy-MM-dd");
  const slice =
    hourSlices.find((s) => s.hour === hour && s.date === dayKey) ??
    hourSlices.find((s) => s.hour === hour);
  const segs = slice?.segments ?? [];

  let candidates: SessionSegment[];
  if (focus) {
    candidates = segs.filter((s) => segsMinuteOverlap(s, focus));
    if (candidates.length === 0) candidates = [focus];
  } else {
    candidates = segs;
  }

  const group: HourPeekEntry[] = candidates
    .slice()
    .sort(
      (a, b) =>
        a.start_min - b.start_min ||
        b.duration_min - a.duration_min ||
        a.app_or_label.localeCompare(b.app_or_label),
    )
    .map((seg) => ({
      items: resolveSegmentPeekItems(mergedActuals, seg.session_ids, hourStart, seg),
      segment: seg,
    }));

  if (group.length === 0) {
    const items = resolveSegmentPeekItems(mergedActuals, fallbackSessionIds, hourStart, focus);
    return { group: [{ items, segment: focus }], index: 0 };
  }

  let index = 0;
  if (focus) {
    const key = segmentCycleKey(focus);
    const found = group.findIndex((e) => (e.segment ? segmentCycleKey(e.segment) === key : false));
    index = found >= 0 ? found : 0;
  }
  return { group, index };
}

type Props = {
  selectedDay?: Date;
  onSelectedDayChange?: (day: Date) => void;
  refreshKey?: number;
  /** Taller layout + month view for dedicated Calendar tab */
  expanded?: boolean;
  /** Controlled calendar view (day / week / month) */
  view?: View;
  onViewChange?: (view: View) => void;
  /** Unsaved propose-plan blocks shown as draft overlays */
  draftBlocks?: ProposedPlannerBlock[] | null;
  /** Plan tab: edit draft blocks in the day agenda */
  onDraftBlocksChange?: (blocks: ProposedPlannerBlock[]) => void;
  /**
   * Plan-tab mode: editable schedule only — no tracked “actual” overlays or toggle.
   * Use the Calendar tab for plan-vs-actual.
   */
  planningOnly?: boolean;
  /** Card title (e.g. “Planner calendar”) — sits in the same header band as nav */
  headerTitle?: ReactNode;
  /** Plan KPI badge(s) beside the title */
  headerBadge?: ReactNode;
};

export function PlannerCalendar({
  selectedDay,
  onSelectedDayChange,
  refreshKey = 0,
  expanded = false,
  view: viewProp,
  onViewChange,
  draftBlocks = null,
  onDraftBlocksChange,
  planningOnly = false,
  headerTitle,
  headerBadge,
}: Props) {
  const [viewInternal, setViewInternal] = useState<View>(Views.DAY);
  const view = viewProp ?? viewInternal;
  const setView = (next: View) => {
    if (viewProp === undefined) setViewInternal(next);
    onViewChange?.(next);
  };
  const [date, setDate] = useState(() => (selectedDay ? startOfDay(selectedDay) : new Date()));
  const [step, setStep] = useState(15);
  const [blocks, setBlocks] = useState<PlannerBlock[]>([]);
  const [actuals, setActuals] = useState<ActualSession[]>([]);
  const [hourSlices, setHourSlices] = useState<HourSlice[]>([]);
  const [showActual, setShowActual] = useState(!planningOnly);
  const [showPlanned, setShowPlanned] = useState(true);
  const [show2dTrack, setShow2dTrack] = useState(true);
  const [loading, setLoading] = useState(true);
  /** Plan tab: no desktop actuals, but still paint Amazfit sleep on the day grid. */
  const layerVisibility = calendarLayerVisibility({
    planned: showPlanned,
    actual: showActual,
    planningOnly,
  });
  const effectiveShowPlanned = layerVisibility.showPlanned;
  const effectiveShowActual = layerVisibility.showActual;
  const loadOverlay = layerVisibility.loadOverlay;
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<PlannerBlock | null>(null);
  const [slotStart, setSlotStart] = useState<Date | null>(null);
  const [focusedEventId, setFocusedEventId] = useState<number | null>(null);
  const [focusedStackItemIndex, setFocusedStackItemIndex] = useState(0);
  const [eventAnchor, setEventAnchor] = useState<EventAnchorRect | null>(null);
  const [hourPeek, setHourPeek] = useState<HourPeekState | null>(null);
  const [hourStretch, setHourStretch] = useState<HourStretch>("tall");
  /** Week-mode multi-week nav highlight (mini-cal / chip); RBC Week still shows 7 days from range start. */
  const [navRange, setNavRange] = useState<NavRange | null>(null);
  const calendarWrapRef = useRef<HTMLDivElement>(null);

  const calendarViews = useMemo(
    () => (expanded ? ([Views.MONTH, Views.WEEK, Views.DAY] as View[]) : ([Views.DAY, Views.WEEK] as View[])),
    [expanded],
  );

  /** External toolbar (above controls) — mirrors RBC Toolbar navigate actions. */
  const handleToolbarNavigate = useCallback(
    (action: "PREV" | "NEXT" | "TODAY" | "DATE", newDate?: Date) => {
      let next: Date;
      if (action === "TODAY") {
        next = new Date();
      } else if (action === "DATE") {
        next = newDate ?? date;
      } else if (action === "PREV") {
        next = localizer.add(date, -1, view);
      } else {
        next = localizer.add(date, 1, view);
      }
      setDate(next);
      onSelectedDayChange?.(startOfDay(next));
    },
    [date, view, onSelectedDayChange],
  );

  const range = useMemo(() => {
    if (planningOnly || view === Views.DAY) {
      return { from: startOfDay(date), to: endOfDay(date) };
    }
    if (view === Views.MONTH) {
      return {
        from: startOfWeek(startOfMonth(date), { weekStartsOn: 1 }),
        to: endOfWeek(endOfMonth(date), { weekStartsOn: 1 }),
      };
    }
    return { from: startOfWeek(date, { weekStartsOn: 1 }), to: endOfWeek(date, { weekStartsOn: 1 }) };
  }, [view, date, planningOnly]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [b, overlay] = await Promise.all([
        fetchPlannerBlocks(range.from, range.to),
        loadOverlay
          ? fetchActualOverlayFull(range.from, range.to)
          : Promise.resolve({ sessions: [] as ActualSession[], hour_slices: [] as HourSlice[] }),
      ]);
      setBlocks(b);
      const a = overlay.sessions;
      setHourSlices(overlay.hour_slices ?? []);
      if (!loadOverlay) {
        setActuals([]);
      } else if (effectiveShowActual) {
        setActuals(a);
      } else {
        // planningOnly: sleep only (PC left open overnight is not "work")
        setActuals(
          a.filter(
            (s) =>
              (s.category || "").toLowerCase() === "sleep" ||
              (s.source || "").toLowerCase() === "wearable_sleep" ||
              (s.app_name || "").toLowerCase() === "amazfit",
          ),
        );
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load planner");
    } finally {
      setLoading(false);
    }
  }, [range.from, range.to, effectiveShowActual, loadOverlay, refreshKey]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!selectedDay) return;
    setDate(selectedDay);
  }, [selectedDay?.toDateString()]);

  // Taller hours so 15/30/45m marks stay readable after collapsing the all-day header.
  const calendarHeight = Math.round((expanded ? 880 : 720) * HOUR_STRETCH_HEIGHT[hourStretch]);

  const events: CalendarEvent[] = useMemo(() => {
    const planned: CalendarEvent[] = effectiveShowPlanned
      ? blocks
          .filter((b) => b.status !== "rolled")
          .map((b) => ({
            id: b.id,
            title: eventTitle(b),
            start: parseApiDate(b.start_at),
            end: parseApiDate(b.end_at),
            resource: b,
          }))
      : [];

    const draftEvents: CalendarEvent[] = effectiveShowPlanned
      ? (draftBlocks ?? [])
          .filter((b) => b.source !== "existing")
          .filter((b) => !draftCoveredBySavedBlocks(b, blocks))
          .map((b, i) => {
            const start = parseApiDate(b.start_at);
            const end = parseApiDate(b.end_at);
            return {
              id: -5000 - i,
              title: b.title,
              start,
              end,
              isDraft: true,
              resource: emptyActualResource(b.title, b.start_at, b.end_at, b.category),
            };
          })
      : [];

    if (!effectiveShowActual && actuals.length === 0) {
      return [...planned, ...draftEvents];
    }

    // 2D track mode on Day view: hide RBC actuals (DayGridActualLayer paints instead)
    const use2d = effectiveShowActual && show2dTrack && view === Views.DAY;
    if (use2d) {
      return [...planned, ...draftEvents];
    }

    const merged = mergeForCalendar(actuals);
    const useStacks = view === Views.MONTH && effectiveShowActual; // week/day + sleep: real spans

    let actualEvents: CalendarEvent[];

    if (useStacks) {
      const stacks = stackActualByHour(merged);
      actualEvents = stacks.map((stack, i) => ({
        id: -2000 - i,
        title: `${stack.items.length} apps · ${Math.round(stack.totalSeconds / 60)}m`,
        start: stack.hourStart,
        end: stack.hourEnd,
        resource: emptyActualResource(
          "Tracked",
          stack.hourStart.toISOString(),
          stack.hourEnd.toISOString(),
        ),
        isActual: true,
        isStack: true,
        actualStack: stack.items,
        stackTotalSeconds: stack.totalSeconds,
      }));
    } else {
      actualEvents = merged.map((s, i) => ({
        id: -1000 - i,
        title: mergedIntervalLabel(s),
        start: parseApiDate(s.start_time),
        end: parseApiDate(s.end_time),
        resource: emptyActualResource(
          s.window_title ?? s.app_name ?? s.category ?? "Actual",
          s.start_time,
          s.end_time,
          s.category ?? "actual",
        ),
        isActual: true,
        isStack: false,
        actualStack: [s],
        stackTotalSeconds: s.duration_seconds,
      }));
    }

    return [...planned, ...draftEvents, ...actualEvents];
  }, [blocks, actuals, effectiveShowActual, effectiveShowPlanned, view, draftBlocks, show2dTrack]);

  const mergedActuals = useMemo(() => mergeForCalendar(actuals), [actuals]);

  const use2dLayer = !planningOnly && effectiveShowActual && show2dTrack && view === Views.DAY;

  const planHourSegs = useMemo(() => {
    if (!use2dLayer || !effectiveShowPlanned) return [];
    return planBlocksToHourSegs(blocks, date, draftBlocks);
  }, [use2dLayer, effectiveShowPlanned, blocks, date, draftBlocks]);

  const openSegmentPeek = useCallback(
    (
      sessionIds: string[],
      hourStart: Date,
      anchorEl: HTMLElement,
      opts?: {
        title?: string;
        segment?: SessionSegment | null;
        /** Overflow “+N”: cycle each hidden chip instead of one aggregate */
        cycleSegments?: SessionSegment[];
      },
    ) => {
      const wrap = calendarWrapRef.current;
      if (!wrap) return;
      const wrapR = wrap.getBoundingClientRect();
      const evR = anchorEl.getBoundingClientRect();

      let group: HourPeekEntry[];
      let index: number;
      if (opts?.cycleSegments && opts.cycleSegments.length > 0) {
        group = opts.cycleSegments
          .slice()
          .sort(
            (a, b) =>
              a.start_min - b.start_min ||
              b.duration_min - a.duration_min ||
              a.app_or_label.localeCompare(b.app_or_label),
          )
          .map((seg) => ({
            items: resolveSegmentPeekItems(mergedActuals, seg.session_ids, hourStart, seg),
            segment: seg,
          }));
        index = 0;
      } else {
        const built = buildSegmentCycleGroup(
          hourSlices,
          hourStart,
          mergedActuals,
          opts?.segment ?? null,
          sessionIds,
        );
        group = built.group;
        index = built.index;
      }

      const current = group[index] ?? {
        items: resolveSegmentPeekItems(mergedActuals, sessionIds, hourStart, opts?.segment),
        title: opts?.title,
        segment: opts?.segment ?? null,
      };

      setFocusedEventId(null);
      setSelected(null);
      setSlotStart(null);
      setEventAnchor({
        top: evR.top - wrapR.top + wrap.scrollTop,
        left: evR.left - wrapR.left + wrap.scrollLeft,
        width: Math.max(evR.width, 48),
        height: evR.height,
      });
      setHourPeek({
        hourStart,
        items: current.items,
        title: current.title ?? opts?.title,
        segment: current.segment ?? null,
        cycleGroup: group.length > 0 ? group : [current],
        cycleIndex: index,
      });
    },
    [mergedActuals, hourSlices],
  );

  const cycleHourPeek = useCallback((dir: -1 | 1) => {
    setHourPeek((prev) => {
      if (!prev || prev.cycleGroup.length < 2) return prev;
      const nextIdx = (prev.cycleIndex + dir + prev.cycleGroup.length) % prev.cycleGroup.length;
      const entry = prev.cycleGroup[nextIdx];
      if (!entry) return prev;
      return {
        ...prev,
        cycleIndex: nextIdx,
        items: entry.items,
        title: entry.title,
        segment: entry.segment ?? null,
      };
    });
  }, []);

  const focusedEvent = useMemo(
    () => (focusedEventId == null ? null : events.find((e) => e.id === focusedEventId) ?? null),
    [focusedEventId, events],
  );

  const focusOverlapGroup = useMemo(() => {
    if (!focusedEvent) return [];
    return events
      .filter((e) => eventsOverlapForFocus(e, focusedEvent))
      .sort((a, b) => a.start.getTime() - b.start.getTime() || a.id - b.id);
  }, [events, focusedEvent]);

  const cycleTotal = useMemo(() => {
    if (!focusedEvent) return 1;
    if (focusOverlapGroup.length >= 2) return focusOverlapGroup.length;
    const stackLen = focusedEvent.actualStack?.length ?? 0;
    return stackLen >= 2 ? stackLen : 1;
  }, [focusedEvent, focusOverlapGroup.length]);

  const cycleEventMode = focusOverlapGroup.length >= 2;
  const cycleStackMode = !cycleEventMode && (focusedEvent?.actualStack?.length ?? 0) >= 2;

  useEffect(() => {
    setFocusedStackItemIndex(0);
  }, [focusedEventId]);

  const cycleFocus = useCallback(
    (dir: -1 | 1) => {
      if (focusedEventId == null || cycleTotal < 2) return;

      if (cycleEventMode) {
        const idx = focusOverlapGroup.findIndex((e) => e.id === focusedEventId);
        if (idx < 0) return;
        const next = focusOverlapGroup[(idx + dir + focusOverlapGroup.length) % focusOverlapGroup.length];
        setFocusedEventId(next.id);
        setFocusedStackItemIndex(0);
        return;
      }

      const stackLen = focusedEvent?.actualStack?.length ?? 0;
      if (stackLen >= 2) {
        setFocusedStackItemIndex((i) => (i + dir + stackLen) % stackLen);
      }
    },
    [cycleEventMode, cycleTotal, focusOverlapGroup, focusedEvent, focusedEventId],
  );

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setFocusedEventId(null);
        setHourPeek(null);
        setEventAnchor(null);
        return;
      }
      if (hourPeek && hourPeek.cycleGroup.length >= 2) {
        if (e.key === "ArrowLeft") {
          e.preventDefault();
          cycleHourPeek(-1);
          return;
        }
        if (e.key === "ArrowRight") {
          e.preventDefault();
          cycleHourPeek(1);
          return;
        }
      }
      if (focusedEventId == null || cycleTotal < 2) return;
      if (e.key === "ArrowLeft") cycleFocus(-1);
      if (e.key === "ArrowRight") cycleFocus(1);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [cycleFocus, cycleHourPeek, focusedEventId, cycleTotal, hourPeek]);

  const measureFocusedAnchor = useCallback(() => {
    const wrap = calendarWrapRef.current;
    if (!wrap || focusedEventId == null) return;
    const el = wrap.querySelector(".rbc-event.calendar-event-focused") as HTMLElement | null;
    if (!el) return;
    const wrapR = wrap.getBoundingClientRect();
    const evR = el.getBoundingClientRect();
    setEventAnchor({
      top: evR.top - wrapR.top + wrap.scrollTop,
      left: evR.left - wrapR.left + wrap.scrollLeft,
      width: evR.width,
      height: evR.height,
    });
  }, [focusedEventId]);

  useEffect(() => {
    if (focusedEventId == null) {
      setEventAnchor(null);
      return;
    }
    measureFocusedAnchor();
    const t = window.setTimeout(measureFocusedAnchor, 50);
    window.addEventListener("resize", measureFocusedAnchor);
    const wrap = calendarWrapRef.current;
    wrap?.addEventListener("scroll", measureFocusedAnchor, true);
    return () => {
      window.clearTimeout(t);
      window.removeEventListener("resize", measureFocusedAnchor);
      wrap?.removeEventListener("scroll", measureFocusedAnchor, true);
    };
  }, [focusedEventId, measureFocusedAnchor, events, view, calendarHeight, focusedStackItemIndex]);

  const eventStyleGetter = useCallback(
    (event: CalendarEvent) => {
      const hasFocus = focusedEventId !== null;
      const isFocused = focusedEventId === event.id;
      const isDimmed = hasFocus && !isFocused;
      const focusClass = [isFocused && "calendar-event-focused", isDimmed && "calendar-event-dimmed"]
        .filter(Boolean)
        .join(" ");

      if (event.isActual) {
        const isSleep =
          event.resource?.category === "Sleep" ||
          event.resource?.category === "sleep" ||
          String(event.title || "").toLowerCase().startsWith("sleep");
        const base3d = isSleep
          ? isFocused
            ? {
                background:
                  "linear-gradient(165deg, rgba(99, 102, 241, 0.95) 0%, rgba(49, 46, 129, 0.98) 100%)",
                boxShadow:
                  "0 5px 0 rgba(30, 27, 75, 0.95), 0 10px 24px rgba(0, 0, 0, 0.45), inset 0 1px 0 rgba(199, 210, 254, 0.4)",
              }
            : {
                background:
                  "linear-gradient(165deg, rgba(99, 102, 241, 0.65) 0%, rgba(67, 56, 202, 0.75) 100%)",
                boxShadow:
                  "0 3px 0 rgba(49, 46, 129, 0.85), 0 6px 14px rgba(0, 0, 0, 0.28), inset 0 1px 0 rgba(165, 180, 252, 0.25)",
              }
          : isFocused
            ? {
                background:
                  "linear-gradient(165deg, rgba(56, 120, 210, 0.92) 0%, rgba(15, 40, 90, 0.95) 55%, rgba(10, 25, 55, 0.98) 100%)",
                boxShadow:
                  "0 5px 0 rgba(8, 20, 45, 0.95), 0 10px 24px rgba(0, 0, 0, 0.45), inset 0 1px 0 rgba(186, 230, 253, 0.45), inset 0 -2px 0 rgba(0, 0, 0, 0.2)",
              }
            : {
                background:
                  "linear-gradient(165deg, rgba(40, 90, 170, 0.55) 0%, rgba(20, 45, 95, 0.65) 100%)",
                boxShadow:
                  "0 3px 0 rgba(12, 30, 65, 0.85), 0 6px 14px rgba(0, 0, 0, 0.28), inset 0 1px 0 rgba(147, 197, 253, 0.2)",
              };
        return {
          className: [
            event.isStack ? "actual-stack-event" : "actual-single-event",
            "actual-event-3d",
            isSleep && "actual-sleep-event",
            focusClass,
          ]
            .filter(Boolean)
            .join(" "),
          style: {
            ...base3d,
            border: "none",
            color: "#e5e7eb",
            borderRadius: 10,
            padding: isFocused ? 4 : 2,
            overflow: "hidden",
          },
        };
      }
      if (event.isDraft) {
        const color = blockColor(event.resource.category, event.resource.color);
        return {
          className: ["planner-draft-event", focusClass].filter(Boolean).join(" "),
          style: {
            background: `linear-gradient(135deg, ${color}55, ${color}28)`,
            border: `1.5px dashed ${color}`,
            color: "#fff",
            opacity: isDimmed ? 0.2 : 0.92,
            borderRadius: 8,
          },
        };
      }
      const color = blockColor(event.resource.category, event.resource.color);
      const faded = event.resource.status === "done";
      return {
        className: ["planner-plan-event", focusClass].filter(Boolean).join(" "),
        style: {
          backgroundColor: faded ? `${color}66` : color,
          borderColor: color,
          color: "#fff",
          opacity: isDimmed ? 0.22 : event.resource.status === "cancelled" ? 0.4 : 1,
        },
      };
    },
    [focusedEventId],
  );

  const onEventDrop = async ({ event, start, end }: { event: CalendarEvent; start: Date; end: Date }) => {
    if (event.isActual || event.isDraft || event.id < 0) return;
    try {
      const mins = event.resource.remaining_minutes;
      await updatePlannerBlock(event.id, {
        start_at: start.toISOString(),
        duration_minutes: mins,
      });
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Reschedule failed");
    }
  };

  const captureAnchorFromClick = (nativeEvent: React.SyntheticEvent) => {
    const wrap = calendarWrapRef.current;
    const target = (nativeEvent.target as HTMLElement | null)?.closest?.(".rbc-event") as HTMLElement | null;
    if (!wrap || !target) return;
    const wrapR = wrap.getBoundingClientRect();
    const evR = target.getBoundingClientRect();
    setEventAnchor({
      top: evR.top - wrapR.top + wrap.scrollTop,
      left: evR.left - wrapR.left + wrap.scrollLeft,
      width: evR.width,
      height: evR.height,
    });
  };

  const onSelectEvent = (event: CalendarEvent, nativeEvent?: React.SyntheticEvent) => {
    onSelectedDayChange?.(startOfDay(event.start));
    setHourPeek(null);
    if (event.isActual) {
      if (focusedEventId === event.id) {
        setFocusedEventId(null);
        setEventAnchor(null);
      } else {
        if (nativeEvent) captureAnchorFromClick(nativeEvent);
        setFocusedEventId(event.id);
      }
      setSelected(null);
      setSlotStart(null);
      return;
    }
    if (nativeEvent) captureAnchorFromClick(nativeEvent);
    setFocusedEventId(event.id);
    setSelected(event.resource);
    setSlotStart(null);
  };

  const onSelectSlot = (slot: SlotInfo) => {
    onSelectedDayChange?.(startOfDay(slot.start));
    setHourPeek(null);
    setFocusedEventId(null);
    setEventAnchor(null);
    setSelected(null);
    setSlotStart(slot.start);
  };

  const openAddAt = (when: Date) => {
    const rounded = new Date(when);
    rounded.setSeconds(0, 0);
    const m = rounded.getMinutes();
    rounded.setMinutes(m - (m % 15));
    setSelected(null);
    setFocusedEventId(null);
    setEventAnchor(null);
    setSlotStart(rounded);
  };

  const openHourPeek = useCallback(
    (hourStart: Date, anchorEl: HTMLElement) => {
      const items = intervalsInHour(mergedActuals, hourStart);
      const wrap = calendarWrapRef.current;
      if (!wrap) return;
      const wrapR = wrap.getBoundingClientRect();
      const evR = anchorEl.getBoundingClientRect();
      // One entry per app/interval so ← → can reach chips buried under others.
      const cycleGroup: HourPeekEntry[] =
        items.length >= 2
          ? items.map((m) => ({ items: [m] }))
          : [{ items }];
      setFocusedEventId(null);
      setSelected(null);
      setSlotStart(null);
      setEventAnchor({
        top: evR.top - wrapR.top + wrap.scrollTop,
        left: evR.left - wrapR.left + wrap.scrollLeft,
        width: Math.max(evR.width, 48),
        height: evR.height,
      });
      setHourPeek({
        hourStart,
        items: cycleGroup[0]?.items ?? items,
        cycleGroup,
        cycleIndex: 0,
      });
    },
    [mergedActuals],
  );

  const isEmpty =
    !loading &&
    blocks.filter((b) => b.status !== "rolled").length === 0 &&
    (!effectiveShowActual || actuals.length === 0);

  if (planningOnly) {
    return (
      <div className="space-y-3">
        <PlanningDayAgenda
          day={date}
          blocks={blocks}
          draftBlocks={draftBlocks}
          loading={loading}
          error={error}
          onDayChange={(next) => {
            setDate(next);
            onSelectedDayChange?.(next);
          }}
          onAdd={openAddAt}
          onPlaceRoutine={async (at, routine) => {
            const start = new Date(at);
            start.setSeconds(0, 0);
            await createPlannerBlock({
              title: routine.title,
              category: routine.category,
              start_at: start.toISOString(),
              duration_minutes: routine.duration_minutes,
              color: routine.color || undefined,
            });
            await load();
          }}
          onUpdateSaved={async (id, patch) => {
            await updatePlannerBlock(id, patch);
            await load();
          }}
          onDeleteSaved={async (id) => {
            await deletePlannerBlock(id);
            setSelected(null);
            await load();
          }}
          onChangeDrafts={onDraftBlocksChange}
        />
        {slotStart && (
          <PlannerBlockForm
            defaultStart={slotStart}
            onCancel={() => setSlotStart(null)}
            onSubmit={async (data) => {
              await createPlannerBlock(data);
              setSlotStart(null);
              await load();
            }}
          />
        )}
      </div>
    );
  }

  return (
    <div className="planner-calendar-shell">
      <div className="planner-cal-header">
        <div className="planner-cal-header__brand">
          {headerTitle}
          {headerBadge}
          <div className="planner-cal-meta__controls">
            <Popover>
              <PopoverTrigger asChild>
                <button
                  type="button"
                  className="planner-cal-meta__display"
                  title={`Display · ${effectiveShowPlanned ? "planned" : "actual only"} · ${effectiveShowActual ? "actual" : "plan only"} · ${step}m`}
                >
                  <Settings2 size={11} />
                  Display
                </button>
              </PopoverTrigger>
              <PopoverContent align="start" className="w-64 space-y-3 bg-popover/95 backdrop-blur-sm">
                <div>
                  <p className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1.5">Layers</p>
                  <div className="flex flex-wrap gap-x-3 gap-y-2">
                    <label className="planner-cal-meta__check" title="Scheduled blocks and unsaved plan drafts.">
                      <input
                        type="checkbox"
                        checked={showPlanned}
                        onChange={(e) => setShowPlanned(e.target.checked)}
                      />
                      Show planned
                    </label>
                    <label
                      className="planner-cal-meta__check"
                      title="Blue blocks are tracked sessions. Click for details; ← → cycles overlaps."
                    >
                      <input
                        type="checkbox"
                        checked={showActual}
                        onChange={(e) => setShowActual(e.target.checked)}
                      />
                      Show actual
                    </label>
                    {view === Views.DAY && effectiveShowActual ? (
                      <label
                        className="planner-cal-meta__check"
                        title="Per-hour 2D lanes for tracked time (hides classic actual bars)."
                      >
                        <input
                          type="checkbox"
                          checked={show2dTrack}
                          onChange={(e) => setShow2dTrack(e.target.checked)}
                        />
                        2D track
                      </label>
                    ) : null}
                  </div>
                </div>
                <div>
                  <p className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1.5">Zoom</p>
                  <div className="flex gap-1.5">
                    {[15, 30, 60].map((s) => (
                      <button
                        key={s}
                        type="button"
                        onClick={() => setStep(s)}
                        className={`flex-1 px-2 py-1 rounded text-xs border ${
                          step === s
                            ? "border-primary/40 bg-primary/15 text-primary"
                            : "border-white/10 text-muted-foreground"
                        }`}
                      >
                        {s}m
                      </button>
                    ))}
                  </div>
                </div>
                <div>
                  <p className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1.5">Row height</p>
                  <div className="flex gap-1.5">
                    {(
                      [
                        ["compact", "S"],
                        ["normal", "M"],
                        ["tall", "L"],
                        ["xlo", "XL"],
                      ] as const
                    ).map(([key, label]) => (
                      <button
                        key={key}
                        type="button"
                        onClick={() => setHourStretch(key)}
                        className={`flex-1 px-2 py-1 rounded text-xs border ${
                          hourStretch === key
                            ? "border-primary/40 bg-primary/15 text-primary"
                            : "border-white/10 text-muted-foreground"
                        }`}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                </div>
                <p className="text-[10px] text-muted-foreground leading-relaxed">
                  2D track (Day): left→right = minutes 0–60 for plan blocks and tracked apps. Turn off
                  for classic full-width drag/drop.
                </p>
              </PopoverContent>
            </Popover>
          </div>
          {loading && <span className="planner-cal-meta__loading">Loading…</span>}
        </div>
        <div className="planner-cal-header__nav">
          <PlannerCalendarToolbar
            date={date}
            view={view}
            views={calendarViews}
            label=""
            onNavigate={handleToolbarNavigate}
            onView={setView}
            navRange={navRange}
            onNavRangeChange={setNavRange}
          />
        </div>
      </div>

      {error && <p className="text-xs text-red-400">{error}</p>}

      <div
        ref={calendarWrapRef}
        className={`planner-calendar-wrap planner-calendar-wrap--no-allday relative overflow-hidden rounded-xl border border-white/10 bg-black/20 p-2 ${
          focusedEventId != null || hourPeek ? "planner-calendar--focus-mode" : ""
        } ${expanded ? "min-h-[880px]" : "min-h-[720px]"}`}
        data-hour-stretch={hourStretch}
        data-calendar-view={view}
        data-2d-track={use2dLayer ? "1" : "0"}
        onClickCapture={(e) => {
          const t = e.target as HTMLElement;
          const gutter = t.closest(".rbc-time-gutter") as HTMLElement | null;
          if (gutter) {
            const labelEl =
              (t.closest(".rbc-label") as HTMLElement | null) ||
              (t.closest(".rbc-timeslot-group")?.querySelector(".rbc-label") as HTMLElement | null);
            const labelText = (labelEl?.textContent || "").trim();
            if (labelText) {
              const hourStart = hourFromGutterLabel(labelText, date);
              if (hourStart) {
                e.preventDefault();
                e.stopPropagation();
                openHourPeek(hourStart, labelEl || gutter);
                return;
              }
            }
          }
          if (focusedEventId == null && !hourPeek && !selected && !slotStart) return;
          if (
            t.closest(".rbc-event.calendar-event-focused") ||
            t.closest('[role="dialog"]')
          ) {
            return;
          }
          setFocusedEventId(null);
          setHourPeek(null);
          setEventAnchor(null);
          setSelected(null);
          setSlotStart(null);
        }}
      >
        {isEmpty && (
          <div className="pointer-events-none absolute inset-x-0 top-4 z-10 flex justify-center px-4">
            <p className="rounded-lg border border-white/10 bg-black/70 px-3 py-2 text-center text-xs text-muted-foreground shadow-lg backdrop-blur-sm">
              No blocks this view — click a time slot to plan, or open Import & routines for timetable / propose week.
            </p>
          </div>
        )}
        <CalendarFocusContext.Provider value={{ focusedId: focusedEventId }}>
          <HourSliceProvider
            slices={hourSlices}
            dayKey={format(date, "yyyy-MM-dd")}
            enabled={use2dLayer}
          >
            <DnDCalendar
              localizer={localizer}
              events={events}
              view={view}
              onView={(next) => setView(next)}
              date={date}
              onNavigate={(newDate, nextView) => {
                setDate(newDate);
                onSelectedDayChange?.(startOfDay(newDate));
                if (nextView === Views.DAY || nextView === Views.WEEK || nextView === Views.MONTH) {
                  setView(nextView);
                }
              }}
              step={step}
              timeslots={Math.max(1, 60 / step)}
              /* App never uses all-day events; RBC still reserves minRows=2 — hide via CSS + prop. */
              allDayMaxRows={0}
              allDayAccessor={() => false}
              showMultiDayTimes
              selectable
              resizable={false}
              toolbar={false}
              draggableAccessor={(e: CalendarEvent) =>
                !use2dLayer && !e.isActual && focusedEventId == null
              }
              onEventDrop={onEventDrop as never}
              onSelectEvent={onSelectEvent as never}
              onSelectSlot={onSelectSlot}
              eventPropGetter={eventStyleGetter as never}
              components={{
                event: EventChip as never,
              }}
              views={calendarViews}
              defaultView={Views.DAY}
              style={{ height: calendarHeight, width: "100%" }}
            />
            {use2dLayer ? (
              <DayGridActualLayer
                day={date}
                slices={effectiveShowActual ? hourSlices : []}
                planSegs={planHourSegs}
                focusedPlanId={focusedEventId}
                containerRef={calendarWrapRef}
                onSegmentClick={(seg: SessionSegment, hourStart, el) => {
                  openSegmentPeek(seg.session_ids, hourStart, el, { segment: seg });
                }}
                onOverflowClick={(hidden, hourStart, el) => {
                  const ids = hidden.flatMap((s) => s.session_ids);
                  openSegmentPeek(ids, hourStart, el, {
                    title: `+${hidden.length} more · ${format(hourStart, "h a")}`,
                    cycleSegments: hidden,
                  });
                }}
                onPlanSegClick={(seg: PlanHourSeg, el) => {
                  const wrap = calendarWrapRef.current;
                  if (wrap) {
                    const wrapR = wrap.getBoundingClientRect();
                    const evR = el.getBoundingClientRect();
                    setEventAnchor({
                      top: evR.top - wrapR.top + wrap.scrollTop,
                      left: evR.left - wrapR.left + wrap.scrollLeft,
                      width: evR.width,
                      height: evR.height,
                    });
                  }
                  setHourPeek(null);
                  const block = blocks.find((b) => b.id === seg.blockId);
                  if (block) {
                    setSelected(block);
                    setFocusedEventId(block.id);
                    onSelectedDayChange?.(startOfDay(new Date(block.start_at)));
                  } else if (seg.isDraft) {
                    setFocusedEventId(seg.blockId);
                    setSelected(null);
                  }
                }}
              />
            ) : null}
          </HourSliceProvider>
        </CalendarFocusContext.Provider>

        {hourPeek && eventAnchor && (() => {
          const span = hourPeekSpan(hourPeek.items, hourPeek.hourStart, hourPeek.segment);
          const peekCycleTotal = hourPeek.cycleGroup.length;
          return (
            <ActualFocusPanel
              popup
              anchor={eventAnchor}
              containerWidth={calendarWrapRef.current?.clientWidth ?? 400}
              containerHeight={calendarWrapRef.current?.clientHeight ?? calendarHeight}
              title={hourPeekTitle(hourPeek.items, hourPeek.hourStart, hourPeek.title)}
              start={span.start}
              end={span.end}
              items={hourPeek.items}
              totalSeconds={hourPeek.items.reduce((n, i) => n + i.duration_seconds, 0)}
              cycleIndex={hourPeek.cycleIndex}
              cycleTotal={peekCycleTotal}
              cycleLabel="overlapped"
              onCyclePrev={() => cycleHourPeek(-1)}
              onCycleNext={() => cycleHourPeek(1)}
              onClose={() => {
                setHourPeek(null);
                setEventAnchor(null);
              }}
            />
          );
        })()}

        {focusedEvent && eventAnchor && !hourPeek && focusedEvent.isActual && (() => {
          const stack = focusedEvent.actualStack ?? [];
          const cycleIdx = cycleEventMode
            ? focusOverlapGroup.findIndex((e) => e.id === focusedEvent.id)
            : focusedStackItemIndex;
          const panelItems = cycleStackMode ? [stack[focusedStackItemIndex]].filter(Boolean) : stack;
          const panelItem = cycleStackMode ? stack[focusedStackItemIndex] : undefined;
          const span = focusedEvent.isActual && panelItem
            ? { start: parseApiDate(panelItem.start_time), end: parseApiDate(panelItem.end_time) }
            : focusedEvent.isActual && stack.length
              ? actualStackTimeSpan(stack)
              : { start: focusedEvent.start, end: focusedEvent.end };
          const wrap = calendarWrapRef.current;

          return (
            <ActualFocusPanel
              popup
              anchor={eventAnchor}
              containerWidth={wrap?.clientWidth ?? 400}
              containerHeight={wrap?.clientHeight ?? calendarHeight}
              title={
                cycleStackMode && panelItem
                  ? mergedIntervalLabel(panelItem)
                  : focusedEvent.title
              }
              start={span.start}
              end={span.end}
              items={panelItems}
              totalSeconds={
                cycleStackMode && panelItem
                  ? panelItem.duration_seconds
                  : focusedEvent.stackTotalSeconds ?? 0
              }
              plannedBlock={
                focusedEvent.isActual
                  ? undefined
                  : {
                      title: focusedEvent.resource.title,
                      category: focusedEvent.resource.category,
                      minutes: focusedEvent.resource.planned_minutes,
                    }
              }
              cycleIndex={cycleIdx >= 0 ? cycleIdx : 0}
              cycleTotal={cycleTotal}
              cycleLabel={cycleStackMode ? "in hour" : "overlapped"}
              onCyclePrev={() => cycleFocus(-1)}
              onCycleNext={() => cycleFocus(1)}
              onClose={() => {
                setFocusedEventId(null);
                setEventAnchor(null);
              }}
            />
          );
        })()}

        {slotStart && (
          <div
            role="dialog"
            aria-label="Add planned block"
            className="planner-cal-float planner-cal-float--center"
          >
            <PlannerBlockForm
              defaultStart={slotStart}
              onCancel={() => setSlotStart(null)}
              onSubmit={async (data) => {
                await createPlannerBlock(data);
                setSlotStart(null);
                await load();
              }}
            />
          </div>
        )}

        {selected && !slotStart && (
          <div
            role="dialog"
            aria-label="Planned block actions"
            className={
              eventAnchor
                ? "planner-cal-float"
                : "planner-cal-float planner-cal-float--center"
            }
            style={
              eventAnchor
                ? (() => {
                    const wrap = calendarWrapRef.current;
                    const cw = wrap?.clientWidth ?? 400;
                    const ch = wrap?.clientHeight ?? calendarHeight;
                    const CARD_W = 320;
                    const CARD_H = 280;
                    const gap = 10;
                    let left = eventAnchor.left + eventAnchor.width + gap;
                    let top = eventAnchor.top;
                    if (left + CARD_W > cw - 8) left = Math.max(8, eventAnchor.left - CARD_W - gap);
                    top = Math.max(8, Math.min(ch - CARD_H - 8, top));
                    return { top, left, width: CARD_W };
                  })()
                : undefined
            }
          >
            <PlannerBlockActions
              block={selected}
              onClose={() => {
                setSelected(null);
                setFocusedEventId(null);
                setEventAnchor(null);
              }}
              onStart={async () => {
                const b = await startPlannerBlock(selected.id);
                setSelected(b);
                await load();
              }}
              onComplete={async (minutes) => {
                const b = await completePlannerBlock(selected.id, minutes);
                if (b.status === "done") {
                  setSelected(null);
                  setFocusedEventId(null);
                  setEventAnchor(null);
                } else {
                  setSelected(b);
                }
                await load();
              }}
              onRollForward={async () => {
                await rollForwardPlannerBlock(selected.id);
                setSelected(null);
                setFocusedEventId(null);
                setEventAnchor(null);
                await load();
              }}
              onDelete={async () => {
                await deletePlannerBlock(selected.id);
                setSelected(null);
                setFocusedEventId(null);
                setEventAnchor(null);
                await load();
              }}
            />
          </div>
        )}
      </div>
    </div>
  );
}
