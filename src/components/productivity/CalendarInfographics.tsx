import { BookOpen, Clock, TrendingUp, Zap } from "lucide-react";
import type { DesktopStats } from "../../api/behaviorClient";

function fmtMinutes(m: number): string {
  if (m < 60) return `${m}m`;
  const h = Math.floor(m / 60);
  const rem = m % 60;
  return rem > 0 ? `${h}h ${rem}m` : `${h}h`;
}

type Props = {
  desktop: DesktopStats | null;
  dueReviews: number;
  onScheduleReview?: () => void;
  /** e.g. "today", "this week", "this month" */
  rangeLabel?: string;
};

export function CalendarInfographics({
  desktop,
  dueReviews,
  onScheduleReview,
  rangeLabel = "today",
}: Props) {
  const avgScore = desktop?.avg_productivity_score ?? 0;
  const scoreColor =
    avgScore >= 80 ? "text-emerald-400" :
    avgScore >= 60 ? "text-green-400" :
    avgScore >= 40 ? "text-yellow-400" : "text-orange-400";

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 text-xs text-muted-foreground uppercase tracking-wider">
        <TrendingUp size={14} className="text-violet-400" />
        Quick stats · {rangeLabel}
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <div className="rounded-xl border border-white/10 bg-white/[0.03] p-4 flex flex-col justify-between">
          <div className="flex items-center gap-2 font-medium text-sm">
            <Zap size={15} className="text-yellow-400" />
            Screen score
          </div>
          <div className={`text-4xl font-bold tabular-nums ${scoreColor}`}>{avgScore}</div>
          <p className="text-[11px] text-muted-foreground">Weighted productivity · {rangeLabel}</p>
        </div>

        <div className="rounded-xl border border-white/10 bg-white/[0.03] p-4 flex flex-col justify-between">
          <div className="flex items-center gap-2 font-medium text-sm">
            <Clock size={15} className="text-blue-400" />
            Tracked {rangeLabel}
          </div>
          <div className="text-4xl font-bold tabular-nums">
            {desktop ? fmtMinutes(Math.round(desktop.total_seconds / 60)) : "—"}
          </div>
          <p className="text-[11px] text-muted-foreground">
            {(() => {
              const apps = desktop?.sessions.filter((s) => s.kind !== "browser").length ?? 0;
              const sites = desktop?.sessions.reduce(
                (n, s) => n + (s.kind === "browser" ? (s.sites?.length ?? 0) : 0),
                0,
              ) ?? 0;
              const label = sites > 0 ? `${apps} apps · ${sites} sites` : `${desktop?.sessions.length ?? 0} apps`;
              return `${label} · ${desktop ? `${(desktop.total_seconds / 3600).toFixed(1)}h` : "—"}`;
            })()}
          </p>
        </div>

        <div className="rounded-xl border border-white/10 bg-white/[0.03] p-4 space-y-3 flex flex-col justify-center">
          {dueReviews > 0 ? (
            <>
              <p className="text-sm flex items-center gap-1.5">
                <BookOpen size={15} className="text-amber-400" />
                {dueReviews} SRS card{dueReviews === 1 ? "" : "s"} due
              </p>
              {onScheduleReview && (
                <button
                  type="button"
                  onClick={onScheduleReview}
                  className="w-full text-xs px-3 py-1.5 rounded-lg border border-amber-500/40 hover:bg-amber-500/10"
                >
                  Schedule review block
                </button>
              )}
            </>
          ) : (
            <p className="text-sm text-muted-foreground">No SRS reviews due</p>
          )}
        </div>
      </div>
    </div>
  );
}
