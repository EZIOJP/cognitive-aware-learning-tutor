import { useEffect, useState } from "react";
import { ClipboardPaste, Database, Loader2, PenLine, Sparkles, Trash2 } from "lucide-react";
import { Link } from "react-router";
import type { QuizFocus, QuizQuestion, CodeDrill, StudySessionItem, NoteTopicOption } from "./studySessionTypes";
import { Button } from "../../app/components/ui/button";

type Props = {
  comparePaths: string[];
  selectedNotePath?: string;
  compareCount: number;
  quizQuestions: QuizQuestion[];
  drills: CodeDrill[];
  sessionItems: StudySessionItem[];
  generating?: boolean;
  /** Optional status line from parent (e.g. "Calling quiz_gen…") */
  generatingDetail?: string | null;
  quizCount?: number;
  quizFocus?: QuizFocus;
  onQuizCountChange?: (n: number) => void;
  onQuizFocusChange?: (f: QuizFocus) => void;
  noteTopics?: NoteTopicOption[];
  selectedTopicIds?: string[];
  onSelectedTopicIdsChange?: (ids: string[]) => void;
  topicsLoading?: boolean;
  onGenerateQuiz: () => void;
  onGenerateDrills: () => void;
  onGeneratePrimer?: () => void;
  onPasteQuiz?: (text: string) => void;
  onRemoveQuestion?: (id: string) => void;
  corpusGroundedNotes?: boolean;
  onTakeQuiz?: () => void;
  onSync?: () => void;
  onEditItem: (id: string, content: string) => void;
};

