import { useCallback, useEffect, useMemo, useRef, useState } from "react";
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
  fetchActualOverlay,
  fetchPlannerBlocks,
  rollForwardPlannerBlock,
  startPlannerBlock,
  updatePlannerBlock,
  type ActualSession,
  type PlannerBlock,
  type ProposedPlannerBlock,
} from "../../api/plannerClient";
import { mergeForCalendar, stackActualByHour, mergedIntervalLabel, parseApiDate, actualStackTimeSpan, eventsOverlapForFocus } from "./planVsActualUtils";
import { ActualStackEvent } from "./ActualStackEvent";
import { ActualFocusPanel, type EventAnchorRect } from "./ActualFocusPanel";
import { CalendarFocusContext } from "./calendarFocusContext";
import { Settings2 } from "lucide-react";
import { Popover, PopoverContent, PopoverTrigger } from "../../app/components/ui/popover";
import { PlannerBlockActions } from "./PlannerBlockActions";
import { PlannerBlockForm } from "./PlannerBlockForm";
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

function EventChip(props: EventProps<CalendarEvent>) {
  if (props.event.isActual) {
    return <ActualStackEvent {...props} />;
  }
  return (
    <div className="text-[11px] leading-tight px-0.5 overflow-hidden">
      <div className="font-medium truncate">{props.event.title}</div>
      {props.event.isDraft ? (
        <div className="opacity-80">draft</div>
      ) : props.event.resource.status === "in_progress" ? (
        <div className="opacity-80">in progress</div>
      ) : null}
    </div>
  );
}

function eventTitle(block: PlannerBlock): string {
  if (block.status === "done") return `${block.title} (done)`;
  if (block.status === "rolled") return `${block.title} (rolled)`;
  return `${block.title} (${block.remaining_minutes}m left)`;
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
};

