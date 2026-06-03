import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Link } from "react-router";
import { motion } from "motion/react";
import { Clock, Loader2, Moon, Zap } from "lucide-react";
import { cn } from "../../app/components/ui/utils";
import { useTheme } from "../../context/ThemeContext";
import {
  fetchHubDaily,
  formatMinutesAsHours,
  type HubDailyPayload,
  type HubSegment,
} from "../../api/hubClient";

interface Activity {
  type: string;
  label: string;
  startHour: number;
  endHour: number;
  color: string;
  isProductive: boolean;
}

const ACTIVITY_META: Record<string, { label: string; color: string; isProductive: boolean }> = {
  sleep: { label: "Sleep", color: "#6366f1", isProductive: false },
  study: { label: "Study", color: "#3b82f6", isProductive: true },
  math: { label: "Math", color: "#10b981", isProductive: true },
  break: { label: "Break", color: "#8b5cf6", isProductive: false },
  relaxation: { label: "Break", color: "#8b5cf6", isProductive: false },
  productive: { label: "Productive", color: "#14b8a6", isProductive: true },
  untracked: { label: "Other", color: "#64748b", isProductive: false },
};

/** Stitch "Midnight Amber" life clock palette */
const MIDNIGHT_AMBER_META: Record<string, { label: string; color: string; isProductive: boolean }> = {
  sleep: { label: "Sleep", color: "#f59e0b", isProductive: false },
  study: { label: "Study", color: "#fbbf24", isProductive: true },
  math: { label: "Math", color: "#d97706", isProductive: true },
  break: { label: "Break", color: "#92400e", isProductive: false },
  relaxation: { label: "Break", color: "#92400e", isProductive: false },
  productive: { label: "Productive", color: "#fbbf24", isProductive: true },
  untracked: { label: "Unallocated", color: "#4b5563", isProductive: false },
};

/** Stitch "Oceanic Aurora" */
const OCEANIC_META: Record<string, { label: string; color: string; isProductive: boolean }> = {
  sleep: { label: "Sleep", color: "#06b6d4", isProductive: false },
  study: { label: "Study", color: "#2dd4bf", isProductive: true },
  math: { label: "Math", color: "#4ade80", isProductive: true },
  break: { label: "Break", color: "#0891b2", isProductive: false },
  relaxation: { label: "Break", color: "#0891b2", isProductive: false },
  productive: { label: "Study", color: "#2dd4bf", isProductive: true },
  untracked: { label: "Unallocated", color: "#4b5c63", isProductive: false },
};

type ClockVariant = "default" | "midnight-amber" | "oceanic-aurora";

function clockVariantFromAccent(accent: string, dark: boolean): ClockVariant {
  if (!dark) return "default";
  if (accent === "midnight-amber" || accent === "amber") return "midnight-amber";
  if (accent === "oceanic-aurora") return "oceanic-aurora";
  return "default";
}

const RING_R = 45;
const RING_C = 2 * Math.PI * RING_R;

const hourToAngle = (h: number) => (h / 24) * 360;

function formatClockTime(hour: number) {
  const h = Math.floor(hour);
  const m = Math.round((hour - h) * 60);
  return `${h.toString().padStart(2, "0")}:${m.toString().padStart(2, "0")}`;
}

function segmentsToActivities(segments: HubSegment[], variant: ClockVariant): Activity[] {
  const palette =
    variant === "midnight-amber"
      ? MIDNIGHT_AMBER_META
      : variant === "oceanic-aurora"
        ? OCEANIC_META
        : ACTIVITY_META;
  const usePreset = variant !== "default";
  return segments.map((s) => {
    const type = s.type || "untracked";
    const meta = palette[type] || palette.untracked;
    return {
      type,
      label: s.label || meta.label,
      startHour: s.startHour,
      endHour: s.endHour,
      color: usePreset ? meta.color : s.color || meta.color,
      isProductive: meta.isProductive,
    };
  });
}

type LifeClockWidgetProps = {
  /** Inside dashboard card — hide outer chrome */
  embedded?: boolean;
  /** Smaller ring for Life Tracker header */
  compact?: boolean;
  showLegend?: boolean;
};

