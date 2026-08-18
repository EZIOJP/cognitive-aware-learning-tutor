import { useEffect, useState } from "react";
import { MousePointer2 } from "lucide-react";
import { fetchFocusQuality, type FocusQualityResponse } from "../../api/behaviorClient";
import { scoreColor } from "./GlanceBar";

type Props = {
  day?: string;
  refreshKey?: number;
};

export function FocusQualityBadge({ day, refreshKey = 0 }: Props) {
  const [data, setData] = useState<FocusQualityResponse | null>(null);

  useEffect(() => {
    let cancelled = false;
    void fetchFocusQuality(day)
      .then((d) => {
        if (!cancelled) setData(d);
      })
      .catch(() => {
        if (!cancelled) setData(null);
      });
    return () => {
      cancelled = true;
    };
  }, [day, refreshKey]);

  if (!data || data.on_plan_minutes <= 0) return null;

  return (
    <div className="rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-xs flex flex-wrap items-center gap-x-4 gap-y-1">
      <span className="flex items-center gap-1.5 text-muted-foreground">
        <MousePointer2 size={13} />
        Focus quality
      </span>
      <span className={`font-bold tabular-nums ${scoreColor(data.score)}`}>{data.score}</span>
      <span className="text-muted-foreground">{data.label}</span>
      <span className="text-muted-foreground tabular-nums">
        {data.switches} switches · {data.on_plan_minutes}m on-plan
      </span>
    </div>
  );
}

export default FocusQualityBadge;
