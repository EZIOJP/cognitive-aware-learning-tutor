import { useEffect, useMemo, useState } from "react";
import { motion } from "motion/react";
import { cn } from "../../../app/components/ui/utils";
import { fetchHubDaily, type HubSegment } from "../../../api/hubClient";

interface Activity {
  type: string;
  startHour: number;
  endHour: number;
  color: string;
  isProductive: boolean;
}

const ACTIVITY_TYPES: Record<string, { label: string; color: string; isProductive: boolean }> = {
  sleep: { label: "Sleep", color: "#6366f1", isProductive: false },
  study: { label: "Study", color: "#3b82f6", isProductive: true },
  math: { label: "Math", color: "#10b981", isProductive: true },
  workout: { label: "Workout", color: "#f59e0b", isProductive: true },
  relaxation: { label: "Break", color: "#8b5cf6", isProductive: false },
  untracked: { label: "Other", color: "#64748b", isProductive: false },
};

function polarToCartesian(cx: number, cy: number, r: number, deg: number) {
  const rad = ((deg - 90) * Math.PI) / 180;
  return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
}

function segmentPath(start: number, end: number, outer: number, inner: number) {
  const s = polarToCartesian(0, 0, outer, start);
  const e = polarToCartesian(0, 0, outer, end);
  const is = polarToCartesian(0, 0, inner, start);
  const ie = polarToCartesian(0, 0, inner, end);
  const large = end - start > 180 ? 1 : 0;
  return `M ${s.x} ${s.y} A ${outer} ${outer} 0 ${large} 1 ${e.x} ${e.y} L ${ie.x} ${ie.y} A ${inner} ${inner} 0 ${large} 0 ${is.x} ${is.y} Z`;
}

const hourToAngle = (h: number) => (h / 24) * 360;

function formatHours(hours: number) {
  const h = Math.floor(Math.max(0, hours));
  const m = Math.round((Math.max(0, hours) - h) * 60);
  return `${h}h ${m}m`;
}

const FALLBACK_ACTIVITIES: Activity[] = [
  { type: "sleep", startHour: 0, endHour: 7, color: ACTIVITY_TYPES.sleep.color, isProductive: false },
  { type: "study", startHour: 7, endHour: 10, color: ACTIVITY_TYPES.study.color, isProductive: true },
  { type: "math", startHour: 10, endHour: 12, color: ACTIVITY_TYPES.math.color, isProductive: true },
  { type: "relaxation", startHour: 12, endHour: 12.75, color: ACTIVITY_TYPES.relaxation.color, isProductive: false },
  { type: "study", startHour: 12.75, endHour: 17, color: ACTIVITY_TYPES.study.color, isProductive: true },
];

function segmentsToActivities(segments: HubSegment[]): Activity[] {
  return segments.map((s) => {
    const type = s.type || "untracked";
    const meta = ACTIVITY_TYPES[type] || ACTIVITY_TYPES.untracked;
    return {
      type,
      startHour: s.startHour,
      endHour: s.endHour,
      color: s.color || meta.color,
      isProductive: meta.isProductive,
    };
  });
}

/** 24h day clock — segments from hub API when available. */
export function DayTimeTracker({ compact = false }: { compact?: boolean }) {
  const [now, setNow] = useState(() => new Date());
  const [activities, setActivities] = useState<Activity[]>(FALLBACK_ACTIVITIES);

  useEffect(() => {
    let cancelled = false;
    fetchHubDaily("today").then((payload) => {
      if (cancelled || !payload?.segments?.length) return;
      setActivities(segmentsToActivities(payload.segments));
    });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  const currentHour = now.getHours() + now.getMinutes() / 60 + now.getSeconds() / 3600;

  const stats = useMemo(() => {
    const passed = activities.filter((a) => a.endHour <= currentHour);
    const productiveTime = passed.filter((a) => a.isProductive).reduce((s, a) => s + (a.endHour - a.startHour), 0);
    const sleepTime = passed.filter((a) => a.type === "sleep").reduce((s, a) => s + (a.endHour - a.startHour), 0);
    return {
      productiveTime,
      sleepTime,
      timeLeft: Math.max(0, 24 - currentHour),
      timePassed: currentHour,
    };
  }, [activities, currentHour]);

  const hand = polarToCartesian(0, 0, 175, hourToAngle(currentHour));

  return (
    <div className={compact ? "" : "gloss-panel rounded-2xl p-5"}>
      {!compact && (
        <div className="text-center mb-4">
          <h3 className="text-lg font-semibold">24-hour life clock</h3>
          <p className="text-sm text-muted-foreground">
            {formatHours(stats.timeLeft)} left today · {Math.round((stats.timePassed / 24) * 100)}% elapsed
          </p>
        </div>
      )}
      <div className={cn("flex gap-4 items-center", compact ? "flex-row" : "flex-col lg:flex-row gap-6")}>
        <div className={cn("relative shrink-0", compact ? "scale-[0.55] origin-left -mr-16" : "")}>
          <svg width={compact ? 200 : 280} height={compact ? 200 : 280} viewBox="-140 -140 280 280" className="-rotate-90">
            <circle cx="0" cy="0" r="120" fill="none" stroke="currentColor" strokeOpacity={0.1} strokeWidth="48" />
            {activities.map((a, idx) => {
              const start = hourToAngle(a.startHour);
              const end = hourToAngle(Math.min(a.endHour, currentHour));
              if (end <= start) return null;
              return (
                <motion.path
                  key={idx}
                  d={segmentPath(start, end, 120, 88)}
                  fill={a.color}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                />
              );
            })}
            <line x1="0" y1="0" x2={hand.x} y2={hand.y} stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
            <circle cx="0" cy="0" r="72" className="fill-background" />
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
            <span className="text-2xl font-mono font-bold tabular-nums">
              {now.getHours().toString().padStart(2, "0")}:{now.getMinutes().toString().padStart(2, "0")}
            </span>
            <span className="text-xs text-muted-foreground">{now.getSeconds().toString().padStart(2, "0")}s</span>
          </div>
        </div>
        <div className={cn("flex-1 grid grid-cols-2 gap-2 w-full", compact && "hidden sm:grid")}>
          <div className="rounded-lg border p-3">
            <p className="text-xs text-muted-foreground">Productive</p>
            <p className="text-lg font-semibold">{formatHours(stats.productiveTime)}</p>
          </div>
          <div className="rounded-lg border p-3">
            <p className="text-xs text-muted-foreground">Sleep</p>
            <p className="text-lg font-semibold">{formatHours(stats.sleepTime)}</p>
          </div>
          <div className="rounded-lg border p-3 col-span-2">
            <p className="text-xs text-muted-foreground mb-2">Day progress</p>
            <div className="relative h-3 rounded-full bg-muted overflow-hidden">
              {activities.map((a, idx) => {
                const end = Math.min(a.endHour, currentHour);
                if (end <= a.startHour) return null;
                const width = ((end - a.startHour) / 24) * 100;
                const left = (a.startHour / 24) * 100;
                return (
                  <div
                    key={idx}
                    className="absolute top-0 h-full"
                    style={{ left: `${left}%`, width: `${width}%`, backgroundColor: a.color }}
                  />
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