export function LifeClockWidget({
  embedded = false,
  compact = false,
  showLegend = !compact,
}: LifeClockWidgetProps) {
  const { accentColor, isDarkMode } = useTheme();
  const clockVariant = clockVariantFromAccent(accentColor, isDarkMode);
  const stitchRing = clockVariant !== "default";
  const midnightAmber = clockVariant === "midnight-amber";
  const oceanic = clockVariant === "oceanic-aurora";

  const [now, setNow] = useState(() => new Date());
  const [hub, setHub] = useState<HubDailyPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(false);
    const load = () => {
      setLoading(true);
      setError(false);
      fetchHubDaily("today")
        .then((payload) => {
          if (!cancelled) {
            setHub(payload);
            setError(!payload);
          }
        })
        .catch(() => {
          if (!cancelled) setError(true);
        })
        .finally(() => {
          if (!cancelled) setLoading(false);
        });
    };
    load();
    const onRefresh = () => load();
    window.addEventListener("hub:refresh", onRefresh);
    return () => {
      cancelled = true;
      window.removeEventListener("hub:refresh", onRefresh);
    };
  }, []);

  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  const activities = useMemo(() => {
    if (hub?.segments?.length) return segmentsToActivities(hub.segments, clockVariant);
    return [];
  }, [hub, clockVariant]);

  const currentHour =
    hub?.current_hour ??
    now.getHours() + now.getMinutes() / 60 + now.getSeconds() / 3600;

  const stats = useMemo(() => {
    if (hub) {
      return {
        productiveMinutes: hub.productive_minutes,
        sleepMinutes: hub.sleep_minutes,
        timeLeft: hub.time_left_hours,
        percentElapsed: hub.percent_elapsed,
        lifeScore: hub.life_score,
      };
    }
    const passed = activities.filter((a) => a.endHour <= currentHour);
    const productiveHours = passed
      .filter((a) => a.isProductive)
      .reduce((s, a) => s + (a.endHour - a.startHour), 0);
    const sleepHours = passed
      .filter((a) => a.type === "sleep")
      .reduce((s, a) => s + (a.endHour - a.startHour), 0);
    return {
      productiveMinutes: Math.round(productiveHours * 60),
      sleepMinutes: Math.round(sleepHours * 60),
      timeLeft: Math.max(0, 24 - currentHour),
      percentElapsed: Math.round((currentHour / 24) * 1000) / 10,
      lifeScore: 0,
    };
  }, [hub, activities, currentHour]);

  const legendRows = useMemo(() => {
    return activities.map((a) => {
      const dur = a.endHour - a.startHour;
      return {
        label: a.label,
        start: a.startHour,
        end: a.endHour,
        duration: dur,
        pct: Math.round((dur / 24) * 1000) / 10,
        color: a.color,
      };
    });
  }, [activities]);

  const size = compact ? 128 : 288;
  const empty = !loading && activities.length === 0;
  const nowRotate = hourToAngle(currentHour);

  const ring = (
    <div
      className={cn(
        "relative shrink-0",
        compact ? "w-32 h-32" : "w-72 h-72",
        stitchRing && !compact && (midnightAmber ? "life-clock-panel--amber" : oceanic ? "life-clock-panel--oceanic" : ""),
        stitchRing && !compact && "rounded-full"
      )}
    >
      <svg
        width={size}
        height={size}
        viewBox="0 0 100 100"
        className="-rotate-90 w-full h-full"
        role="img"
        aria-label="24-hour life timeline"
      >
        <circle
          cx="50"
          cy="50"
          r={RING_R}
          fill="none"
          stroke={stitchRing ? "rgba(255,255,255,0.05)" : "currentColor"}
          strokeOpacity={stitchRing ? 1 : 0.12}
          strokeWidth={compact ? 10 : 8}
        />
        {stitchRing && (
          <circle
            cx="50"
            cy="50"
            r={RING_R}
            fill="none"
            stroke="rgba(255,255,255,0.05)"
            strokeWidth={compact ? 10 : 8}
            strokeDasharray="1 3"
          />
        )}
        {activities.map((a, idx) => {
          const dur = Math.max(0, a.endHour - a.startHour);
          if (dur <= 0) return null;
          const len = (dur / 24) * RING_C;
          const offset = (a.startHour / 24) * RING_C;
          const isFuture = a.startHour >= currentHour;
          return (
            <motion.circle
              key={`${a.type}-${idx}`}
              cx="50"
              cy="50"
              r={RING_R}
              fill="none"
              stroke={a.color}
              strokeWidth={compact ? 10 : 8}
              strokeLinecap="round"
              strokeDasharray={`${len} ${RING_C - len}`}
              strokeDashoffset={-offset}
              initial={{ opacity: 0 }}
              animate={{ opacity: isFuture ? 0.35 : 1 }}
              transition={{ duration: 0.6 }}
              aria-label={`${a.label} ${formatClockTime(a.startHour)} to ${formatClockTime(a.endHour)}`}
            />
          );
        })}
        <g transform={`rotate(${nowRotate} 50 50)`}>
          <line
            x1="50"
            y1={compact ? 6 : 4}
            x2="50"
            y2={compact ? 14 : 12}
            stroke={stitchRing ? (oceanic ? "#06b6d4" : "#ffffff") : "currentColor"}
            strokeWidth="1.5"
            strokeLinecap="round"
          />
          <circle
            cx="50"
            cy={compact ? 5 : 3}
            r={compact ? 2.5 : 3}
            className={stitchRing ? "fill-primary animate-pulse" : "fill-primary"}
          />
        </g>
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none text-center">
        <span
          className={cn(
            "font-mono font-bold tabular-nums leading-none",
            compact ? "text-base" : "text-[32px]"
          )}
        >
          {now.getHours().toString().padStart(2, "0")}:
          {now.getMinutes().toString().padStart(2, "0")}
        </span>
        {!compact && (
          <span className="text-xs text-muted-foreground font-mono mt-1">
            {hub?.date ?? now.toISOString().slice(0, 10)}
          </span>
        )}
        {compact && (
          <span className="text-[9px] text-muted-foreground font-mono">
            {now.getSeconds().toString().padStart(2, "0")}s
          </span>
        )}
      </div>
    </div>
  );

  const metricCard = (label: string, value: string, icon: ReactNode) => (
    <div
      className={cn(
        "flex items-center justify-between p-4 rounded-2xl",
        stitchRing ? "life-clock-metric" : "rounded-lg border border-border/50 bg-background/40 p-3"
      )}
    >
      <div className="flex items-center gap-2">
        {icon}
        <span className="text-sm text-foreground">{label}</span>
      </div>
      <span className="font-mono font-semibold tabular-nums text-sm">{value}</span>
    </div>
  );

  const metrics = (
    <div
      className={cn(
        "flex-1 flex flex-col gap-3 w-full min-w-0",
        compact && "hidden lg:flex"
      )}
    >
      {metricCard(
        "Productive",
        formatMinutesAsHours(stats.productiveMinutes),
        <Zap className={cn("w-4 h-4", midnightAmber ? "text-secondary" : "text-muted-foreground")} />
      )}
      {metricCard(
        "Sleep",
        formatMinutesAsHours(stats.sleepMinutes),
        <Moon className={cn("w-4 h-4", midnightAmber ? "text-primary" : "text-muted-foreground")} />
      )}
      <div
        className={cn(
          "p-4 rounded-2xl space-y-2",
          midnightAmber ? "life-clock-metric" : "rounded-lg border border-border/50 bg-background/40 col-span-2"
        )}
      >
        <div className="flex justify-between text-sm">
          <span>Day progress</span>
          <span className={cn("font-mono tabular-nums", midnightAmber && "text-secondary")}>
            {stats.percentElapsed}%
          </span>
        </div>
        <div
          className={cn(
            "relative h-2 w-full rounded-full overflow-hidden",
            midnightAmber ? "life-clock-progress-track" : "bg-muted"
          )}
          role="progressbar"
          aria-valuenow={stats.percentElapsed}
          aria-valuemin={0}
          aria-valuemax={100}
        >
          <div
            className={cn(
              "absolute inset-y-0 left-0 rounded-full transition-all duration-500",
              midnightAmber ? "life-clock-progress-fill" : "bg-primary/80"
            )}
            style={{ width: `${Math.min(100, stats.percentElapsed)}%` }}
          />
        </div>
        <p className="text-xs text-muted-foreground">{stats.timeLeft.toFixed(1)}h left today</p>
      </div>
      {stats.lifeScore > 0 && (
        <p className="text-center text-sm text-muted-foreground">
          Life score <span className="font-semibold text-foreground">{stats.lifeScore}</span>/100
        </p>
      )}
    </div>
  );

  const legend = showLegend && legendRows.length > 0 && (
    <div className="mt-6 overflow-x-auto">
      <table className="w-full text-sm text-left">
        <thead className={cn(midnightAmber && "border-b border-white/10")}>
          <tr className="text-muted-foreground">
            <th className="py-2 font-medium">Category</th>
            <th className="py-2 font-medium text-center">Start</th>
            <th className="py-2 font-medium text-center">End</th>
            <th className="py-2 font-medium text-center">Duration</th>
            <th className="py-2 font-medium text-right">% of Day</th>
          </tr>
        </thead>
        <tbody className={cn(midnightAmber && "divide-y divide-white/5")}>
          {legendRows.map((row, i) => (
            <tr key={i}>
              <td className="py-3 flex items-center gap-2">
                <span className="w-3 h-3 rounded-full shrink-0" style={{ backgroundColor: row.color }} />
                {row.label}
              </td>
              <td className="py-3 text-center font-mono text-xs text-muted-foreground">
                {formatClockTime(row.start)}
              </td>
              <td className="py-3 text-center font-mono text-xs text-muted-foreground">
                {formatClockTime(row.end)}
              </td>
              <td className="py-3 text-center font-mono text-xs">
                {formatMinutesAsHours(Math.round(row.duration * 60))}
              </td>
              <td className="py-3 text-right font-mono text-xs">{row.pct}%</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );

  if (loading) {
    return (
      <div className={cn(!embedded && "gloss-panel rounded-2xl p-5", "flex items-center justify-center gap-2 py-12")}>
        <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
        <span className="text-sm text-muted-foreground">Loading today&apos;s timeline…</span>
      </div>
    );
  }

  if (error && !hub) {
    return (
      <div className={cn(!embedded && "gloss-panel rounded-2xl p-5", "text-center py-8 space-y-2")}>
        <p className="text-sm text-muted-foreground">Could not load today&apos;s timeline.</p>
        <button
          type="button"
          className="text-sm text-primary hover:underline"
          onClick={() => window.location.reload()}
        >
          Retry
        </button>
      </div>
    );
  }

  if (empty) {
    return (
      <div className={cn(!embedded && "gloss-panel rounded-2xl p-5", "text-center py-6 space-y-3")}>
        <Clock className="w-10 h-10 mx-auto text-muted-foreground/50" />
        <p className="text-sm text-muted-foreground max-w-xs mx-auto">
          Log your day in Life Tracker to fill the ring.
        </p>
        <Link
          to="/life-tracker"
          className="inline-flex text-sm font-medium text-primary hover:underline"
        >
          Open Life Tracker →
        </Link>
      </div>
    );
  }

  return (
    <div
      className={cn(
        !embedded && "gloss-panel rounded-2xl p-5 md:p-8",
        midnightAmber && !embedded && "life-clock-panel--amber"
      )}
    >
      {!embedded && !compact && (
        <div className="text-center mb-4">
          <h3 className="text-lg font-semibold">24-hour life clock</h3>
          <p className="text-sm text-muted-foreground">Track how your day is unfolding</p>
        </div>
      )}
      <div
        className={cn(
          "flex gap-4 items-start",
          compact ? "flex-row" : "flex-col lg:flex-row gap-6"
        )}
      >
        {ring}
        {metrics}
      </div>
      {legend}
    </div>
  );
}
