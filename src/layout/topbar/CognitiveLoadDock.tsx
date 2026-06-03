import { Activity } from "lucide-react";
import { useStudySession } from "../../context/StudySessionContext";
import { Badge } from "../../app/components/ui/badge";
import {
  COGNITIVE_LOAD_BADGE,
  COGNITIVE_LOAD_PERCENT,
  COGNITIVE_LOAD_SHORT,
} from "../../lib/cognitiveLoadDisplay";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "../../app/components/ui/popover";

const loadColors = {
  low: "bg-green-500",
  medium: "bg-yellow-500",
  high: "bg-red-500",
};

export function CognitiveLoadDock() {
  const { cognitiveLoad } = useStudySession();

  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          type="button"
          className="gloss-dock-btn flex items-center gap-2 rounded-full px-3 py-1.5 text-sm min-w-[7.25rem]"
          aria-label={`Cognitive load: ${COGNITIVE_LOAD_BADGE[cognitiveLoad]}`}
        >
          <Activity className="w-4 h-4 shrink-0" />
          <span
            className={`w-2 h-2 shrink-0 rounded-full ${loadColors[cognitiveLoad]}`}
          />
          <span className="hidden sm:inline text-xs font-medium font-mono w-[2.75rem] text-center tabular-nums">
            {COGNITIVE_LOAD_SHORT[cognitiveLoad]}
          </span>
        </button>
      </PopoverTrigger>
      <PopoverContent className="gloss-popover w-64 p-4" align="end" sideOffset={8}>
        <div className="space-y-3">
          <div className="flex items-center justify-between gap-2">
            <span className="text-sm font-medium">Cognitive load</span>
            <Badge
              variant={cognitiveLoad === "high" ? "destructive" : "secondary"}
              className="min-w-[4.5rem] justify-center font-mono tabular-nums"
            >
              {COGNITIVE_LOAD_BADGE[cognitiveLoad]}
            </Badge>
          </div>
          <div className="w-full h-2 rounded-full bg-muted overflow-hidden">
            <div
              className={`h-full transition-[width] duration-300 ${loadColors[cognitiveLoad]}`}
              style={{ width: COGNITIVE_LOAD_PERCENT[cognitiveLoad] }}
            />
          </div>
          <p className="text-xs text-muted-foreground">
            Driven by gamma band spikes and canvas inactivity. Tune thresholds in{" "}
            <code className="text-[10px]">config.ts</code>.
          </p>
        </div>
      </PopoverContent>
    </Popover>
  );
}
