import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router";
import {
  AlertCircle,
  BookOpen,
  Brain,
  Calculator,
  Clock,
  Code2,
  Loader2,
  PenLine,
  Play,
  Plus,
  RefreshCw,
  Sparkles,
  Trash2,
} from "lucide-react";
import { Button } from "../../app/components/ui/button";
import {
  deleteQuizDeck,
  fetchDueReview,
  fetchQuizBacklog,
  fetchQuizDecks,
  fetchRecentQuizResults,
  saveQuizDeck,
} from "../../api/globalQuizClient";
import { GlobalQuizRunner } from "../../features/quiz/GlobalQuizRunner";
import type { DueReviewItem, QuizDeckSummary, QuizDomain } from "../../features/quiz/types";
import { useAuth } from "../../context/AuthContext";

type Tab = "due" | "start" | "decks" | "create" | "results";

type ActiveQuiz = {
  domain: QuizDomain;
  config: Record<string, unknown>;
};

const EMPTY_MCQ = () => ({
  id: `q${Date.now()}`,
  question: "",
  options: ["", "", "", ""],
  answer_index: 0,
  hint: "",
});

export function ReviewHubPage() {
  const { user } = useAuth();
  const [searchParams] = useSearchParams();
  const initialTab = (searchParams.get("tab") as Tab) || "due";
  const fromLectureNotes = searchParams.get("source") === "lecture_notes";
  const [tab, setTab] = useState<Tab>(initialTab);

  useEffect(() => {
    const t = searchParams.get("tab") as Tab | null;
    if (t) setTab(t);
  }, [searchParams]);
  const [due, setDue] = useState<DueReviewItem[]>([]);
  const [decks, setDecks] = useState<QuizDeckSummary[]>([]);
  const [results, setResults] = useState<
    Array<{
      session_id: string;
      domain: string;
      correct: number;
      total: number;
      accuracy_pct: number;
      completed_at?: string;
    }>
  >([]);
  const [backlog, setBacklog] = useState<{ due_count: number; total_cards: number } | null>(null);
  const [loading, setLoading] = useState(false);
  const [active, setActive] = useState<ActiveQuiz | null>(null);
  const [groupNumber, setGroupNumber] = useState(1);
  const [mathTopic, setMathTopic] = useState("Arithmetic");
  const [timeLimitMin, setTimeLimitMin] = useState(10);
  const [perQuestionSec, setPerQuestionSec] = useState(60);

  const [deckTitle, setDeckTitle] = useState("My custom quiz");
  const [deckTopic, setDeckTopic] = useState("");
  const [draftItems, setDraftItems] = useState([EMPTY_MCQ()]);
  const [savingDeck, setSavingDeck] = useState(false);

  const timeOpts = useMemo(
    () => ({
      time_limit_sec: timeLimitMin > 0 ? timeLimitMin * 60 : undefined,
      per_question_sec: perQuestionSec > 0 ? perQuestionSec : undefined,
    }),
    [timeLimitMin, perQuestionSec]
  );

  const refresh = async () => {
    if (!user) return;
    setLoading(true);
    try {
      const [dueRes, deckRes, resultRes, bl] = await Promise.all([
        fetchDueReview(),
        fetchQuizDecks(),
        fetchRecentQuizResults(),
        fetchQuizBacklog(),
      ]);
      setDue(dueRes.items);
      setDecks(deckRes.decks);
      setResults(resultRes.results);
      setBacklog({ due_count: bl.due_count, total_cards: bl.total_cards });
    } catch {
      setDue([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void refresh();
  }, [user]);

  const startDueReview = () => {
    setActive({
      domain: "review",
      config: { limit: 25, ...timeOpts },
    });
  };

  const handleSaveDeck = async () => {
    const items = draftItems.filter((q) => q.question.trim() && q.options.some((o) => o.trim()));
    if (!items.length) return;
    setSavingDeck(true);
    try {
      await saveQuizDeck({
        title: deckTitle,
        topic: deckTopic,
        domain: "study",
        items,
        time_limit_sec: timeOpts.time_limit_sec,
      });
      setDraftItems([EMPTY_MCQ()]);
      setTab("decks");
      await refresh();
    } finally {
      setSavingDeck(false);
    }
  };

  if (!user) {
    return (
      <div className="p-8 text-center text-muted-foreground space-y-3">
        <p>Sign in to use the global quiz handler and FSRS review queue.</p>
        <Button asChild>
          <Link to="/login">Sign in</Link>
        </Button>
      </div>
    );
  }

  if (active) {
    return (
      <div className="mx-auto max-w-2xl py-6">
        <GlobalQuizRunner
          domain={active.domain}
          config={active.config}
          onDone={() => {
            setActive(null);
            void refresh();
          }}
          onClose={() => setActive(null)}
        />
      </div>
    );
  }

  const tabs: { id: Tab; label: string }[] = [
    { id: "due", label: `Due (${backlog?.due_count ?? due.length})` },
    { id: "start", label: "Start quiz" },
    { id: "decks", label: "My decks" },
    { id: "create", label: "Create quiz" },
    { id: "results", label: "Results" },
  ];

  const dueCount = backlog?.due_count ?? due.length;
  const hasDue = dueCount > 0;
  const queueEmpty = !hasDue && (backlog?.total_cards ?? 0) === 0;

  return (
    <div className="mx-auto max-w-3xl space-y-6 p-6">
      <header>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight flex items-center gap-2">
              <Brain className="h-6 w-6 text-primary" /> Review Hub
            </h1>
            <p className="mt-1 text-sm text-muted-foreground">
              One quiz handler for vocab, math, lecture notes, and code — FSRS scheduling, time bounds, and custom decks.
            </p>
            <p className="mt-2 text-xs text-muted-foreground">
              <Link to="/lecture-notes" className="text-primary hover:underline">
                Lecture Notes
              </Link>
              {" · generate notes → quiz · cards land here automatically"}
            </p>
          </div>
          {hasDue && (
            <div
              className="review-hub-due-badge shrink-0 flex items-center gap-2 rounded-lg border-2 border-amber-500/70 bg-amber-500/15 px-3 py-2 shadow-sm"
              role="status"
              aria-live="polite"
            >
              <AlertCircle className="h-5 w-5 text-amber-600 dark:text-amber-400" />
              <div>
                <p className="text-sm font-semibold text-amber-900 dark:text-amber-100">
                  {dueCount} card{dueCount === 1 ? "" : "s"} due now
                </p>
                <p className="text-[10px] text-amber-800/80 dark:text-amber-200/80">Review to update FSRS</p>
              </div>
            </div>
          )}
        </div>
      </header>

      {fromLectureNotes && !hasDue && (
        <div className="gloss-panel rounded-xl p-4 border border-primary/30 flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-sm font-medium text-primary">Finish the learning loop</p>
            <p className="text-xs text-muted-foreground mt-1">
              After your quiz, cards appear here. No due items yet — generate and take a quiz from your latest
              lecture notes first.
            </p>
          </div>
          <Button size="sm" asChild>
            <Link to="/lecture-notes">
              <BookOpen className="h-4 w-4 mr-1" /> Back to Lecture Notes
            </Link>
          </Button>
        </div>
      )}

      {queueEmpty && !fromLectureNotes && tab === "due" && (
        <div className="gloss-panel rounded-xl p-4 border border-dashed border-primary/25">
          <p className="text-sm font-medium">Activate spaced repetition</p>
          <p className="text-xs text-muted-foreground mt-1 mb-3">
            You have lecture notes on disk, but no review cards yet. Open your latest note, use{" "}
            <strong className="text-foreground">Generate &amp; take quiz</strong>, then return here.
          </p>
          <Button size="sm" className="gap-1" asChild>
            <Link to="/lecture-notes">
              <Sparkles className="h-4 w-4" /> Test knowledge from latest notes
            </Link>
          </Button>
        </div>
      )}

      {hasDue && tab !== "due" && (
        <div className="rounded-xl border border-amber-500/50 bg-amber-500/10 px-4 py-3 flex flex-wrap items-center justify-between gap-2">
          <p className="text-sm text-amber-950 dark:text-amber-50">
            You have <strong>{dueCount}</strong> spaced-repetition cards waiting.
          </p>
          <Button size="sm" className="gap-1 bg-amber-600 hover:bg-amber-700 text-white" onClick={() => setTab("due")}>
            <Play className="h-4 w-4" /> Go to Due tab
          </Button>
        </div>
      )}

      <div className="flex flex-wrap gap-1 border-b pb-1">
        {tabs.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setTab(t.id)}
            className={`px-3 py-1.5 text-sm rounded-t-md transition ${
              tab === t.id
                ? t.id === "due" && hasDue
                  ? "bg-amber-500/20 text-amber-900 dark:text-amber-100 font-semibold border-b-2 border-amber-500"
                  : "bg-primary/10 text-primary font-medium"
                : t.id === "due" && hasDue
                  ? "text-amber-700 dark:text-amber-300 font-medium hover:bg-amber-500/10"
                  : "text-muted-foreground hover:text-foreground"
            }`}
          >
            {t.label}
          </button>
        ))}
        <Button variant="ghost" size="sm" className="ml-auto" onClick={() => void refresh()} disabled={loading}>
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
        </Button>
      </div>

      <section className="gloss-panel rounded-xl p-4 flex flex-wrap gap-4 items-end text-sm">
        <label className="space-y-1">
          <span className="text-xs text-muted-foreground flex items-center gap-1">
            <Clock className="h-3 w-3" /> Session limit (min)
          </span>
          <input
            type="number"
            min={0}
            max={120}
            value={timeLimitMin}
            onChange={(e) => setTimeLimitMin(Number(e.target.value) || 0)}
            className="w-20 rounded border bg-background px-2 py-1"
          />
        </label>
        <label className="space-y-1">
          <span className="text-xs text-muted-foreground">Per question (sec)</span>
          <input
            type="number"
            min={0}
            max={300}
            value={perQuestionSec}
            onChange={(e) => setPerQuestionSec(Number(e.target.value) || 0)}
            className="w-20 rounded border bg-background px-2 py-1"
          />
        </label>
        <p className="text-xs text-muted-foreground flex-1 min-w-[200px]">
          Applies to quizzes started from this page. 0 = no limit.
        </p>
      </section>

      {tab === "due" && (
        <section
          className={`gloss-panel rounded-xl p-5 space-y-3 ${
            hasDue ? "ring-2 ring-amber-500/60 border-amber-500/30 bg-amber-500/5" : ""
          }`}
        >
          <div className="flex items-center justify-between gap-2 flex-wrap">
            <div className="flex items-center gap-2">
              <h2 className="font-medium">Spaced repetition queue</h2>
              {hasDue && (
                <span className="text-[10px] font-semibold uppercase tracking-wide rounded-full bg-amber-500/25 text-amber-900 dark:text-amber-100 px-2 py-0.5 border border-amber-500/40">
                  Action needed
                </span>
              )}
            </div>
            {due.length > 0 && (
              <Button
                size="sm"
                onClick={startDueReview}
                className="gap-1 bg-amber-600 hover:bg-amber-700 text-white shadow-sm"
              >
                <Play className="h-4 w-4" /> Review all due ({due.length})
              </Button>
            )}
          </div>
          {due.length === 0 ? (
            <div className="rounded-lg border border-dashed p-4 space-y-3 text-sm text-muted-foreground">
              <p>Nothing due yet. Each quiz answer creates a review card automatically.</p>
              <ol className="list-decimal ml-5 space-y-1 text-xs">
                <li>
                  <Link to="/lecture-notes" className="text-primary hover:underline">
                    Lecture Notes
                  </Link>{" "}
                  → open a note → Generate quiz
                </li>
                <li>Take the quiz (Intelligence Hub → Take quiz now)</li>
                <li>Return here — due cards appear after your first session</li>
              </ol>
              <Button size="sm" variant="outline" asChild>
                <Link to="/lecture-notes">
                  <BookOpen className="h-4 w-4 mr-1" /> Start at Lecture Notes
                </Link>
              </Button>
            </div>
          ) : (
            <ul className="divide-y rounded-lg border border-amber-500/25 overflow-hidden">
              {due.map((item) => (
                <li
                  key={`${item.domain}-${item.card_id ?? item.item_id}`}
                  className="flex items-center justify-between gap-2 px-3 py-2.5 text-sm bg-background/60 border-l-4 border-l-amber-500/80 hover:bg-amber-500/5 transition-colors"
                >
                  <div className="min-w-0">
                    <span className="text-xs uppercase text-muted-foreground mr-2">{item.domain}</span>
                    <span className="truncate">{item.label}</span>
                    <span className="ml-2 text-xs text-muted-foreground">
                      m{item.mastery}
                      {item.stability != null && ` · S${item.stability}`}
                    </span>
                  </div>
                  <Button
                    size="sm"
                    variant="outline"
                    className="border-amber-500/40 hover:bg-amber-500/15"
                    onClick={() =>
                      setActive({
                        domain: "review",
                        config: { limit: 1, domains: [item.domain], ...timeOpts },
                      })
                    }
                  >
                    Review
                  </Button>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      {tab === "start" && (
        <section className="gloss-panel rounded-xl p-5 space-y-4">
          <h2 className="font-medium">Start a timed quiz</h2>
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="rounded-lg border p-3 space-y-2">
              <div className="flex items-center gap-2 text-sm font-medium">
                <BookOpen className="h-4 w-4" /> Vocab group
              </div>
              <input
                type="number"
                min={1}
                value={groupNumber}
                onChange={(e) => setGroupNumber(Number(e.target.value) || 1)}
                className="w-full rounded border bg-background px-2 py-1 text-sm"
              />
              <Button
                size="sm"
                onClick={() =>
                  setActive({
                    domain: "vocab",
                    config: { group_number: groupNumber, ...timeOpts },
                  })
                }
              >
                Quiz group
              </Button>
            </div>
            <div className="rounded-lg border p-3 space-y-2">
              <div className="flex items-center gap-2 text-sm font-medium">
                <Calculator className="h-4 w-4" /> Math topic
              </div>
              <input
                value={mathTopic}
                onChange={(e) => setMathTopic(e.target.value)}
                className="w-full rounded border bg-background px-2 py-1 text-sm"
              />
              <Button
                size="sm"
                onClick={() =>
                  setActive({ domain: "math", config: { topic: mathTopic, ...timeOpts } })
                }
              >
                Practice problem
              </Button>
            </div>
          </div>
          <p className="text-xs text-muted-foreground flex items-center gap-1">
            <Code2 className="h-3 w-3" /> Study & code quizzes:{" "}
            <Link to="/lecture-notes" className="text-primary hover:underline">
              Lecture Notes
            </Link>{" "}
            → Intelligence Hub → Generate quiz → Take quiz
          </p>
        </section>
      )}

      {tab === "decks" && (
        <section className="gloss-panel rounded-xl p-5 space-y-3">
          <h2 className="font-medium">My quiz decks</h2>
          {decks.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No custom decks yet. Use the Create tab to build your own MCQ set.
            </p>
          ) : (
            <ul className="divide-y rounded-lg border">
              {decks.map((d) => (
                <li key={d.id} className="flex items-center justify-between px-3 py-2 text-sm gap-2">
                  <div>
                    <p className="font-medium">{d.title}</p>
                    <p className="text-xs text-muted-foreground">
                      {d.item_count} questions · {d.domain}
                      {d.time_limit_sec ? ` · ${Math.round(d.time_limit_sec / 60)}m limit` : ""}
                    </p>
                  </div>
                  <div className="flex gap-1">
                    <Button size="sm" onClick={() => setActive({ domain: "deck", config: { deck_id: d.id } })}>
                      Play
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={async () => {
                        await deleteQuizDeck(d.id);
                        void refresh();
                      }}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      {tab === "create" && (
        <section className="gloss-panel rounded-xl p-5 space-y-4">
          <h2 className="font-medium flex items-center gap-2">
            <PenLine className="h-4 w-4" /> Create custom quiz
          </h2>
          <input
            value={deckTitle}
            onChange={(e) => setDeckTitle(e.target.value)}
            placeholder="Deck title"
            className="w-full rounded border bg-background px-3 py-2 text-sm"
          />
          <input
            value={deckTopic}
            onChange={(e) => setDeckTopic(e.target.value)}
            placeholder="Topic (optional)"
            className="w-full rounded border bg-background px-3 py-2 text-sm"
          />
          {draftItems.map((q, qi) => (
            <div key={q.id} className="rounded-lg border p-3 space-y-2">
              <input
                value={q.question}
                onChange={(e) => {
                  const next = [...draftItems];
                  next[qi] = { ...q, question: e.target.value };
                  setDraftItems(next);
                }}
                placeholder={`Question ${qi + 1}`}
                className="w-full rounded border bg-background px-2 py-1 text-sm"
              />
              {q.options.map((opt, oi) => (
                <div key={oi} className="flex items-center gap-2">
                  <input
                    type="radio"
                    name={`ans-${q.id}`}
                    checked={q.answer_index === oi}
                    onChange={() => {
                      const next = [...draftItems];
                      next[qi] = { ...q, answer_index: oi };
                      setDraftItems(next);
                    }}
                  />
                  <input
                    value={opt}
                    onChange={(e) => {
                      const next = [...draftItems];
                      const opts = [...q.options];
                      opts[oi] = e.target.value;
                      next[qi] = { ...q, options: opts };
                      setDraftItems(next);
                    }}
                    placeholder={`Option ${String.fromCharCode(65 + oi)}`}
                    className="flex-1 rounded border bg-background px-2 py-1 text-xs"
                  />
                </div>
              ))}
              <input
                value={q.hint}
                onChange={(e) => {
                  const next = [...draftItems];
                  next[qi] = { ...q, hint: e.target.value };
                  setDraftItems(next);
                }}
                placeholder="Hint (optional)"
                className="w-full rounded border bg-background px-2 py-1 text-xs"
              />
            </div>
          ))}
          <div className="flex gap-2">
            <Button type="button" variant="outline" size="sm" onClick={() => setDraftItems((p) => [...p, EMPTY_MCQ()])}>
              <Plus className="h-4 w-4 mr-1" /> Add question
            </Button>
            <Button type="button" size="sm" disabled={savingDeck} onClick={() => void handleSaveDeck()}>
              {savingDeck ? <Loader2 className="h-4 w-4 animate-spin" /> : "Save deck & seed review cards"}
            </Button>
          </div>
        </section>
      )}

      {tab === "results" && (
        <section className="gloss-panel rounded-xl p-5 space-y-3">
          <h2 className="font-medium">Recent quiz results</h2>
          {results.length === 0 ? (
            <p className="text-sm text-muted-foreground">Complete a quiz to see results here.</p>
          ) : (
            <ul className="divide-y rounded-lg border text-sm">
              {results.map((r) => (
                <li key={r.session_id} className="flex justify-between px-3 py-2">
                  <span>
                    <span className="text-xs uppercase text-muted-foreground mr-2">{r.domain}</span>
                    {r.correct}/{r.total} ({r.accuracy_pct}%)
                  </span>
                  <span className="text-xs text-muted-foreground">
                    {r.completed_at ? new Date(r.completed_at).toLocaleString() : ""}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}
    </div>
  );
}
