import type { EventProps } from "react-big-calendar";
import { format } from "date-fns";
import {
  fmtDurationMinutes,
  scoreAccent,
  shortAppName,
  type MergedInterval,
} from "./planVsActualUtils";
import { useCalendarFocus } from "./calendarFocusContext";

const MAX_ROWS = 3;
const MAX_ROWS_FOCUSED = 8;

type StackEvent = {
  id?: number;
  title: string;
  start: Date;
  end: Date;
  isActual?: boolean;
  actualStack?: MergedInterval[];
  stackTotalSeconds?: number;
};

export function ActualStackEvent({ event }: EventProps<StackEvent>) {
  const { focusedId } = useCalendarFocus();
  const isFocused = focusedId != null && focusedId === event.id;
  const items = event.actualStack ?? [];
  const rowLimit = isFocused ? MAX_ROWS_FOCUSED : MAX_ROWS;
  const visible = items.slice(0, rowLimit);
  const hidden = items.length - visible.length;
  const totalMins = Math.round((event.stackTotalSeconds ?? 0) / 60);
  const hourLabel = event.start ? format(event.start, "h:mm a") : "";

  const textName = isFocused ? "text-[11px]" : "text-[9px]";
  const textMeta = isFocused ? "text-[10px]" : "text-[8px]";

  const tooltip = items
    .map((i) => {
      const name = shortAppName(i.app_name || i.category);
      return `${name} · ${fmtDurationMinutes(Math.round(i.duration_seconds / 60))}`;
    })
    .join("\n");

  if (items.length <= 1 && items[0]) {
    const one = items[0];
    const name = shortAppName(one.app_name || one.category);
    const mins = Math.round(one.duration_seconds / 60);
    return (
      <div
        className={`actual-stack-card h-full flex flex-col justify-center gap-0.5 px-1 ${isFocused ? "actual-stack-card--focused" : ""}`}
        title={tooltip}
      >
        <div className="flex items-center gap-1 min-w-0">
          <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${scoreAccent(one.productivity_score)}`} />
          <span className={`${isFocused ? "text-[11px]" : "text-[10px]"} font-semibold truncate`}>{name}</span>
        </div>
        <span className={`${textMeta} text-sky-200/80 tabular-nums pl-2.5`}>{fmtDurationMinutes(mins)}</span>
      </div>
    );
  }

  return (
    <div
      className={`actual-stack-card h-full flex flex-col gap-0.5 px-1 py-0.5 overflow-hidden ${isFocused ? "actual-stack-card--focused" : ""}`}
      title={isFocused ? undefined : tooltip}
    >
      <div className="flex items-center justify-between gap-1 border-b border-sky-400/25 pb-0.5 mb-0.5">
        <span className={`${textMeta} font-semibold text-sky-100/90 tabular-nums`}>{hourLabel}</span>
        <span className={`${textMeta} text-sky-200/70 whitespace-nowrap`}>
          {items.length} · {fmtDurationMinutes(totalMins)}
        </span>
      </div>
      <div className="flex flex-col gap-px min-h-0 flex-1 overflow-hidden">
        {visible.map((item) => {
          const name = shortAppName(item.app_name || item.category);
          const mins = Math.round(item.duration_seconds / 60);
          return (
            <div key={`${item.start_time}-${name}`} className="flex items-center gap-1 min-w-0">
              <span className={`w-1 h-3 rounded-sm shrink-0 ${scoreAccent(item.productivity_score)}`} />
              <span className={`${textName} truncate flex-1 opacity-95`}>{name}</span>
              <span className={`${textMeta} tabular-nums text-sky-200/60 shrink-0`}>{mins}m</span>
            </div>
          );
        })}
        {hidden > 0 && (
          <span className={`${textMeta} text-sky-300/60 pl-2`}>+{hidden} · click to expand</span>
        )}
      </div>
    </div>
  );
}
