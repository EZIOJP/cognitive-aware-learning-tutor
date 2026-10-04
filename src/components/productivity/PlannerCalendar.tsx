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
import { buildHourSlicesFromSessions } from "./buildHourSlices";
import { DayGridCreateLayer } from "./DayGridCreateLayer";
import { PlannerDayTrack } from "./PlannerDayTrack";
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
  compact: 0.75,
  normal: 1,
  tall: 1.35,
  xlo: 1.75,
};

const HOUR_STRETCH_OPTIONS: { key: HourStretch; label: string; hint: string }[] = [
  { key: "compact", label: "S", hint: "Compact" },
  { key: "normal", label: "M", hint: "Default" },
  { key: "tall", label: "L", hint: "Comfortable" },
  { key: "xlo", label: "XL", hint: "Spacious" },
];

const DISPLAY_PREFS_KEY = "calt.planner.display.v2";

function loadDisplayPrefs(planningOnly: boolean): {
  showPlanned: boolean;
  showActual: boolean;
  hourStretch: HourStretch;
} {
  const fallback = {
    showPlanned: true,
    showActual: true,
    hourStretch: "tall" as HourStretch,
  };
  try {
    const raw = localStorage.getItem(DISPLAY_PREFS_KEY);
    if (!raw) return fallback;
    const p = JSON.parse(raw) as Partial<typeof fallback>;
    const stretch = HOUR_STRETCH_OPTIONS.some((o) => o.key === p.hourStretch)
      ? (p.hourStretch as HourStretch)
      : fallback.hourStretch;
    return {
      showPlanned: typeof p.showPlanned === "boolean" ? p.showPlanned : true,
      showActual: typeof p.showActual === "boolean" ? p.showActual : true,
      hourStretch: stretch,
    };
  } catch {
    return fallback;
  }
}

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
    // Tracked chips on Plan + Calendar when the Display toggle is on.
    showActual: actual,
    loadOverlay: true,
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
  return `${block.title} (${fmtDurationMinutes(block.remaining_minutes)} left)`;
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
  /** Optional leading chrome (usually omit — tab already says Calendar). */
  headerTitle?: ReactNode;
  /** Compact KPI beside Display (e.g. on-plan hours). */
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
  /** Slot snap for week/month RBC + click-to-add rounding (day create uses 1m). */
  const step = 15;
  const [blocks, setBlocks] = useState<PlannerBlock[]>([]);
  const [actuals, setActuals] = useState<ActualSession[]>([]);
  const [hourSlices, setHourSlices] = useState<HourSlice[]>([]);
  const initialDisplay = useMemo(() => loadDisplayPrefs(planningOnly), [planningOnly]);
  const [showActual, setShowActual] = useState(initialDisplay.showActual);
  const [showPlanned, setShowPlanned] = useState(initialDisplay.showPlanned);
  const show2dTrack = true;
  const [loading, setLoading] = useState(true);
  /** Plan tab: 2D minute grid (default) vs lane-based timeline editor */
  const [planAgendaEdit, setPlanAgendaEdit] = useState(false);
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
  const [slotDuration, setSlotDuration] = useState(60);
  const [focusedEventId, setFocusedEventId] = useState<number | null>(null);
  const [focusedStackItemIndex, setFocusedStackItemIndex] = useState(0);
  const [eventAnchor, setEventAnchor] = useState<EventAnchorRect | null>(null);
  const [hourPeek, setHourPeek] = useState<HourPeekState | null>(null);
  const [hourStretch, setHourStretch] = useState<HourStretch>(initialDisplay.hourStretch);
  /** Week-mode multi-week nav highlight (mini-cal / chip); RBC Week still shows 7 days from range start. */
  const [navRange, setNavRange] = useState<NavRange | null>(null);
  const calendarWrapRef = useRef<HTMLDivElement>(null);
  const dayTrackBodyRef = useRef<HTMLDivElement>(null);
  const hasPaintedRef = useRef(false);

  useEffect(() => {
    try {
      localStorage.setItem(
        DISPLAY_PREFS_KEY,
        JSON.stringify({ showPlanned, showActual, hourStretch }),
      );
    } catch {
      /* ignore quota / private mode */
    }
  }, [showPlanned, showActual, hourStretch]);

  const togglePlanned = useCallback(() => {
    setShowPlanned((on) => {
      // Keep at least one layer visible on the calendar tab
      if (on && !planningOnly && !showActual) return true;
      return !on;
    });
  }, [planningOnly, showActual]);

  const toggleActual = useCallback(() => {
    setShowActual((on) => {
      if (on && !showPlanned) return true;
      return !on;
    });
  }, [showPlanned]);

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
    // Stale-while-revalidate: only gate first paint — tab re-entry must not flash Loading.
    if (!hasPaintedRef.current) setLoading(true);
    setError(null);
    try {
      const b = await fetchPlannerBlocks(range.from, range.to);
      setBlocks(b);
      hasPaintedRef.current = true;
      setLoading(false);

      if (!loadOverlay || !effectiveShowActual) {
        setActuals([]);
        setHourSlices([]);
        return;
      }
      // Overlay second so the calendar grid paints before tracked chips.
      // Focus/C++ returns hour_slices: [] — build them client-side from sessions.
      const overlay = await fetchActualOverlayFull(range.from, range.to);
      const a = overlay.sessions ?? [];
      let slices = overlay.hour_slices ?? [];
      if (a.length && !slices.length) {
        slices = buildHourSlicesFromSessions(a, date);
      }
      setHourSlices(slices);
      setActuals(a);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load planner");
      setLoading(false);
    }
  }, [range.from, range.to, effectiveShowActual, loadOverlay, refreshKey, date]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!selectedDay) return;
    setDate(selectedDay);
  }, [selectedDay?.toDateString()]);

  // Taller hours so 15/30/45m marks stay readable after collapsing the all-day header.
  const calendarHeight = Math.round((expanded ? 880 : 720) * HOUR_STRETCH_HEIGHT[hourStretch]);

  // 2D minute track whenever Day view + toggle is on (planned and/or actual).
  // Create/drag uses X=minutes, Y=hours — must not depend on actual overlay alone.
  const use2dLayer = show2dTrack && view === Views.DAY;

  // Minute bar uses CSS grid (--planner-hour-col) to clear the hour gutter;
  // no JS lane measurement needed for the header axis.

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

    // Plan-tab 2D track: DayGridActualLayer paints plan blocks minute-positioned
    if (use2dLayer && planningOnly) {
      return [];
    }

    if (!effectiveShowActual && actuals.length === 0) {
      return [...planned, ...draftEvents];
    }

    // 2D track mode on Day view: hide RBC actuals (DayGridActualLayer paints instead)
    const use2dActual = use2dLayer && !planningOnly;
    if (use2dActual) {
      return [...planned, ...draftEvents];
    }

    const merged = mergeForCalendar(actuals);
    const useStacks = view === Views.MONTH && effectiveShowActual; // week/day + sleep: real spans

    let actualEvents: CalendarEvent[];

    if (useStacks) {
      const stacks = stackActualByHour(merged);
      actualEvents = stacks.map((stack, i) => ({
        id: -2000 - i,
        title: `${stack.items.length} apps · ${fmtDurationMinutes(Math.round(stack.totalSeconds / 60))}`,
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
  }, [blocks, actuals, effectiveShowActual, effectiveShowPlanned, view, draftBlocks, use2dLayer, planningOnly]);

  const mergedActuals = useMemo(() => mergeForCalendar(actuals), [actuals]);

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
    // Classic vertical select only when 2D minute track is off.
    if (use2dLayer) return;
    onSelectedDayChange?.(startOfDay(slot.start));
    setHourPeek(null);
    setFocusedEventId(null);
    setEventAnchor(null);
    setSelected(null);
    setSlotDuration(Math.max(step, 60));
    setSlotStart(slot.start);
  };

  const onHorizontalCreate = useCallback(
    ({ start, durationMinutes }: { start: Date; durationMinutes: number }) => {
      onSelectedDayChange?.(startOfDay(start));
      setHourPeek(null);
      setFocusedEventId(null);
      setEventAnchor(null);
      setSelected(null);
      setSlotDuration(Math.max(step, durationMinutes));
      setSlotStart(start);
    },
    [onSelectedDayChange, step],
  );

  const openAddAt = (when: Date) => {
    const rounded = new Date(when);
    rounded.setSeconds(0, 0);
    const m = rounded.getMinutes();
    rounded.setMinutes(m - (m % step));
    setSelected(null);
    setFocusedEventId(null);
    setEventAnchor(null);
    setSlotDuration(Math.max(step, 60));
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

  if (planningOnly && planAgendaEdit) {
    return (
      <div className="space-y-3">
        <div className="flex flex-wrap items-center justify-end gap-1.5 px-0.5">
          <button
            type="button"
            onClick={() => setPlanAgendaEdit(false)}
            className="rounded-lg border border-white/10 px-2.5 py-1 text-[11px] text-muted-foreground hover:bg-white/5"
          >
            2D view
          </button>
          <button
            type="button"
            className="rounded-lg border border-primary/40 bg-primary/15 px-2.5 py-1 text-[11px] text-primary"
          >
            Timeline edit
          </button>
        </div>
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
            defaultDuration={slotDuration}
            onCancel={() => {
              setSlotStart(null);
              setSlotDuration(60);
            }}
            onSubmit={async (data) => {
              await createPlannerBlock(data);
              setSlotStart(null);
              setSlotDuration(60);
              await load();
            }}
          />
        )}
      </div>
    );
  }

  return (
    <div className="planner-calendar-shell">
      {planningOnly ? (
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2 px-0.5">
          <p className="text-[10px] text-muted-foreground">
            Drag across minutes; move into the next/previous hour to extend · 1m while creating · click a block to edit
          </p>
          <div className="flex gap-1.5">
            <button
              type="button"
              onClick={() => setPlanAgendaEdit(false)}
              className={`rounded-lg border px-2.5 py-1 text-[11px] ${
                !planAgendaEdit
                  ? "border-primary/40 bg-primary/15 text-primary"
                  : "border-white/10 text-muted-foreground hover:bg-white/5"
              }`}
            >
              2D view
            </button>
            <button
              type="button"
              onClick={() => setPlanAgendaEdit(true)}
              className={`rounded-lg border px-2.5 py-1 text-[11px] ${
                planAgendaEdit
                  ? "border-primary/40 bg-primary/15 text-primary"
                  : "border-white/10 text-muted-foreground hover:bg-white/5"
              }`}
            >
              Timeline edit
            </button>
          </div>
        </div>
      ) : null}
      <div className="planner-cal-header">
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
        <div className="planner-cal-header__brand">
          {headerTitle}
          {headerBadge}
          <div className="planner-cal-meta__controls">
            <Popover>
              <PopoverTrigger asChild>
                <button
                  type="button"
                  className="planner-cal-meta__display"
                  aria-label="Display options"
                  title={`Display · ${effectiveShowPlanned ? "planned" : "actual only"} · ${effectiveShowActual ? "actual" : "plan only"}`}
                >
                  <Settings2 size={12} aria-hidden />
                  <span className="planner-cal-meta__display-label">Display</span>
                </button>
              </PopoverTrigger>
              <PopoverContent align="end" className="planner-cal-display-pop w-56 space-y-3 bg-popover/95 backdrop-blur-sm">
                {!planningOnly ? (
                  <div>
                    <p className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1.5">Layers</p>
                    <div className="planner-cal-display-pop__toggles" role="group" aria-label="Visible layers">
                      <button
                        type="button"
                        className={`planner-cal-display-pop__toggle ${showPlanned ? "is-on" : ""}`}
                        aria-pressed={showPlanned}
                        title="Scheduled blocks and draft plan"
                        onClick={togglePlanned}
                      >
                        Planned
                      </button>
                      <button
                        type="button"
                        className={`planner-cal-display-pop__toggle ${showActual ? "is-on" : ""}`}
                        aria-pressed={showActual}
                        title="Tracked app / site sessions"
                        onClick={toggleActual}
                      >
                        Actual
                      </button>
                    </div>
                  </div>
                ) : null}
                <div>
                  <p className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1.5">
                    Row height
                    <span className="ml-1.5 normal-case tracking-normal text-muted-foreground/70">
                      {HOUR_STRETCH_OPTIONS.find((o) => o.key === hourStretch)?.hint}
                    </span>
                  </p>
                  <div className="planner-cal-display-pop__toggles" role="group" aria-label="Hour row height">
                    {HOUR_STRETCH_OPTIONS.map(({ key, label, hint }) => (
                      <button
                        key={key}
                        type="button"
                        title={hint}
                        aria-pressed={hourStretch === key}
                        onClick={() => setHourStretch(key)}
                        className={`planner-cal-display-pop__toggle ${
                          hourStretch === key ? "is-on" : ""
                        }`}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                </div>
              </PopoverContent>
            </Popover>
          </div>
          {loading && <span className="planner-cal-meta__loading">Loading…</span>}
        </div>
      </div>

      {error && error !== "enforcer_unreachable" ? (
        <p className="text-[11px] text-muted-foreground mb-1.5">{error}</p>
      ) : null}

      <div className="planner-cal-grid-stack">
        {view === Views.DAY && !use2dLayer ? (
          <div
            className="planner-cal-minute-bar"
            title="Minutes within each hour (0–60). Blocks map left→right to start/end minutes."
          >
            <span className="planner-cal-minute-bar__label" aria-hidden>
              hr
            </span>
            <div className="planner-cal-minute-bar__lane" aria-hidden>
              {[0, 15, 30, 45, 60].map((m) => (
                <span
                  key={m}
                  className={
                    m === 0
                      ? "planner-cal-minute-bar__mark planner-cal-minute-bar__mark--zero"
                      : m === 60
                        ? "planner-cal-minute-bar__mark planner-cal-minute-bar__mark--edge"
                        : "planner-cal-minute-bar__mark"
                  }
                  style={{ left: `${(m / 60) * 100}%` }}
                >
                  <span className="planner-cal-minute-bar__tick" />
                  <span className="planner-cal-minute-bar__num">{m}</span>
                </span>
              ))}
            </div>
          </div>
        ) : null}

      <div
        ref={calendarWrapRef}
        className={`planner-calendar-wrap planner-calendar-wrap--no-allday relative overflow-visible ${
          focusedEventId != null || hourPeek ? "planner-calendar--focus-mode" : ""
        }`}
        style={{ minHeight: calendarHeight }}
        data-hour-stretch={hourStretch}
        data-calendar-view={view}
        data-2d-track={use2dLayer ? "1" : "0"}
        onClickCapture={(e) => {
          const t = e.target as HTMLElement;
          const gutter = t.closest(".rbc-time-gutter, .planner-day-track__hours") as HTMLElement | null;
          if (gutter) {
            const labelEl =
              (t.closest(".rbc-label") as HTMLElement | null) ||
              (t.closest(".planner-day-track__hour") as HTMLElement | null) ||
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
        {isEmpty && !use2dLayer ? (
          <div className="pointer-events-none absolute inset-x-0 top-3 z-10 flex justify-center px-4">
            <p className="text-center text-[11px] text-muted-foreground/80">
              No blocks yet — click a time slot to plan
            </p>
          </div>
        ) : null}
        <CalendarFocusContext.Provider value={{ focusedId: focusedEventId }}>
          <HourSliceProvider
            slices={hourSlices}
            dayKey={format(date, "yyyy-MM-dd")}
            enabled={use2dLayer}
          >
            {use2dLayer ? (
              <PlannerDayTrack
                day={date}
                height={calendarHeight}
                bodyRef={dayTrackBodyRef}
                emptyHint={
                  isEmpty ? "Drag across the grid to add a block" : null
                }
                onHourLabelClick={(hourStart, el) => openHourPeek(hourStart, el)}
              >
                <DayGridCreateLayer
                  day={date}
                  step={step}
                  containerRef={calendarWrapRef}
                  onCreate={onHorizontalCreate}
                />
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
              </PlannerDayTrack>
            ) : (
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
                allDayMaxRows={0}
                allDayAccessor={() => false}
                showMultiDayTimes
                selectable
                resizable={false}
                toolbar={false}
                draggableAccessor={(e: CalendarEvent) =>
                  !e.isActual && focusedEventId == null
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
            )}
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
              defaultDuration={slotDuration}
              onCancel={() => {
                setSlotStart(null);
                setSlotDuration(60);
              }}
              onSubmit={async (data) => {
                await createPlannerBlock(data);
                setSlotStart(null);
                setSlotDuration(60);
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
    </div>
  );
}
