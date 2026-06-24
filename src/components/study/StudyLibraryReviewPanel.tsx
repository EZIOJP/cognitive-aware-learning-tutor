import { Check, Code2, Loader2, RefreshCw } from "lucide-react";
import type { StudySessionItem } from "./studySessionTypes";
import { Button } from "../../app/components/ui/button";
import { cn } from "../../app/components/ui/utils";

type Props = {
  items: StudySessionItem[];
  compareCount: number;
  syncing?: boolean;
  onToggleApproved: (id: string) => void;
  onApproveAll: () => void;
  onFinalize?: () => void;
};

export function StudyLibraryReviewPanel({
  items,
  compareCount,
  syncing,
  onToggleApproved,
  onApproveAll,
  onFinalize,
}: Props) {
  const approvedCount = items.filter((i) => i.approved).length;
  const quizCount = items.filter((i) => i.kind === "quiz").length;
  const drillCount = items.filter((i) => i.kind === "exercise").length;
  const noteCount = items.filter((i) => i.kind === "note").length;

  return (
    <aside className="w-80 shrink-0 flex flex-col gap-3 min-h-0">
      <div className="study-library-glass rounded-xl p-4">
        <h3 className="text-white font-semibold mb-1">Final Batch Review</h3>
        <p className="text-xs text-slate-400 leading-relaxed">
          Approve generated quizzes and drills before saving to your library.
        </p>
      </div>

      <div className="study-library-glass rounded-xl p-3 flex-1 overflow-y-auto study-library-markdown-scroll flex flex-col gap-2 min-h-0">
        <div className="flex items-center justify-between pb-2 border-b border-slate-700/50 text-xs">
          <span className="text-slate-300">{approvedCount}/{items.length} approved</span>
          <button
            type="button"
            className="text-blue-400 hover:text-blue-300 flex items-center gap-1"
            onClick={onApproveAll}
          >
            <Check className="w-3.5 h-3.5" /> Approve all
          </button>
        </div>

        {items.length === 0 && (
          <p className="text-xs text-slate-500 py-4 text-center">
            Generate quiz or drills in the Intelligence Hub first.
          </p>
        )}

        {items.map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => onToggleApproved(item.id)}
            className={cn(
              "bg-slate-800/40 border rounded-lg p-3 flex items-center justify-between hover:bg-slate-700/30 transition-colors text-left w-full",
              item.approved ? "border-blue-500/40 bg-blue-500/10" : "border-slate-700/50",
            )}
          >
            <div className="flex items-center gap-3 min-w-0">
              <div
                className={cn(
                  "w-8 h-8 rounded flex items-center justify-center shrink-0 border text-xs font-bold font-mono",
                  item.kind === "quiz"
                    ? "bg-blue-500/10 text-blue-400 border-blue-500/20"
                    : item.kind === "exercise"
                      ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                      : "bg-slate-500/10 text-slate-300 border-slate-500/20",
                )}
              >
                {item.kind === "quiz" ? "Q" : item.kind === "exercise" ? <Code2 className="w-4 h-4" /> : "N"}
              </div>
              <div className="min-w-0">
                <p className="text-sm font-medium text-slate-200 truncate">{item.title}</p>
                <p className="text-xs text-slate-500 truncate">{item.detail}</p>
              </div>
            </div>
            <div
              className={cn(
                "w-4 h-4 border rounded shrink-0 flex items-center justify-center",
                item.approved ? "border-blue-400 bg-blue-500/30" : "border-slate-500",
              )}
            >
              {item.approved && <Check className="w-3 h-3 text-blue-300" />}
            </div>
          </button>
        ))}
      </div>

      <div className="study-library-glass rounded-xl p-4">
        <h3 className="text-white font-semibold mb-2">Finalize Session</h3>
        <div className="bg-slate-800/60 border border-slate-700/50 rounded-lg p-3 mb-3 text-xs text-slate-300">
          <span className="text-slate-400">Summary:</span>{" "}
          {items.length === 0
            ? "Nothing to save yet"
            : `${quizCount} quiz · ${drillCount} drills · ${noteCount} notes · ${approvedCount} approved`}
        </div>
        <Button
          type="button"
          className="w-full bg-emerald-600 hover:bg-emerald-500 shadow-[0_0_15px_rgba(16,185,129,0.35)] gap-2"
          disabled={approvedCount === 0 || syncing}
          onClick={onFinalize}
        >
          {syncing ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
          Finalize & Sync
        </Button>
        {compareCount < 2 && (
          <p className="text-[10px] text-slate-500 mt-2 text-center">Compare 2 files for full workflow</p>
        )}
      </div>
    </aside>
  );
}