function formatElapsed(sec: number): string {
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

function stageForElapsed(focus: QuizFocus, elapsedSec: number, tab: "quiz" | "code"): string {
  if (tab === "code") {
    if (elapsedSec < 15) return "Building drill prompts…";
    if (elapsedSec < 45) return "Waiting on AI for code drills…";
    return "Still working — large models can take a minute…";
  }
  if (elapsedSec < 20) return "1/4 Reading note topics…";
  if (elapsedSec < 60) return "2/4 Generating per-topic MCQs (small context)…";
  if (elapsedSec < 120) return "3/4 Combining + tagging for review…";
  if (elapsedSec < 180) return "4/4 Seeding SRS deck…";
  return "Still generating — topic loop can take a few minutes…";
}

export function StudyLibraryIntelligenceHub({
  comparePaths,
  selectedNotePath = "",
  compareCount,
  quizQuestions,
  drills,
  sessionItems,
  generating,
  generatingDetail = null,
  quizCount = 12,
  quizFocus = "mixed",
  onQuizCountChange,
  onQuizFocusChange,
  noteTopics = [],
  selectedTopicIds = [],
  onSelectedTopicIdsChange,
  topicsLoading = false,
  onGenerateQuiz,
  onGenerateDrills,
  onGeneratePrimer,
  onPasteQuiz,
  onRemoveQuestion,
  corpusGroundedNotes = false,
  onTakeQuiz,
  onSync,
  onEditItem,
}: Props) {
  const [tab, setTab] = useState<"quiz" | "code">("quiz");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editDraft, setEditDraft] = useState("");
  const [pasteOpen, setPasteOpen] = useState(false);
  const [pasteText, setPasteText] = useState("");
  const [elapsedSec, setElapsedSec] = useState(0);

  useEffect(() => {
    if (!generating) {
      setElapsedSec(0);
      return;
    }
    const started = Date.now();
    setElapsedSec(0);
    const id = window.setInterval(() => {
      setElapsedSec(Math.floor((Date.now() - started) / 1000));
    }, 500);
    return () => window.clearInterval(id);
  }, [generating]);

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

  const planHint =
    quizFocus === "concept"
      ? "Question style: concepts / definitions"
      : quizFocus === "coding"
        ? "Question style: coding / API"
        : "Question style: mixed concept + coding";

  const countOptions = noteTopics.length > 0 ? [12, 20, 30, 40, 50] : [5, 8, 10, 12, 15, 20, 25];

  const liveStage = generatingDetail?.trim() || stageForElapsed(quizFocus, elapsedSec, tab);
  const estCalls =
    noteTopics.length > 0
      ? Math.max(noteTopics.length, Math.ceil(quizCount / 2))
      : null;

  return (
    <section className="study-library-glass w-72 shrink-0 flex flex-col p-3 min-h-0">
      <div className="flex items-center justify-between mb-2">
        <h2 className="font-semibold text-sm text-foreground">Study tools</h2>
        <Link to="/ai-coach" className="text-primary hover:text-primary/80 text-xs">
          AI Coach
        </Link>
      </div>

      <div className="flex gap-2 mb-3">
        <button
          type="button"
          className="study-library-intel-tab flex-1 py-1.5 px-2 rounded-md text-xs font-medium border border-transparent text-muted-foreground"
          data-active={tab === "quiz"}
          onClick={() => setTab("quiz")}
        >
          Theoretical Quiz
        </button>
        <button
          type="button"
          className="study-library-intel-tab flex-1 py-1.5 px-2 rounded-md text-xs font-medium border border-transparent text-muted-foreground hover:bg-muted"
          data-active={tab === "code"}
          onClick={() => setTab("code")}
        >
          Code Drills
        </button>
      </div>

      <div className="shrink-0 mb-2 space-y-2">
        {tab === "quiz" && (
          <div className="space-y-1.5 rounded-md border border-border/60 bg-muted/20 p-2">
            <label className="flex items-center justify-between gap-2 text-[11px] text-muted-foreground">
              <span>Questions</span>
              <select
                className="h-7 rounded border border-border bg-background px-1.5 text-xs text-foreground"
                value={quizCount}
                disabled={generating}
                onChange={(e) => onQuizCountChange?.(Number(e.target.value))}
              >
                {countOptions.map((n) => (
                  <option key={n} value={n}>
                    {n}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex items-center justify-between gap-2 text-[11px] text-muted-foreground">
              <span>Style</span>
              <select
                className="h-7 rounded border border-border bg-background px-1.5 text-xs text-foreground"
                value={quizFocus === "cover_all" ? "mixed" : quizFocus}
                disabled={generating}
                onChange={(e) => onQuizFocusChange?.(e.target.value as QuizFocus)}
              >
                <option value="mixed">Mixed</option>
                <option value="concept">Concepts</option>
                <option value="coding">Coding / API</option>
              </select>
            </label>
            <p className="text-[10px] text-muted-foreground/80">{planHint}</p>
            <p className="text-[10px] text-foreground/80 leading-snug">
              Engine walks each topic with a <span className="font-medium">small context window</span>,
              then combines into one quiz — richer questions, tagged for spaced review.
            </p>
            {noteTopics.length > 0 && onSelectedTopicIdsChange && (
              <div className="rounded-md border border-border/60 bg-muted/20 p-2 space-y-1.5">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-[10px] font-medium text-foreground">
                    Topic filter{" "}
                    {selectedTopicIds.length
                      ? `(${selectedTopicIds.length} of ${noteTopics.length})`
                      : `(all ${noteTopics.length})`}
                  </p>
                  <div className="flex gap-1">
                    <button
                      type="button"
                      className="text-[10px] text-primary hover:underline"
                      disabled={generating || topicsLoading}
                      onClick={() => onSelectedTopicIdsChange(noteTopics.map((t) => t.topic_id))}
                    >
                      All
                    </button>
                    <span className="text-[10px] text-muted-foreground">·</span>
                    <button
                      type="button"
                      className="text-[10px] text-muted-foreground hover:underline"
                      disabled={generating || topicsLoading}
                      onClick={() => onSelectedTopicIdsChange([])}
                    >
                      Clear
                    </button>
                  </div>
                </div>
                <div className="max-h-36 overflow-y-auto space-y-0.5 pr-0.5">
                  {noteTopics.map((t) => {
                    const checked = selectedTopicIds.includes(t.topic_id);
                    return (
                      <label
                        key={t.topic_id}
                        className="flex items-start gap-1.5 text-[10px] leading-snug cursor-pointer rounded px-1 py-0.5 hover:bg-accent/40"
                      >
                        <input
                          type="checkbox"
                          className="mt-0.5"
                          checked={checked}
                          disabled={generating}
                          onChange={() => {
                            if (checked) {
                              onSelectedTopicIdsChange(selectedTopicIds.filter((id) => id !== t.topic_id));
                            } else {
                              onSelectedTopicIdsChange([...selectedTopicIds, t.topic_id]);
                            }
                          }}
                        />
                        <span>
                          <span className="font-mono text-foreground/90">{t.topic_id}</span>
                          <span className="text-muted-foreground"> — {t.title}</span>
                        </span>
                      </label>
                    );
                  })}
                </div>
                <p className="text-[10px] text-muted-foreground/80">
                  Leave clear to loop the whole note topic-by-topic. Filter only if you want a subset.
                </p>
              </div>
            )}
            {topicsLoading && (
              <p className="text-[10px] text-muted-foreground">Loading topics…</p>
            )}
          </div>
        )}

        {generating && (
          <div
            className="rounded-md border border-primary/30 bg-primary/5 p-2.5 space-y-1.5"
            role="status"
            aria-live="polite"
          >
            <div className="flex items-center gap-2 text-xs font-medium text-foreground">
              <Loader2 className="w-3.5 h-3.5 animate-spin text-primary shrink-0" />
              <span>
                {tab === "quiz"
                  ? noteTopics.length > 0
                    ? "Topic-loop quiz…"
                    : "Generating quiz…"
                  : "Generating drills…"}
              </span>
              <span className="ml-auto font-mono text-[10px] text-muted-foreground tabular-nums">
                {formatElapsed(elapsedSec)}
              </span>
            </div>
            <p className="text-[11px] text-foreground/90 leading-snug">{liveStage}</p>
            {tab === "quiz" && noteTopics.length > 0 && (
              <p className="text-[10px] text-muted-foreground">
                Target ~{quizCount} questions · ~{estCalls} topic calls · keep this tab open
              </p>
            )}
            {tab === "quiz" && noteTopics.length === 0 && (
              <p className="text-[10px] text-muted-foreground">
                Target {quizCount} questions · {planHint}
              </p>
            )}
            <div className="h-1 rounded-full bg-muted overflow-hidden">
              <div
                className="h-full bg-primary/70 transition-[width] duration-500 ease-out"
                style={{
                  width: `${Math.min(
                    92,
                    noteTopics.length > 0 ? 8 + elapsedSec * 0.4 : 12 + elapsedSec * 1.2,
                  )}%`,
                }}
              />
            </div>
          </div>
        )}

        {corpusGroundedNotes && onGeneratePrimer && (
          <Button
            type="button"
            size="sm"
            variant="secondary"
            className="w-full h-8 text-xs gap-1"
            disabled={generating}
            onClick={onGeneratePrimer}
          >
            {generating ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Database className="w-3.5 h-3.5" />
            )}
            Corpus primer (opt-in RAG)
          </Button>
        )}
        <Button
          type="button"
          size="sm"
          variant="outline"
          className="w-full h-8 text-xs border-border gap-1"
          disabled={generating || sourcePaths.length === 0}
          onClick={tab === "quiz" ? onGenerateQuiz : onGenerateDrills}
        >
          {generating ? (
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
          ) : (
            <Sparkles className="w-3.5 h-3.5" />
          )}
          {generating
            ? tab === "quiz"
              ? "Generating…"
              : "Working…"
            : tab === "quiz"
              ? noteTopics.length > 0
                ? "Generate quiz (topic loop)"
                : "Generate quiz"
              : "Generate drills"}
        </Button>
        {tab === "quiz" && onPasteQuiz && (
          <Button
            type="button"
            size="sm"
            variant="ghost"
            className="w-full h-8 text-xs gap-1"
            disabled={generating}
            onClick={() => setPasteOpen((v) => !v)}
          >
            <ClipboardPaste className="w-3.5 h-3.5" />
            Paste import
          </Button>
        )}
        {tab === "quiz" && pasteOpen && onPasteQuiz && (
          <div className="space-y-1.5">
            <textarea
              className="w-full h-24 text-[10px] bg-muted/40 border border-border rounded p-2 font-mono text-foreground"
              placeholder="Paste web/book MCQs (Question 1 … A) … B) …)"
              value={pasteText}
              onChange={(e) => setPasteText(e.target.value)}
            />
            <Button
              type="button"
              size="sm"
              className="w-full h-7 text-[10px]"
              disabled={pasteText.trim().length < 20 || generating}
              onClick={() => {
                onPasteQuiz(pasteText);
                setPasteText("");
                setPasteOpen(false);
              }}
            >
              Import into draft
            </Button>
          </div>
        )}
        {(tab === "quiz" ? quizQuestions.length > 0 : drills.length > 0) && onTakeQuiz && !generating && (
          <Button type="button" size="sm" className="w-full h-8 text-xs gap-1" onClick={onTakeQuiz}>
            Take quiz now
          </Button>
        )}
        {tab === "quiz" && quizQuestions.length > 0 && !generating && (
          <p className="text-[10px] text-muted-foreground px-0.5">
            Draft ready — review below, then take when you want.
          </p>
        )}
      </div>

      <div className="flex-1 overflow-y-auto study-library-markdown-scroll space-y-3 pr-1 min-h-0">
        {generating && tab === "quiz" && quizQuestions.length === 0 && (
          <p className="text-[11px] text-muted-foreground px-1 leading-relaxed">
            Draft will appear here when generation finishes. Bulk mode walks sections one by one —
            progress is shown above.
          </p>
        )}
        {tab === "quiz" &&
          (quizQuestions.length > 0 ? (
            quizQuestions.map((q, i) => (
              <div key={q.id} className="study-library-glass-card p-3">
                <div className="flex items-start justify-between gap-1 mb-1">
                  <p className="text-[10px] uppercase tracking-wide text-muted-foreground">
                    {q.concept || `Q${i + 1}`}
                  </p>
                  {onRemoveQuestion && !generating && (
                    <button
                      type="button"
                      className="text-muted-foreground hover:text-destructive p-0.5"
                      title="Remove from draft"
                      onClick={() => onRemoveQuestion(q.id)}
                    >
                      <Trash2 className="w-3 h-3" />
                    </button>
                  )}
                </div>
                <p className="text-sm text-foreground/90 mb-2">
                  Q{i + 1}: {q.question}
                </p>
                <div className="text-[11px] text-muted-foreground space-y-0.5">
                  {q.options.map((o, j) => (
                    <p key={j}>
                      {String.fromCharCode(65 + j)}. {o}
                    </p>
                  ))}
                </div>
              </div>
            ))
          ) : (
            !generating && (
              <p className="text-[11px] text-slate-500 px-1">
                Select a note and generate MCQs from your lecture notes (no corpus RAG). Generate fills a
                draft only — take the quiz when ready.
              </p>
            )
          ))}

        {tab === "code" &&
          (drills.length > 0 ? (
            drills.map((d) => (
              <div key={d.id} className="study-library-glass-card p-3 bg-[#282c34]/80 font-mono text-[11px]">
                <span className="text-[10px] text-blue-300 float-right">{d.language}</span>
                <p className="text-foreground font-sans text-sm mb-2">{d.title}</p>
                <p className="text-muted-foreground font-sans text-[11px] mb-2">{d.prompt}</p>
                <pre className="text-foreground/90 overflow-x-auto whitespace-pre-wrap">{d.starter_code}</pre>
              </div>
            ))
          ) : (
            !generating && (
              <p className="text-[11px] text-slate-500 px-1">
                Generate coding exercises from your selected notes.
              </p>
            )
          ))}

        {hubItems.map((item) => (
          <div key={item.id} className="study-library-glass-card p-2 border border-border">
            {editingId === item.id ? (
              <div className="space-y-1">
                <textarea
                  className="w-full h-24 text-[10px] bg-muted/40 border border-border rounded p-2 font-mono text-foreground"
                  value={editDraft}
                  onChange={(e) => setEditDraft(e.target.value)}
                />
                <Button type="button" size="sm" className="h-6 text-[10px]" onClick={saveEdit}>
                  Save
                </Button>
              </div>
            ) : (
              <>
                <p className="text-xs text-foreground truncate">{item.title}</p>
                <p className="text-[10px] text-slate-500">{item.detail}</p>
                <button
                  type="button"
                  className="mt-1 text-[10px] text-primary hover:text-primary flex items-center gap-1"
                  onClick={() => startEdit(item)}
                >
                  <PenLine className="w-3 h-3" /> Edit
                </button>
              </>
            )}
          </div>
        ))}
      </div>

      <div className="pt-3 mt-2 border-t border-border">
        <Button
          type="button"
          size="sm"
          className="w-full bg-primary hover:bg-primary/90 text-primary-foreground gap-2"
          disabled={compareCount < 2 || generating}
          onClick={onSync}
        >
          <Database className="w-4 h-4" />
          Continue to Review
        </Button>
        {compareCount >= 2 && (
          <p className="text-[10px] text-center text-primary/70 mt-2 flex items-center justify-center gap-1">
            <Sparkles className="w-3 h-3" />
            Gap analysis ready
          </p>
        )}
      </div>
    </section>
  );
}
