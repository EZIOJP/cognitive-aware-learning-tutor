import { BookOpen, Clock, Moon, Target, Zap } from "lucide-react";
import type { DesktopStats, GoalsStatusResponse } from "../../api/behaviorClient";
import { formatHoursMins } from "../../utils/formatDuration";

export function scoreColor(score: number): string {
  if (score >= 80) return "text-emerald-400";
  if (score >= 60) return "text-green-400";
  if (score >= 40) return "text-yellow-400";
  return "text-orange-400";
}

export function scoreRingStroke(score: number): string {
  if (score >= 80) return "stroke-emerald-400";
  if (score >= 60) return "stroke-green-400";
  if (score >= 40) return "stroke-yellow-400";
  return "stroke-orange-400";
}

function MiniScoreRing({ score, size = 40 }: { score: number; size?: number }) {
  const r = (size - 6) / 2;
  const c = 2 * Math.PI * r;
  const pct = Math.max(0, Math.min(100, score)) / 100;
  return (
    <svg width={size} height={size} className="shrink-0 -rotate-90" aria-hidden>
      <circle
        cx={size / 2}
        cy={size / 2}
        r={r}
        fill="none"
        stroke="rgba(255,255,255,0.08)"
        strokeWidth={3}
      />
      <circle
        cx={size / 2}
        cy={size / 2}
        r={r}
        fill="none"
        className={scoreRingStroke(score)}
        strokeWidth={3}
        strokeLinecap="round"
        strokeDasharray={c}
        strokeDashoffset={c * (1 - pct)}
      />
    </svg>
  );
}

type Props = {
  desktop: DesktopStats | null;
  dueReviews: number;
  onScheduleReview?: () => void;
  /** e.g. "today", "this week", "this month" */
  rangeLabel?: string;
  /** Last-night / selected-day sleep from wearables (hours) */
  sleepHours?: number | null;
  sleepScore?: number | null;
  goalsStatus?: GoalsStatusResponse | null;
};

/**
 * Single horizontal glance strip — icon + big number + muted label.
 * No bordered card grid; one bottom rule only.
 */
export function GlanceBar({
  desktop,
  dueReviews,
  onScheduleReview,
  rangeLabel = "today",
  sleepHours = null,
  sleepScore = null,
  goalsStatus = null,
}: Props) {
  const avgScore = desktop?.avg_productivity_score ?? 0;
  const pulse = desktop?.pulse ?? avgScore;
  const pulseLabel = desktop?.pulse_label ?? "Productivity";
  const showPulse = desktop?.pulse != null;
  const displayScore = showPulse ? pulse : avgScore;
  const scoreCaption = showPulse ? `Pulse · ${rangeLabel}` : `Score · ${rangeLabel}`;
  const sleepLabel =
    sleepHours != null && sleepHours > 0 ? `${sleepHours.toFixed(1)}h` : "—";
  const trackedLabel = desktop ? formatHoursMins(Math.round(desktop.total_seconds / 60)) : "—";
  const dailyGoal = goalsStatus?.goals?.[0];
  const goalPct = dailyGoal?.pct ?? 0;
  const goalMet = dailyGoal?.met ?? false;

  return (
    <div className="border-b border-white/10 pb-4">
      <div className="flex flex-wrap items-end gap-x-8 gap-y-4 sm:gap-x-10">
        <div className="flex items-center gap-3 min-w-[7rem]">
          <div className="relative flex items-center justify-center">
            <MiniScoreRing score={displayScore} />
            <span
              className={`absolute text-xs font-bold tabular-nums ${scoreColor(displayScore)}`}
            >
              {displayScore}
            </span>
          </div>
          <div>
            <div className={`text-2xl font-bold tabular-nums leading-none ${scoreColor(displayScore)}`}>
              {displayScore}
            </div>
            <div
              className="mt-1 text-[10px] uppercase tracking-wider text-muted-foreground"
              title={showPulse ? pulseLabel : undefined}
            >
              {scoreCaption}
            </div>
          </div>
        </div>

        <div className="min-w-[5.5rem]">
          <div className="flex items-center gap-1.5 text-indigo-300/90">
            <Moon size={14} aria-hidden />
            <span className="text-2xl font-bold tabular-nums text-indigo-200 leading-none">
              {sleepLabel}
            </span>
          </div>
          <div className="mt-1 text-[10px] uppercase tracking-wider text-muted-foreground">
            {sleepHours == null || sleepHours <= 0
              ? "Sleep · no data"
              : sleepScore != null && sleepScore > 0
                ? `Sleep · watch ${sleepScore}`
                : "Sleep"}
          </div>
        </div>

        <div className="min-w-[5.5rem]">
          <div className="flex items-center gap-1.5 text-blue-300/90">
            <Clock size={14} aria-hidden />
            <span className="text-2xl font-bold tabular-nums leading-none">{trackedLabel}</span>
          </div>
          <div className="mt-1 text-[10px] uppercase tracking-wider text-muted-foreground">
            Tracked · {rangeLabel}
          </div>
        </div>

        <div className="min-w-[6.5rem] flex-1 sm:flex-initial">
          <div className="flex items-center gap-1.5 text-amber-300/90">
            <BookOpen size={14} aria-hidden />
            <span className="text-2xl font-bold tabular-nums leading-none">
              {dueReviews > 0 ? dueReviews : "0"}
            </span>
          </div>
          <div className="mt-1 flex flex-wrap items-center gap-2">
            <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
              {dueReviews > 0 ? "SRS due" : "SRS clear"}
            </span>
            {dueReviews > 0 && onScheduleReview ? (
              <button
                type="button"
                onClick={onScheduleReview}
                className="text-[10px] px-2 py-0.5 rounded-md border border-amber-500/40 text-amber-200/90 hover:bg-amber-500/10"
              >
                Schedule
              </button>
            ) : null}
          </div>
        </div>

        {dailyGoal ? (
          <div className="min-w-[5.5rem]">
            <div className="flex items-center gap-1.5 text-teal-300/90">
              <Target size={14} aria-hidden />
              <span className="text-2xl font-bold tabular-nums leading-none">{goalPct}%</span>
            </div>
            <div className="mt-1 text-[10px] uppercase tracking-wider text-muted-foreground">
              {goalMet ? "Goal met" : "Daily goal"}
            </div>
          </div>
        ) : null}

        <div className="hidden md:flex items-center gap-1.5 text-[10px] text-muted-foreground ml-auto pb-1">
          <Zap size={12} className="text-yellow-400/80" aria-hidden />
          At a glance
        </div>
      </div>
    </div>
  );
}

export default GlanceBar;
