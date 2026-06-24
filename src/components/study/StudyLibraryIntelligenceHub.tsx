import { useState } from "react";
import { Database, Loader2, PenLine, Sparkles } from "lucide-react";
import { Link } from "react-router";
import type { QuizQuestion, CodeDrill, StudySessionItem } from "./studySessionTypes";
import { Button } from "../../app/components/ui/button";
import { cn } from "../../app/components/ui/utils";

type Props = {
  comparePaths: string[];
  selectedNotePath?: string;
  compareCount: number;
  quizQuestions: QuizQuestion[];
  drills: CodeDrill[];
  sessionItems: StudySessionItem[];
  generating?: boolean;
  onGenerateQuiz: () => void;
  onGenerateDrills: () => void;
  onTakeQuiz?: () => void;
  onSync?: () => void;
  onEditItem: (id: string, content: string) => void;
};

export function StudyLibraryIntelligenceHub({
  comparePaths,
  selectedNotePath = "",
  compareCount,
  quizQuestions,
  drills,
  sessionItems,
  generating,
  onGenerateQuiz,
  onGenerateDrills,
  onTakeQuiz,
  onSync,
  onEditItem,
}: Props) {
  const [tab, setTab] = useState<"quiz" | "code">("quiz");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editDraft, setEditDraft] = useState("");

  const sourcePaths =
    comparePaths.length >= 2
      ? comparePaths
      : comparePaths.length === 1
        ? comparePaths
        : selectedNotePath
          ? [selectedNotePath]
          : [];

  const startEdit = (item: StudySessionItem) => {
    setEditingId(item.id);
    setEditDraft(item.content);
  };

  const saveEdit = () => {
    if (editingId) onEditItem(editingId, editDraft);
    setEditingId(null);
  };

  const hubItems = sessionItems.filter((i) => (tab === "quiz" ? i.kind === "quiz" : i.kind === "exercise"));

  return (
    <section className="study-library-glass w-72 shrink-0 flex flex-col p-3 min-h-0">
      <div className="flex items-center justify-between mb-2">
        <h2 className="font-semibold text-sm text-white">Study tools</h2>
        <Link to="/ai-coach" className="text-emerald-400 hover:text-white text-xs">
          AI Coach
        </Link>
      </div>

      <div className="flex gap-2 mb-3">
        <button
          type="button"
          className="study-library-intel-tab flex-1 py-1.5 px-2 rounded-md text-xs font-medium border border-transparent text-emerald-100/80"
          data-active={tab === "quiz"}
          onClick={() => setTab("quiz")}
        >
          Theoretical Quiz
        </button>
        <button
          type="button"
          className="study-library-intel-tab flex-1 py-1.5 px-2 rounded-md text-xs font-medium border border-transparent text-emerald-100/80 hover:bg-emerald-900/20"
          data-active={tab === "code"}
          onClick={() => setTab("code")}
        >
          Code Drills
        </button>
      </div>

      <div className="shrink-0 mb-2">
        <Button
          type="button"
          size="sm"
          variant="outline"
          className="w-full h-8 text-xs border-emerald-800/50 gap-1"
          disabled={generating || sourcePaths.length === 0}
          onClick={tab === "quiz" ? onGenerateQuiz : onGenerateDrills}
        >
          {generating ? (
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
          ) : (
            <Sparkles className="w-3.5 h-3.5" />
          )}
          {tab === "quiz" ? "Generate quiz" : "Generate drills"}
        </Button>
        {(tab === "quiz" ? quizQuestions.length > 0 : drills.length > 0) && onTakeQuiz && (
          <Button
            type="button"
            size="sm"
            className="w-full h-8 text-xs mt-2 gap-1"
            onClick={onTakeQuiz}
          >
            Take quiz now
          </Button>
        )}
      </div>

      <div className="flex-1 overflow-y-auto study-library-markdown-scroll space-y-3 pr-1 min-h-0">
        {tab === "quiz" &&
          (quizQuestions.length > 0 ? (
            quizQuestions.map((q, i) => (
              <div key={q.id} className="study-library-glass-card p-3">
                <p className="text-sm text-emerald-50/90 mb-2">
                  Q{i + 1}: {q.question}
                </p>
                <div className="text-[11px] text-emerald-200/70 space-y-0.5">
                  {q.options.map((o, j) => (
                    <p key={j}>
                      {String.fromCharCode(65 + j)}. {o}
                    </p>
                  ))}
                </div>
              </div>
            ))
          ) : (
            <p className="text-[11px] text-slate-500 px-1">
              Select notes and generate MCQs from lecture + reference content.
            </p>
          ))}

        {tab === "code" &&
          (drills.length > 0 ? (
            drills.map((d) => (
              <div key={d.id} className="study-library-glass-card p-3 bg-[#282c34]/80 font-mono text-[11px]">
                <span className="text-[10px] text-blue-300 float-right">{d.language}</span>
                <p className="text-emerald-100 font-sans text-sm mb-2">{d.title}</p>
                <p className="text-emerald-200/80 font-sans text-[11px] mb-2">{d.prompt}</p>
                <pre className="text-emerald-100/90 overflow-x-auto whitespace-pre-wrap">{d.starter_code}</pre>
              </div>
            ))
          ) : (
            <p className="text-[11px] text-slate-500 px-1">Generate coding exercises from your selected notes.</p>
          ))}

        {hubItems.map((item) => (
          <div key={item.id} className="study-library-glass-card p-2 border border-emerald-800/30">
            {editingId === item.id ? (
              <div className="space-y-1">
                <textarea
                  className="w-full h-24 text-[10px] bg-black/30 border border-emerald-900/40 rounded p-2 font-mono text-emerald-100"
                  value={editDraft}
                  onChange={(e) => setEditDraft(e.target.value)}
                />
                <Button type="button" size="sm" className="h-6 text-[10px]" onClick={saveEdit}>
                  Save
                </Button>
              </div>
            ) : (
              <>
                <p className="text-xs text-emerald-100 truncate">{item.title}</p>
                <p className="text-[10px] text-slate-500">{item.detail}</p>
                <button
                  type="button"
                  className="mt-1 text-[10px] text-emerald-400 hover:text-emerald-300 flex items-center gap-1"
                  onClick={() => startEdit(item)}
                >
                  <PenLine className="w-3 h-3" /> Edit
                </button>
              </>
            )}
          </div>
        ))}
      </div>

      <div className="pt-3 mt-2 border-t border-emerald-900/40">
        <Button
          type="button"
          size="sm"
          className="w-full bg-gradient-to-r from-emerald-600 to-emerald-500 hover:from-emerald-500 hover:to-emerald-400 gap-2"
          disabled={compareCount < 2}
          onClick={onSync}
        >
          <Database className="w-4 h-4" />
          Continue to Review
        </Button>
        {compareCount >= 2 && (
          <p className="text-[10px] text-center text-emerald-300/70 mt-2 flex items-center justify-center gap-1">
            <Sparkles className="w-3 h-3" />
            Gap analysis ready
          </p>
        )}
      </div>
    </section>
  );
}
