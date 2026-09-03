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
import { getVocabToken } from "../../api/vocabClient";
import { resolveApiUrl } from "../../utils/resolveBackendUrl";
import {
  deleteQuizDeck,
  fetchContentCatalog,
  fetchDueReview,
  fetchMathCurriculum,
  fetchQuizBacklog,
  fetchQuizDecks,
  fetchRecentQuizResults,
  importContentBank,
  saveQuizDeck,
  syncContentBankToDb,
  type ContentTopicSummary,
  type GeneratorRecipeSummary,
} from "../../api/globalQuizClient";
import { llmBodyFieldsForTask } from "../../api/transcriptsClient";
import { GlobalQuizRunner } from "../../features/quiz/GlobalQuizRunner";
import { LoopTab } from "../../features/quiz/studyLoop/LoopTab";
import type { DueReviewItem, QuizDeckSummary, QuizDomain } from "../../features/quiz/types";
import { useAuth } from "../../context/AuthContext";

type Tab = "due" | "loop" | "start" | "decks" | "create" | "results";

type ActiveQuiz =
  | { mode: "start"; domain: QuizDomain; config: Record<string, unknown> }
  | { mode: "resume"; sessionId: string };

type MathSkillNode = {
  id: string;
  title: string;
  status: string;
  layer?: number;
};

const EMPTY_MCQ = () => ({
  id: `q${Date.now()}`,
  question: "",
  options: ["", "", "", ""],
  answer_index: 0,
  hint: "",
});

