import { AlertTriangle, Loader2 } from "lucide-react";
import type { GapAnalysisResult } from "./studySessionTypes";
import { cn } from "../../app/components/ui/utils";

type Props = {
  gap: GapAnalysisResult | null;
  loading?: boolean;
};

const SEVERITY_CLASS: Record<string, string> = {
  high: "border-red-500/40 bg-red-500/10 text-red-200",
  medium: "border-amber-500/40 bg-amber-500/10 text-amber-100",
  low: "border-emerald-500/30 bg-emerald-500/10 text-emerald-100",
};

export function StudyLibraryGapPanel({ gap, loading }: Props) {
  if (loading) {
    return (
      <div className="study-library-glass shrink-0 p-3 flex items-center gap-2 text-xs text-emerald-300">
        <Loader2 className="w-4 h-4 animate-spin" />
        Running gap analysis…
      </div>
    );
  }

  if (!gap) return null;

  return (
    <div className="study-library-glass shrink-0 p-3 max-h-40 overflow-y-auto study-library-markdown-scroll space-y-2">
      <div className="flex items-start gap-2">
        <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
        <p className="text-xs text-slate-300 leading-relaxed">{gap.summary}</p>
      </div>
      <div className="flex flex-wrap gap-1.5">
        {gap.gaps.slice(0, 6).map((g, i) => (
          <span
            key={`${g.topic}-${i}`}
            className={cn(
              "text-[10px] px-2 py-0.5 rounded border",
              SEVERITY_CLASS[g.severity] ?? SEVERITY_CLASS.medium,
            )}
            title={g.suggestion}
          >
            {g.topic}
          </span>
        ))}
      </div>
      {gap.source === "template" && (
        <p className="text-[10px] text-slate-500">Enable local LLM for full gap analysis.</p>
      )}
    </div>
  );
}
