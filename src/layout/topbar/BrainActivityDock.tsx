import { Brain } from "lucide-react";
import { useStudySession } from "../../context/StudySessionContext";
import { BiometricMonitor } from "../../app/components/BiometricMonitor";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "../../app/components/ui/popover";

export function BrainActivityDock() {
  const { biometricData, cognitiveLoad } = useStudySession();
  const latest = biometricData[biometricData.length - 1];

  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          type="button"
          className="gloss-dock-btn flex items-center gap-2 rounded-full px-3 py-1.5 text-sm"
          aria-label="Brain activity"
        >
          <Brain className="w-4 h-4 text-blue-500" />
          <span className="hidden sm:inline text-muted-foreground">EEG</span>
          <span className="flex gap-1 font-mono text-xs">
            <span className="text-blue-500">{latest?.alpha.toFixed(0) ?? "—"}</span>
            <span className="text-green-500">{latest?.beta.toFixed(0) ?? "—"}</span>
            <span className="text-red-500">{latest?.gamma.toFixed(0) ?? "—"}</span>
          </span>
        </button>
      </PopoverTrigger>
      <PopoverContent
        className="gloss-popover w-[min(100vw-2rem,380px)] p-0 border-0"
        align="end"
        sideOffset={8}
      >
        <div className="p-2 max-h-[70vh] overflow-y-auto">
          <BiometricMonitor data={biometricData} cognitiveLoad={cognitiveLoad} />
        </div>
      </PopoverContent>
    </Popover>
  );
}