export function ReviewHubPage() {
  const { user, sessionReady } = useAuth();
  const [searchParams] = useSearchParams();
  const initialTab = (searchParams.get("tab") as Tab) || "due";
  const fromLectureNotes = searchParams.get("source") === "lecture_notes";
  const resumeSession = searchParams.get("session");
  const mathNodeParam = searchParams.get("math_node");
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
  const [backlog, setBacklog] = useState<{
    due_count: number;
    total_cards: number;
    weak_topics?: string[];
  } | null>(null);
  const [loading, setLoading] = useState(false);
  const [active, setActive] = useState<ActiveQuiz | null>(null);
  const [groupNumber, setGroupNumber] = useState(1);
  const [mathTopic, setMathTopic] = useState("Arithmetic");
  const [mathNodeId, setMathNodeId] = useState(mathNodeParam || "times_1_20");
  const [mathCount, setMathCount] = useState(5);
  const [mathSkills, setMathSkills] = useState<MathSkillNode[]>([]);
  const [contentTopics, setContentTopics] = useState<ContentTopicSummary[]>([]);
  const [generators, setGenerators] = useState<GeneratorRecipeSummary[]>([]);
  const [generatorTopicId, setGeneratorTopicId] = useState("");
  const [contentStats, setContentStats] = useState<{
    question_count: number;
    topic_count: number;
    generator_count: number;
    db_question_count: number;
  } | null>(null);
  const [contentTopicId, setContentTopicId] = useState("");
  const [contentNoteTag, setContentNoteTag] = useState("");
  const [curriculumSteps, setCurriculumSteps] = useState<
    Array<{ order: number; note_topic_id: string; title: string; prefer_topic_ids: string[] }>
  >([]);
  const [seedingContent, setSeedingContent] = useState(false);
  const [notePath, setNotePath] = useState("");
  const [noteQuizCount, setNoteQuizCount] = useState(5);
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
      setBacklog({
        due_count: bl.due_count,
        total_cards: bl.total_cards,
        weak_topics: bl.weak_topics,
      });
      try {
        const token = getVocabToken();
        const res = await fetch(`${resolveApiUrl()}/api/math/skills`, {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        });
        if (res.ok) {
          const data = (await res.json()) as { nodes?: MathSkillNode[]; next_node_id?: string };
          setMathSkills(data.nodes || []);
          if (data.next_node_id && !mathNodeParam) {
            setMathNodeId(data.next_node_id);
          }
        }
      } catch {
        /* skills optional */
      }
      try {
        const [cat, cur] = await Promise.all([
          fetchContentCatalog({ kind: "math" }),
          fetchMathCurriculum().catch(() => null),
        ]);
        setContentTopics(cat.topics || []);
        setGenerators(cat.generators || []);
        setContentStats({
          question_count: cat.question_count || 0,
          topic_count: cat.topic_count || 0,
          generator_count: cat.generator_count || cat.generators?.length || 0,
          db_question_count: cat.db_question_count || 0,
        });
        if (!contentTopicId && cat.topics?.length) {
          setContentTopicId(cat.topics[0].topic_id);
        }
        if (!generatorTopicId && cat.generators?.length) {
          setGeneratorTopicId(cat.generators[0].topic_id);
        }
        if (cur?.levels?.length) {
          const steps = cur.levels.flatMap((l) =>
            (l.steps || []).map((s) => ({
              order: s.order,
              note_topic_id: s.note_topic_id,
              title: s.title,
              prefer_topic_ids: s.prefer_topic_ids || [],
            }))
          );
          setCurriculumSteps(steps);
          if (!contentNoteTag && steps[0]) {
            setContentNoteTag(steps[0].note_topic_id);
          }
        }
      } catch {
        setContentTopics([]);
        setGenerators([]);
        setContentStats(null);
      }
    } catch {
      setDue([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void refresh();
  }, [user]);

  useEffect(() => {
    if (resumeSession) {
      setActive({ mode: "resume", sessionId: resumeSession });
    }
  }, [resumeSession]);

  useEffect(() => {
    if (mathNodeParam) {
      setMathNodeId(mathNodeParam);
      setTab("start");
    }
  }, [mathNodeParam]);

  const startDueReview = () => {
    setActive({
      mode: "start",
      domain: "review",
      config: { limit: 25, ...timeOpts },
    });
  };

  const startAutoGenerateFromNote = () => {
    const path = notePath.trim();
    if (!path) return;
    setActive({
      mode: "start",
      domain: "study",
      config: {
        note_path: path,
        topic: path.split("/").pop()?.replace(/\.md$/i, "") ?? "Study",
        count: noteQuizCount,
        auto_generate: true,
        expand_siblings: true,
        // Same global AI prefs / quiz_gen tier as Lecture Notes generate-quiz
        ...llmBodyFieldsForTask("quiz_gen"),
        ...timeOpts,
      },
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

  if (!sessionReady) {
    return (
      <div className="p-8 text-center text-muted-foreground">
        Loading review queue…
      </div>
    );
  }

  if (!user) {
    return (
      <div className="p-8 text-center text-muted-foreground space-y-3">
        <p>Start the local API with run.bat, then refresh to use Study Loop.</p>
        <Button asChild>
          <Link to="/">Dashboard</Link>
        </Button>
      </div>
    );
  }

  if (active) {
    return (
      <div
        className={`mx-auto py-6 ${
          active.mode === "resume" || (active.mode === "start" && active.domain === "math")
            ? "max-w-3xl"
            : "max-w-2xl"
        }`}
      >
        {active.mode === "resume" ? (
          <GlobalQuizRunner
            sessionId={active.sessionId}
            navigateOnComplete={false}
            onDone={() => {
              setActive(null);
              void refresh();
            }}
            onClose={() => setActive(null)}
          />
        ) : (
          <GlobalQuizRunner
            domain={active.domain}
            config={active.config}
            navigateOnComplete={false}
            onDone={() => {
              setActive(null);
              void refresh();
            }}
            onClose={() => setActive(null)}
          />
        )}
      </div>
    );
  }

  const tabs: { id: Tab; label: string }[] = [
    { id: "due", label: `Due (${backlog?.due_count ?? due.length})` },
    { id: "loop", label: "Loop" },
    { id: "start", label: "Learn" },
    { id: "decks", label: "Flash decks" },
    { id: "create", label: "Create deck" },
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
              <Brain className="h-6 w-6 text-primary" /> Study Loop
            </h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Daily Learn — vocab · lecture · core math (live) · flash decks — then FSRS until you get them right.
            </p>
            <p className="mt-2 text-xs text-muted-foreground">
              <Link to="/lecture-notes" className="text-primary hover:underline">
                Lecture Notes
              </Link>
              {" · "}
              <Link to="/gre-vocab" className="text-primary hover:underline">
                GRE Vocab
              </Link>
              {" · wrong answers reappear until correct"}
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

      {(backlog?.weak_topics?.length ?? 0) > 0 && (
        <div className="gloss-panel rounded-xl p-3 text-xs text-muted-foreground">
          <span className="font-medium text-foreground">Weak topics (from recent misses):</span>{" "}
          {backlog!.weak_topics!.slice(0, 8).join(" · ")}
        </div>
      )}

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

      {tab === "loop" && (
        <LoopTab
          onStartPractice={(sessionId) => {
            setActive({ mode: "resume", sessionId });
          }}
        />
      )}

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
                        mode: "start",
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
          <h2 className="font-medium">Today&apos;s learn tasks</h2>
          <p className="text-xs text-muted-foreground">
            Vocab + lecture quizzes seed FSRS. Core math uses live mathgenerator — misses get more of the same until you learn them.
          </p>

          <div className="rounded-lg border-2 border-primary/40 bg-primary/10 p-3 space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="text-sm font-medium">Core math drill (adaptive live)</div>
              <span className="text-[11px] text-muted-foreground">
                aptitude generators only · wrong → retry + more of that type
              </span>
            </div>
            <div className="flex flex-wrap gap-2 items-center">
              <label className="text-xs text-muted-foreground whitespace-nowrap">Questions</label>
              <input
                type="number"
                min={5}
                max={40}
                value={mathCount}
                onChange={(e) => setMathCount(Number(e.target.value) || 15)}
                className="w-16 rounded border bg-background px-2 py-1 text-sm"
              />
              <Button
                size="sm"
                onClick={() =>
                  setActive({
                    mode: "start",
                    domain: "math",
                    config: {
                      adaptive_aptitude: true,
                      core_math_drill: true,
                      count: mathCount,
                      boost_note_topics: contentNoteTag ? [contentNoteTag] : undefined,
                      ...timeOpts,
                    },
                  })
                }
              >
                Start adaptive core math
              </Button>
            </div>
          </div>

          <div className="rounded-lg border border-primary/30 bg-primary/5 p-3 space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2 text-sm font-medium">
                <Brain className="h-4 w-4" /> Curated packs + single generator
              </div>
              {contentStats && (
                <span className="text-[11px] text-muted-foreground">
                  {contentStats.question_count.toLocaleString()} curated · {contentStats.generator_count}{" "}
                  generators · DB {contentStats.db_question_count.toLocaleString()}
                </span>
              )}
            </div>
            {!contentTopics.length && !generators.length ? (
              <p className="text-xs text-muted-foreground">
                No packs or generators loaded. Confirm API is running and{" "}
                <code className="text-foreground">data/questions/math/</code> + mathgenerator clone exist.
              </p>
            ) : (
              <>
                <div className="grid gap-2 sm:grid-cols-2">
                  <div className="space-y-1">
                    <label className="text-[11px] text-muted-foreground">Daily Path step (MT tag)</label>
                    <select
                      value={contentNoteTag}
                      onChange={(e) => setContentNoteTag(e.target.value)}
                      className="w-full rounded border bg-background px-2 py-1.5 text-sm"
                    >
                      {(curriculumSteps.length
                        ? curriculumSteps
                        : Array.from(
                            new Set(
                              [
                                ...contentTopics.flatMap((t) => t.note_topic_ids || []),
                                ...generators.flatMap((g) => g.note_topic_ids || []),
                              ].filter(Boolean)
                            )
                          ).map((tag) => ({
                            order: 0,
                            note_topic_id: tag,
                            title: tag,
                            prefer_topic_ids: [] as string[],
                          }))
                      ).map((s) => (
                        <option key={`${s.order}-${s.note_topic_id}`} value={s.note_topic_id}>
                          {s.order ? `${s.order}. ` : ""}
                          {s.note_topic_id} — {s.title}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="space-y-1">
                    <label className="text-[11px] text-muted-foreground">Curated pack</label>
                    <select
                      value={contentTopicId}
                      onChange={(e) => setContentTopicId(e.target.value)}
                      className="w-full rounded border bg-background px-2 py-1.5 text-sm"
                    >
                      {contentTopics.map((t) => (
                        <option key={t.topic_id} value={t.topic_id}>
                          {t.title} ({t.question_count ?? "?"}) · {(t.note_topic_ids || []).join(",") || "—"}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="space-y-1 sm:col-span-2">
                    <label className="text-[11px] text-muted-foreground">
                      On-demand generator (indexes into DB when served)
                    </label>
                    <select
                      value={generatorTopicId}
                      onChange={(e) => setGeneratorTopicId(e.target.value)}
                      className="w-full rounded border bg-background px-2 py-1.5 text-sm"
                    >
                      {generators
                        .filter(
                          (g) =>
                            !contentNoteTag ||
                            (g.note_topic_ids || []).includes(contentNoteTag)
                        )
                        .map((g) => (
                          <option key={g.topic_id} value={g.topic_id}>
                            #{g.gen_id} {g.title} · {(g.note_topic_ids || []).join(",") || "—"}
                          </option>
                        ))}
                    </select>
                  </div>
                </div>
                <div className="flex flex-wrap gap-2 items-center">
                  <label className="text-xs text-muted-foreground whitespace-nowrap">Questions</label>
                  <input
                    type="number"
                    min={1}
                    max={40}
                    value={mathCount}
                    onChange={(e) => setMathCount(Number(e.target.value) || 10)}
                    className="w-16 rounded border bg-background px-2 py-1 text-sm"
                  />
                  <Button
                    size="sm"
                    onClick={() => {
                      const step = curriculumSteps.find((s) => s.note_topic_id === contentNoteTag);
                      if (step?.prefer_topic_ids?.length) {
                        setActive({
                          mode: "start",
                          domain: "math",
                          config: {
                            note_topic_id: contentNoteTag,
                            prefer_topic_ids: step.prefer_topic_ids,
                            count: mathCount,
                            ...timeOpts,
                          },
                        });
                        return;
                      }
                      setActive({
                        mode: "start",
                        domain: "math",
                        config: {
                          note_topic_id: contentNoteTag || undefined,
                          count: mathCount,
                          ...timeOpts,
                        },
                      });
                    }}
                    disabled={!contentNoteTag && !contentTopicId}
                  >
                    Start Daily Path step
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() =>
                      setActive({
                        mode: "start",
                        domain: "math",
                        config: { topic_id: contentTopicId, count: mathCount, ...timeOpts },
                      })
                    }
                    disabled={!contentTopicId}
                  >
                    Start curated pack
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() =>
                      setActive({
                        mode: "start",
                        domain: "math",
                        config: {
                          topic_id: generatorTopicId,
                          use_generator: true,
                          count: mathCount,
                          ...timeOpts,
                        },
                      })
                    }
                    disabled={!generatorTopicId}
                  >
                    Generate live
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    disabled={seedingContent}
                    onClick={async () => {
                      setSeedingContent(true);
                      try {
                        await syncContentBankToDb("math");
                        await importContentBank({ kind: "math" });
                        await refresh();
                      } finally {
                        setSeedingContent(false);
                      }
                    }}
                  >
                    {seedingContent ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}
                    Sync curated → DB
                  </Button>
                </div>
              </>
            )}
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <div className="rounded-lg border p-3 space-y-2">
              <div className="flex items-center gap-2 text-sm font-medium">
                <Calculator className="h-4 w-4" /> Math skill
              </div>
              <select
                value={mathNodeId}
                onChange={(e) => setMathNodeId(e.target.value)}
                className="w-full rounded border bg-background px-2 py-1 text-sm"
              >
                {(mathSkills.length
                  ? mathSkills
                  : [{ id: "times_1_20", title: "Times tables 1–20", status: "available" }]
                ).map((n) => (
                  <option key={n.id} value={n.id} disabled={n.status === "locked"}>
                    {n.title}
                    {n.status === "locked" ? " (locked)" : n.status === "mastered" ? " ✓" : ""}
                  </option>
                ))}
              </select>
              <div className="flex gap-2 items-center">
                <label className="text-xs text-muted-foreground whitespace-nowrap">Questions</label>
                <input
                  type="number"
                  min={1}
                  max={20}
                  value={mathCount}
                  onChange={(e) => setMathCount(Number(e.target.value) || 5)}
                  className="w-16 rounded border bg-background px-2 py-1 text-sm"
                />
              </div>
              <Button
                size="sm"
                onClick={() =>
                  setActive({
                    mode: "start",
                    domain: "math",
                    config: { node_id: mathNodeId, topic: mathTopic, count: mathCount, ...timeOpts },
                  })
                }
              >
                Start math drill
              </Button>
              <p className="text-[10px] text-muted-foreground">
                Or coarse topic bank:{" "}
                <button
                  type="button"
                  className="text-primary underline"
                  onClick={() =>
                    setActive({
                      mode: "start",
                      domain: "math",
                      config: { topic: mathTopic, count: mathCount, ...timeOpts },
                    })
                  }
                >
                  {mathTopic}
                </button>
              </p>
            </div>
            <div className="rounded-lg border p-3 space-y-2">
              <div className="flex items-center gap-2 text-sm font-medium">
                <BookOpen className="h-4 w-4" /> Notes — auto-generate
              </div>
              <p className="text-[10px] text-muted-foreground">
                Paste a library note path (e.g. <code className="text-foreground">data_foundations/lecture_2/numpy_lecture_notes.md</code>).
                Questions are built from the note file only — no corpus RAG.
              </p>
              <input
                type="text"
                value={notePath}
                onChange={(e) => setNotePath(e.target.value)}
                placeholder="folder/note.md"
                className="w-full rounded border bg-background px-2 py-1 text-sm"
              />
              <div className="flex gap-2 items-center">
                <label className="text-xs text-muted-foreground whitespace-nowrap">Questions</label>
                <input
                  type="number"
                  min={1}
                  max={20}
                  value={noteQuizCount}
                  onChange={(e) => setNoteQuizCount(Number(e.target.value) || 5)}
                  className="w-16 rounded border bg-background px-2 py-1 text-sm"
                />
                <Button
                  size="sm"
                  className="gap-1"
                  disabled={!notePath.trim()}
                  onClick={startAutoGenerateFromNote}
                >
                  <Sparkles className="h-3.5 w-3.5" /> Auto-generate &amp; start
                </Button>
              </div>
              {decks.length === 0 ? (
                <p className="text-xs text-muted-foreground">
                  Or{" "}
                  <Link to="/lecture-notes" className="text-primary hover:underline">
                    open Lecture Notes
                  </Link>{" "}
                  and use Generate &amp; quiz on a note.
                </p>
              ) : null}
            </div>
            <div className="rounded-lg border p-3 space-y-2">
              <div className="flex items-center gap-2 text-sm font-medium">
                <BookOpen className="h-4 w-4" /> Saved decks
              </div>
              {decks.length === 0 ? (
                <p className="text-xs text-muted-foreground">
                  No decks yet.{" "}
                  <Link to="/lecture-notes" className="text-primary hover:underline">
                    Generate quiz from Lecture Notes
                  </Link>{" "}
                  — cards land here automatically.
                </p>
              ) : (
                <ul className="max-h-40 overflow-y-auto divide-y text-sm">
                  {decks.slice(0, 8).map((d) => (
                    <li key={d.id} className="flex items-center justify-between gap-2 py-1.5">
                      <span className="truncate">{d.title}</span>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() =>
                          setActive({ mode: "start", domain: "deck", config: { deck_id: d.id, ...timeOpts } })
                        }
                      >
                        Quiz
                      </Button>
                    </li>
                  ))}
                </ul>
              )}
              <Button size="sm" variant="outline" asChild>
                <Link to="/lecture-notes">Open Lecture Notes</Link>
              </Button>
            </div>
            <div className="rounded-lg border p-3 space-y-2 sm:col-span-2">
              <div className="flex items-center gap-2 text-sm font-medium">
                <BookOpen className="h-4 w-4" /> Vocab group
              </div>
              <div className="flex flex-wrap gap-2 items-end">
                <input
                  type="number"
                  min={1}
                  value={groupNumber}
                  onChange={(e) => setGroupNumber(Number(e.target.value) || 1)}
                  className="w-24 rounded border bg-background px-2 py-1 text-sm"
                />
                <Button
                  size="sm"
                  onClick={() =>
                    setActive({
                      mode: "start",
                      domain: "vocab",
                      config: { group_number: groupNumber, ...timeOpts },
                    })
                  }
                >
                  Quiz group
                </Button>
              </div>
            </div>
          </div>
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
                    <Button
                      size="sm"
                      onClick={() =>
                        setActive({ mode: "start", domain: "deck", config: { deck_id: d.id } })
                      }
                    >
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