export function PlannerCalendar({
  selectedDay,
  onSelectedDayChange,
  refreshKey = 0,
  expanded = false,
  view: viewProp,
  onViewChange,
  draftBlocks = null,
}: Props) {
  const [viewInternal, setViewInternal] = useState<View>(Views.WEEK);
  const view = viewProp ?? viewInternal;
  const setView = (next: View) => {
    if (viewProp === undefined) setViewInternal(next);
    onViewChange?.(next);
  };
  const [date, setDate] = useState(() => (selectedDay ? startOfDay(selectedDay) : new Date()));
  const [step, setStep] = useState(30);
  const [blocks, setBlocks] = useState<PlannerBlock[]>([]);
  const [actuals, setActuals] = useState<ActualSession[]>([]);
  const [showActual, setShowActual] = useState(true);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<PlannerBlock | null>(null);
  const [slotStart, setSlotStart] = useState<Date | null>(null);
  const [focusedEventId, setFocusedEventId] = useState<number | null>(null);
  const [focusedStackItemIndex, setFocusedStackItemIndex] = useState(0);
  const [eventAnchor, setEventAnchor] = useState<EventAnchorRect | null>(null);
  const [hourStretch, setHourStretch] = useState<HourStretch>("tall");
  const calendarWrapRef = useRef<HTMLDivElement>(null);

  const range = useMemo(() => {
    if (view === Views.DAY) {
      return { from: startOfDay(date), to: endOfDay(date) };
    }
    if (view === Views.MONTH) {
      return {
        from: startOfWeek(startOfMonth(date), { weekStartsOn: 1 }),
        to: endOfWeek(endOfMonth(date), { weekStartsOn: 1 }),
      };
    }
    return { from: startOfWeek(date, { weekStartsOn: 1 }), to: endOfWeek(date, { weekStartsOn: 1 }) };
  }, [view, date]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [b, a] = await Promise.all([
        fetchPlannerBlocks(range.from, range.to),
        showActual ? fetchActualOverlay(range.from, range.to) : Promise.resolve([]),
      ]);
      setBlocks(b);
      setActuals(a);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load planner");
    } finally {
      setLoading(false);
    }
  }, [range.from, range.to, showActual, refreshKey]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!selectedDay) return;
    setDate(selectedDay);
  }, [selectedDay?.toDateString()]);

  const calendarHeight = Math.round((expanded ? 640 : 540) * HOUR_STRETCH_HEIGHT[hourStretch]);

  const events: CalendarEvent[] = useMemo(() => {
    const planned: CalendarEvent[] = blocks
      .filter((b) => b.status !== "rolled")
      .map((b) => ({
        id: b.id,
        title: eventTitle(b),
        start: parseApiDate(b.start_at),
        end: parseApiDate(b.end_at),
        resource: b,
      }));

    const draftEvents: CalendarEvent[] = (draftBlocks ?? [])
      .filter((b) => b.source !== "existing")
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
      });

    if (!showActual) {
      return [...planned, ...draftEvents];
    }

    const merged = mergeForCalendar(actuals);
    const useStacks = view === Views.MONTH; // week: real time spans

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
          s.app_name ?? s.category ?? "Actual",
          s.start_time,
          s.end_time,
        ),
        isActual: true,
        isStack: false,
        actualStack: [s],
        stackTotalSeconds: s.duration_seconds,
      }));
    }

    return [...planned, ...draftEvents, ...actualEvents];
  }, [blocks, actuals, showActual, view, draftBlocks]);

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
        setEventAnchor(null);
        return;
      }
      if (focusedEventId == null || cycleTotal < 2) return;
      if (e.key === "ArrowLeft") cycleFocus(-1);
      if (e.key === "ArrowRight") cycleFocus(1);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [cycleFocus, focusedEventId, cycleTotal]);

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
        const base3d = isFocused
          ? {
              background: "linear-gradient(165deg, rgba(56, 120, 210, 0.92) 0%, rgba(15, 40, 90, 0.95) 55%, rgba(10, 25, 55, 0.98) 100%)",
              boxShadow:
                "0 5px 0 rgba(8, 20, 45, 0.95), 0 10px 24px rgba(0, 0, 0, 0.45), inset 0 1px 0 rgba(186, 230, 253, 0.45), inset 0 -2px 0 rgba(0, 0, 0, 0.2)",
            }
          : {
              background: "linear-gradient(165deg, rgba(40, 90, 170, 0.55) 0%, rgba(20, 45, 95, 0.65) 100%)",
              boxShadow:
                "0 3px 0 rgba(12, 30, 65, 0.85), 0 6px 14px rgba(0, 0, 0, 0.28), inset 0 1px 0 rgba(147, 197, 253, 0.2)",
            };
        return {
          className: [
            event.isStack ? "actual-stack-event" : "actual-single-event",
            "actual-event-3d",
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
        className: focusClass || undefined,
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
    setFocusedEventId(null);
    setEventAnchor(null);
    setSelected(event.resource);
    setSlotStart(null);
  };

  const onSelectSlot = (slot: SlotInfo) => {
    onSelectedDayChange?.(startOfDay(slot.start));
    setFocusedEventId(null);
    setEventAnchor(null);
    setSelected(null);
    setSlotStart(slot.start);
  };

  const isEmpty =
    !loading &&
    blocks.filter((b) => b.status !== "rolled").length === 0 &&
    (!showActual || actuals.length === 0);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2 justify-between planner-toolbar-row">
        <div className="flex flex-wrap gap-2 items-center">
          <label
            className="flex items-center gap-1.5 text-xs text-muted-foreground"
            title="Blue blocks are tracked sessions. Click for details; ← → cycles overlaps."
          >
            <input
              type="checkbox"
              checked={showActual}
              onChange={(e) => setShowActual(e.target.checked)}
            />
            Show actual
          </label>
          <Popover>
            <PopoverTrigger asChild>
              <button
                type="button"
                className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs border border-white/10 text-muted-foreground hover:bg-white/5 hover:text-foreground"
              >
                <Settings2 size={12} />
                Display
                <span className="text-[10px] opacity-60">
                  {step}m · {hourStretch === "compact" ? "S" : hourStretch === "normal" ? "M" : hourStretch === "tall" ? "L" : "XL"}
                </span>
              </button>
            </PopoverTrigger>
            <PopoverContent align="start" className="w-64 space-y-3 bg-popover/95 backdrop-blur-sm">
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
                Calendar merges sessions within 15 min; Day ribbon uses 2 min — same data, different zoom.
              </p>
            </PopoverContent>
          </Popover>
          <span className="hidden sm:inline text-[10px] text-muted-foreground/80">
            KPIs above follow Month / Week / Day
          </span>
        </div>
        {loading && <span className="text-xs text-muted-foreground">Loading…</span>}
      </div>

      {error && <p className="text-xs text-red-400">{error}</p>}

      <div
        ref={calendarWrapRef}
        className={`planner-calendar-wrap relative rounded-xl border border-white/10 bg-black/20 p-2 ${
          focusedEventId != null ? "planner-calendar--focus-mode overflow-visible" : ""
        } ${expanded ? "min-h-[640px]" : "min-h-[520px]"}`}
        data-hour-stretch={hourStretch}
        data-calendar-view={view}
        onClickCapture={(e) => {
          if (focusedEventId == null) return;
          const t = e.target as HTMLElement;
          if (
            t.closest(".rbc-event.calendar-event-focused") ||
            t.closest('[role="dialog"]')
          ) {
            return;
          }
          setFocusedEventId(null);
          setEventAnchor(null);
        }}
      >
        {isEmpty && (
          <div className="pointer-events-none absolute inset-x-0 top-14 z-10 flex justify-center px-4">
            <p className="rounded-lg border border-white/10 bg-black/70 px-3 py-2 text-center text-xs text-muted-foreground shadow-lg backdrop-blur-sm">
              No blocks this view — click a time slot to plan, or open Import & routines for timetable / propose week.
            </p>
          </div>
        )}
        <CalendarFocusContext.Provider value={{ focusedId: focusedEventId }}>
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
            selectable
            resizable={false}
            draggableAccessor={(e: CalendarEvent) => !e.isActual && focusedEventId == null}
            onEventDrop={onEventDrop as never}
            onSelectEvent={onSelectEvent as never}
            onSelectSlot={onSelectSlot}
            eventPropGetter={eventStyleGetter as never}
            components={{ event: EventChip as never }}
            views={expanded ? [Views.MONTH, Views.WEEK, Views.DAY] : [Views.DAY, Views.WEEK]}
            defaultView={expanded ? Views.WEEK : Views.WEEK}
            style={{ height: calendarHeight }}
          />
        </CalendarFocusContext.Provider>

        {focusedEvent && eventAnchor && (() => {
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
      </div>

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

      {selected && (
        <PlannerBlockActions
          block={selected}
          onClose={() => setSelected(null)}
          onStart={async () => {
            const b = await startPlannerBlock(selected.id);
            setSelected(b);
            await load();
          }}
          onComplete={async (minutes) => {
            const b = await completePlannerBlock(selected.id, minutes);
            setSelected(b.status === "done" ? null : b);
            await load();
          }}
          onRollForward={async () => {
            await rollForwardPlannerBlock(selected.id);
            setSelected(null);
            await load();
          }}
          onDelete={async () => {
            await deletePlannerBlock(selected.id);
            setSelected(null);
            await load();
          }}
        />
      )}
    </div>
  );
}
