import { BookOpen, Clock, Moon, Target } from "lucide-react";
import type { ReactNode } from "react";
import type { DesktopStats, GoalsStatusResponse } from "../../api/behaviorClient";
import { formatHoursMins } from "../../utils/formatDuration";
import { cn } from "../../app/components/ui/utils";

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

function MiniScoreRing({ score, size = 36 }: { score: number; size?: number }) {
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
  /**
   * `bar` — classic horizontal strip (calendar / non-home).
   * `rail` — compact equal cells under a mode hero (Home).
   */
  variant?: "bar" | "rail";
  /** When true, omit the Tracked cell (shown elsewhere as a hero). */
  hideTracked?: boolean;
};

function glanceValues(props: Props) {
  const {
    desktop,
    dueReviews,
    rangeLabel = "today",
    sleepHours = null,
    sleepScore = null,
    goalsStatus = null,
  } = props;
  const avgScore = desktop?.avg_productivity_score ?? 0;
  const pulse = desktop?.pulse ?? avgScore;
  const pulseLabel = desktop?.pulse_label ?? "Productivity";
  const showPulse = desktop?.pulse != null;
  const displayScore = showPulse ? pulse : avgScore;
  const scoreCaption = showPulse ? `Pulse · ${rangeLabel}` : `Score · ${rangeLabel}`;
  const sleepLabel =
    sleepHours != null && sleepHours > 0 ? `${sleepHours.toFixed(1)}h` : "—";
  const sleepCaption =
    sleepHours == null || sleepHours <= 0
      ? "Sleep · no data"
      : sleepScore != null && sleepScore > 0
        ? `Sleep · watch ${sleepScore}`
        : "Sleep";
  const trackedLabel = (() => {
    const mins: number[] = [];
    if (desktop && Number.isFinite(desktop.total_seconds)) {
      mins.push(Math.round(desktop.total_seconds / 60));
    }
    if (desktop && Number.isFinite(desktop.productive_seconds)) {
      mins.push(Math.round(desktop.productive_seconds / 60));
    }
    if (!mins.length) return "—";
    return formatHoursMins(Math.max(...mins));
  })();
  const dailyGoal = goalsStatus?.goals?.[0];
  const goalPct = dailyGoal?.pct ?? 0;
  const goalMet = dailyGoal?.met ?? false;

  return {
    displayScore,
    scoreCaption,
    pulseLabel,
    showPulse,
    sleepLabel,
    sleepCaption,
    trackedLabel,
    dueReviews,
    dailyGoal,
    goalPct,
    goalMet,
    rangeLabel,
  };
}

/**
 * Glance metrics — bar (legacy strip) or rail (Home compact cells).
 */
