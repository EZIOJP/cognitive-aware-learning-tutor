import { Flame } from "lucide-react";
import { computeStreak, type AdherenceDay } from "./planVsActualUtils";

type Props = {
  days: AdherenceDay[];
  threshold?: number;
  loading?: boolean;
};

export function AdherenceStreak({ days, threshold = 0.7, loading }: Props) {
  const streak = computeStreak(days, threshold);
  const pctLabel = Math.round(threshold * 100);

  return (
    <div className="rounded-xl border border-white/10 bg-white/[0.03] p-4 flex flex-col justify-center min-w-[140px]">
      <div className="flex items-center gap-2 text-sm font-medium mb-2">
        <Flame size={15} className="text-orange-400" />
        Streak
      </div>
      {loading ? (
        <div className="h-10 w-16 rounded bg-white/5 animate-pulse" />
      ) : (
        <>
          <div className="text-3xl font-bold tabular-nums">{streak}</div>
          <p className="text-[11px] text-muted-foreground mt-1">
            day{streak === 1 ? "" : "s"} · ≥{pctLabel}% on planned days
          </p>
        </>
      )}
    </div>
  );
}

export default AdherenceStreak;
