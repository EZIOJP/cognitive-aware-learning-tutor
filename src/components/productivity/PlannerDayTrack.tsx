import { useEffect, useMemo, useState, type ReactNode, type RefObject } from "react";

type Props = {
  day: Date;
  /** Total body height in px (24 hour rows). */
  height: number;
  bodyRef: RefObject<HTMLDivElement | null>;
  children?: ReactNode;
  /** Shown centered in the body when the day has no blocks. */
  emptyHint?: string | null;
  onHourLabelClick?: (hourStart: Date, el: HTMLElement) => void;
};

function hourParts(hour: number): { time: string; meridiem: string } {
  const h12 = ((hour + 11) % 12) + 1;
  return {
    time: `${h12}:00`,
    meridiem: hour >= 12 ? "PM" : "AM",
  };
}

/**
 * Unified day track: one CSS grid owns hour column + minute axis + body.
 * Shared column tracks keep 0/15/30/45/60 lines and create math aligned.
 */
export function PlannerDayTrack({
  day,
  height,
  bodyRef,
  children,
  emptyHint,
  onHourLabelClick,
}: Props) {
  const [nowTop, setNowTop] = useState<number | null>(null);

  const dayKey = useMemo(() => {
    const y = day.getFullYear();
    const m = String(day.getMonth() + 1).padStart(2, "0");
    const d = String(day.getDate()).padStart(2, "0");
    return `${y}-${m}-${d}`;
  }, [day]);

  useEffect(() => {
    const tick = () => {
      const n = new Date();
      const key = `${n.getFullYear()}-${String(n.getMonth() + 1).padStart(2, "0")}-${String(n.getDate()).padStart(2, "0")}`;
      if (key !== dayKey) {
        setNowTop(null);
        return;
      }
      const mins = n.getHours() * 60 + n.getMinutes() + n.getSeconds() / 60;
      setNowTop((mins / (24 * 60)) * height);
    };
    tick();
    const id = window.setInterval(tick, 30_000);
    return () => window.clearInterval(id);
  }, [dayKey, height]);

  // Jump the nearest scroll parent so "today" doesn't open stuck on empty midnight.
  useEffect(() => {
    const n = new Date();
    const key = `${n.getFullYear()}-${String(n.getMonth() + 1).padStart(2, "0")}-${String(n.getDate()).padStart(2, "0")}`;
    if (key !== dayKey) return;
    const mins = n.getHours() * 60 + n.getMinutes();
    const top = (mins / (24 * 60)) * height;
    const id = window.requestAnimationFrame(() => {
      const track = bodyRef.current?.closest(".planner-day-track") as HTMLElement | null;
      if (!track) return;
      let node: HTMLElement | null = track.parentElement;
      while (node && node !== document.body) {
        const style = window.getComputedStyle(node);
        const scrollable =
          /(auto|scroll)/.test(style.overflowY) && node.scrollHeight > node.clientHeight + 8;
        if (scrollable) {
          const trackTop =
            track.getBoundingClientRect().top -
            node.getBoundingClientRect().top +
            node.scrollTop;
          const target = Math.max(0, trackTop + top - Math.min(120, node.clientHeight * 0.25));
          node.scrollTo({ top: target, behavior: "auto" });
          break;
        }
        node = node.parentElement;
      }
    });
    return () => window.cancelAnimationFrame(id);
  }, [dayKey, height, bodyRef]);

  return (
    <div
      className="planner-day-track"
      style={{ ["--planner-day-body-h" as string]: `${height}px` }}
      data-day={dayKey}
    >
      <div className="planner-day-track__corner" aria-hidden>
        <span className="planner-day-track__min-zero" title="Start of hour">
          0
        </span>
      </div>
      <div className="planner-day-track__minutes" aria-hidden>
        {/* Idle: 15 / 30 / 45 */}
        {[15, 30, 45].map((m) => (
          <span
            key={m}
            className="planner-day-track__min-mark planner-day-track__min-mark--major"
            style={{ left: `${(m / 60) * 100}%` }}
          >
            <span className="planner-day-track__min-label">{m}</span>
            <span className="planner-day-track__min-tick" />
          </span>
        ))}
        {/* Create-only: 5-minute labels + 1-minute tick stubs (shown via data-creating) */}
        <div className="planner-day-track__min-fine">
          {Array.from({ length: 59 }, (_, i) => i + 1).map((m) => {
            const isFive = m % 5 === 0;
            return (
              <span
                key={m}
                className={
                  isFive
                    ? "planner-day-track__min-fine-mark planner-day-track__min-fine-mark--label"
                    : "planner-day-track__min-fine-mark"
                }
                style={{ left: `${(m / 60) * 100}%` }}
              >
                {isFive ? (
                  <span className="planner-day-track__min-label">{m}</span>
                ) : null}
                <span
                  className={
                    isFive
                      ? "planner-day-track__min-tick planner-day-track__min-tick--five"
                      : "planner-day-track__min-tick planner-day-track__min-tick--one"
                  }
                />
              </span>
            );
          })}
        </div>
        <span className="planner-day-track__min-end" title="End of hour">
          <span className="planner-day-track__min-label">60</span>
          <span className="planner-day-track__min-tick planner-day-track__min-tick--end" />
        </span>
      </div>

      <div className="planner-day-track__hours" aria-hidden={false}>
        {Array.from({ length: 24 }, (_, hour) => {
          const { time, meridiem } = hourParts(hour);
          return (
            <button
              key={hour}
              type="button"
              className="planner-day-track__hour"
              data-hour={hour}
              onClick={(e) => {
                const hourStart = new Date(day);
                hourStart.setHours(hour, 0, 0, 0);
                onHourLabelClick?.(hourStart, e.currentTarget);
              }}
            >
              <span className="planner-day-track__hour-time">{time}</span>
              <span className="planner-day-track__hour-meridiem">{meridiem}</span>
            </button>
          );
        })}
      </div>

      <div
        ref={bodyRef}
        className="planner-day-track__body"
        data-day-track-body="1"
      >
        {Array.from({ length: 24 }, (_, hour) => (
          <div
            key={hour}
            className="planner-day-track__row"
            data-hour={hour}
            data-day-track-row="1"
          />
        ))}
        {nowTop != null ? (
          <div
            className="planner-day-track__now"
            style={{ top: nowTop }}
            aria-hidden
          />
        ) : null}
        {emptyHint ? (
          <p className="planner-day-track__empty" aria-live="polite">
            {emptyHint}
          </p>
        ) : null}
        {children}
      </div>
    </div>
  );
}