export function GlanceBar(props: Props) {
  const { variant = "bar", hideTracked = false, onScheduleReview } = props;
  const v = glanceValues(props);

  if (variant === "rail") {
    return (
      <div
        className={cn(
          "grid gap-px bg-white/[0.06] border-t border-white/10",
          hideTracked ? "grid-cols-2 sm:grid-cols-4" : "grid-cols-2 sm:grid-cols-3 lg:grid-cols-5",
        )}
      >
        <RailCell>
          <div className="flex items-center gap-2.5">
            <div className="relative flex items-center justify-center">
              <MiniScoreRing score={v.displayScore} size={32} />
              <span
                className={`absolute text-[10px] font-bold tabular-nums ${scoreColor(v.displayScore)}`}
              >
                {v.displayScore}
              </span>
            </div>
            <div className="min-w-0">
              <p className={`text-lg font-semibold tabular-nums leading-none ${scoreColor(v.displayScore)}`}>
                {v.displayScore}
              </p>
              <p className="mt-1 text-[10px] uppercase tracking-wider text-muted-foreground truncate">
                {v.scoreCaption}
              </p>
            </div>
          </div>
        </RailCell>

        {!hideTracked ? (
          <RailCell>
            <div className="flex items-center gap-1.5 text-sky-300/90">
              <Clock size={13} aria-hidden />
              <span className="text-lg font-semibold tabular-nums leading-none text-sky-100">
                {v.trackedLabel}
              </span>
            </div>
            <p className="mt-1 text-[10px] uppercase tracking-wider text-muted-foreground">
              Tracked · {v.rangeLabel}
            </p>
          </RailCell>
        ) : null}

        <RailCell>
          <div className="flex items-center gap-1.5 text-violet-300/80">
            <Moon size={13} aria-hidden />
            <span className="text-lg font-semibold tabular-nums leading-none text-violet-100">
              {v.sleepLabel}
            </span>
          </div>
          <p className="mt-1 text-[10px] uppercase tracking-wider text-muted-foreground truncate">
            {v.sleepCaption}
          </p>
        </RailCell>

        <RailCell>
          <div className="flex items-center gap-1.5 text-amber-300/90">
            <BookOpen size={13} aria-hidden />
            <span className="text-lg font-semibold tabular-nums leading-none">
              {v.dueReviews > 0 ? v.dueReviews : "0"}
            </span>
          </div>
          <div className="mt-1 flex flex-wrap items-center gap-1.5">
            <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
              {v.dueReviews > 0 ? "SRS due" : "SRS clear"}
            </span>
            {v.dueReviews > 0 && onScheduleReview ? (
              <button
                type="button"
                onClick={onScheduleReview}
                className="text-[10px] px-1.5 py-0.5 rounded border border-amber-500/35 text-amber-200/90 hover:bg-amber-500/10"
              >
                Schedule
              </button>
            ) : null}
          </div>
        </RailCell>

        {v.dailyGoal ? (
          <RailCell>
            <div className="flex items-center gap-1.5 text-teal-300/90">
              <Target size={13} aria-hidden />
              <span className="text-lg font-semibold tabular-nums leading-none">{v.goalPct}%</span>
            </div>
            <p className="mt-1 text-[10px] uppercase tracking-wider text-muted-foreground">
              {v.goalMet ? "Goal met" : "Daily goal"}
            </p>
          </RailCell>
        ) : (
          <RailCell>
            <p className="text-lg font-semibold tabular-nums leading-none text-muted-foreground/50">—</p>
            <p className="mt-1 text-[10px] uppercase tracking-wider text-muted-foreground">Daily goal</p>
          </RailCell>
        )}
      </div>
    );
  }

  // Classic horizontal strip (non-home surfaces)
  return (
    <div className="border-b border-white/10 pb-3 mb-0">
      <div className="flex flex-wrap items-end gap-x-6 gap-y-3 sm:gap-x-8">
        <div className="flex items-center gap-3 min-w-[7rem]">
          <div className="relative flex items-center justify-center">
            <MiniScoreRing score={v.displayScore} />
            <span
              className={`absolute text-xs font-bold tabular-nums ${scoreColor(v.displayScore)}`}
            >
              {v.displayScore}
            </span>
          </div>
          <div>
            <div className={`text-2xl font-bold tabular-nums leading-none ${scoreColor(v.displayScore)}`}>
              {v.displayScore}
            </div>
            <div
              className="mt-1 text-[10px] uppercase tracking-wider text-muted-foreground"
              title={v.showPulse ? v.pulseLabel : undefined}
            >
              {v.scoreCaption}
            </div>
          </div>
        </div>

        <div className="min-w-[5.5rem]">
          <div className="flex items-center gap-1.5 text-indigo-300/90">
            <Moon size={14} aria-hidden />
            <span className="text-2xl font-bold tabular-nums text-indigo-200 leading-none">
              {v.sleepLabel}
            </span>
          </div>
          <div className="mt-1 text-[10px] uppercase tracking-wider text-muted-foreground">
            {v.sleepCaption}
          </div>
        </div>

        <div className="min-w-[5.5rem]">
          <div className="flex items-center gap-1.5 text-blue-300/90">
            <Clock size={14} aria-hidden />
            <span className="text-2xl font-bold tabular-nums leading-none">{v.trackedLabel}</span>
          </div>
          <div className="mt-1 text-[10px] uppercase tracking-wider text-muted-foreground">
            Tracked · {v.rangeLabel}
          </div>
        </div>

        <div className="min-w-[6.5rem] flex-1 sm:flex-initial">
          <div className="flex items-center gap-1.5 text-amber-300/90">
            <BookOpen size={14} aria-hidden />
            <span className="text-2xl font-bold tabular-nums leading-none">
              {v.dueReviews > 0 ? v.dueReviews : "0"}
            </span>
          </div>
          <div className="mt-1 flex flex-wrap items-center gap-2">
            <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
              {v.dueReviews > 0 ? "SRS due" : "SRS clear"}
            </span>
            {v.dueReviews > 0 && onScheduleReview ? (
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

        {v.dailyGoal ? (
          <div className="min-w-[5.5rem]">
            <div className="flex items-center gap-1.5 text-teal-300/90">
              <Target size={14} aria-hidden />
              <span className="text-2xl font-bold tabular-nums leading-none">{v.goalPct}%</span>
            </div>
            <div className="mt-1 text-[10px] uppercase tracking-wider text-muted-foreground">
              {v.goalMet ? "Goal met" : "Daily goal"}
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}

function RailCell({ children }: { children: ReactNode }) {
  return <div className="bg-black/35 px-3.5 py-2.5 min-w-0">{children}</div>;
}

export default GlanceBar;
