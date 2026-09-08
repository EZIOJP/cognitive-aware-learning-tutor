import { useEffect, useState } from "react";
import { ArrowLeft, Loader2, PenLine, Play } from "lucide-react";
import { Link } from "react-router";
import { toast, Toaster } from "sonner";
import { Button } from "../../../app/components/ui/button";
import {
  createStudyLoopSession,
  fetchStudyLoopReadCards,
  fetchStudyLoopToday,
  markStudyLoopRead,
  startStudyLoopPractice,
  startStudyLoopToday,
  type StudyLoopReadCard,
} from "../../../api/globalQuizClient";
import { TagPicker } from "./TagPicker";
import { ReadCardPanel } from "./ReadCardPanel";
import { QuestionEditor } from "./QuestionEditor";

export type LoopPhase = "pick_tag" | "read" | "practice" | "edit_question";

type TodayInfo = {
  day: string;
  tags: string[];
  mode: string;
  state: string;
  current_tag: string | null;
  steps?: Array<{ tag?: string; kind?: string; label?: string }>;
  has_mathcore?: boolean;
};

type DailyStartMeta = {
  step_kind?: string;
  step_label?: string;
  practice_target?: number;
  encourage_more?: boolean;
  difficulty_level?: string | null;
};

type Props = {
  onStartPractice: (quizSessionId: string) => void;
};

export function LoopTab({ onStartPractice }: Props) {
  const [phase, setPhase] = useState<LoopPhase>("pick_tag");
  const [tag, setTag] = useState<string | null>(null);
  const [loopSessionId, setLoopSessionId] = useState<string | null>(null);
  const [cards, setCards] = useState<StudyLoopReadCard[]>([]);
  const [busy, setBusy] = useState(false);
  const [editorOpen, setEditorOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [today, setToday] = useState<TodayInfo | null>(null);
  const [onDaily, setOnDaily] = useState(false);
  const [dailyMeta, setDailyMeta] = useState<DailyStartMeta | null>(null);

  useEffect(() => {
    void fetchStudyLoopToday()
      .then((t) =>
        setToday({
          day: t.day,
          tags: t.tags || [],
          mode: t.mode,
          state: t.state,
          current_tag: t.current_tag,
          steps: t.steps as TodayInfo["steps"],
          has_mathcore: Boolean(t.has_mathcore) ||
            Boolean(
              (t.steps || []).some((s) => String((s as { kind?: string }).kind || "") === "mathcore")
            ),
        })
      )
      .catch(() => setToday(null));
  }, []);

  const startDaily = async (markRead = false) => {
    setBusy(true);
    setError(null);
    try {
      const res = await startStudyLoopToday(markRead);
      setOnDaily(true);
      const steps = (res.steps || []) as TodayInfo["steps"];
      setToday({
        day: res.day,
        tags: res.tags || [],
        mode: res.mode,
        state: res.state,
        current_tag: res.current_tag,
        steps,
        has_mathcore: Boolean(steps?.some((s) => s.kind === "mathcore")),
      });
      setDailyMeta({
        step_kind: res.step_kind,
        step_label: res.step_label,
        practice_target: res.practice_target,
        encourage_more: res.encourage_more,
        difficulty_level: res.difficulty_level,
      });
      const quizId = String(res.quiz?.session_id || "").trim();
      if (quizId) {
        if (res.encourage_more) {
          toast.message("Math Core: at least 20 questions are required — keep going after if you can.");
        }
        if (res.difficulty_level) {
          toast.message(`Difficulty: ${res.difficulty_level} — pass ~80% to unlock the next level.`);
        }
        setPhase("practice");
        onStartPractice(quizId);
        return;
      }
      setTag(res.current_tag);
      setLoopSessionId(res.loop_session_id || (res.loop_session_ids || [])[0] || null);
      setCards(res.read_cards || []);
      setPhase("read");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Could not start today’s path";
      setError(msg);
      toast.error(msg);
    } finally {
      setBusy(false);
    }
  };

  const pickTag = async (tagId: string) => {
    setBusy(true);
    setError(null);
    try {
      setOnDaily(false);
      const [session, cardRes] = await Promise.all([
        createStudyLoopSession(tagId),
        fetchStudyLoopReadCards(tagId),
      ]);
      setTag(tagId);
      setLoopSessionId(session.session_id);
      setCards(cardRes.items || []);
      setPhase("read");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Could not start loop session";
      setError(msg);
      toast.error(msg);
    } finally {
      setBusy(false);
    }
  };

  const markReadAndPractice = async () => {
    setBusy(true);
    setError(null);
    try {
      if (onDaily) {
        await startDaily(true);
        return;
      }
      if (!loopSessionId) return;
      await markStudyLoopRead(loopSessionId);
      const practice = await startStudyLoopPractice(loopSessionId, 15);
      if (!practice.session_id) {
        throw new Error("Practice did not return a quiz session");
      }
      setPhase("practice");
      onStartPractice(practice.session_id);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Could not start practice";
      setError(msg);
      toast.error(msg);
    } finally {
      setBusy(false);
    }
  };

  const backToPicker = () => {
    setPhase("pick_tag");
    setTag(null);
    setLoopSessionId(null);
    setCards([]);
    setError(null);
    setOnDaily(false);
    setDailyMeta(null);
  };

  const pathLabels =
    today?.steps?.length && onDaily
      ? today.steps.map((s) => s.label || s.tag || "?").join(" → ")
      : today?.tags?.length && onDaily
        ? today.tags.join(" → ")
        : tag;
  const isMathCoreStep = onDaily && (dailyMeta?.step_kind === "mathcore" || dailyMeta?.encourage_more);
  const practiceTarget = dailyMeta?.practice_target ?? 15;

  return (
    <div className="space-y-4">
      <Toaster richColors position="top-center" />
      <div className="gloss-panel rounded-xl p-4 space-y-4">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <h2 className="text-sm font-semibold">Today’s path</h2>
            <p className="text-xs text-muted-foreground mt-0.5">
              {today?.has_mathcore
                ? "Math Core daily: skim reference + worksheet cards, then at least 20 questions. Extra free practice is encouraged."
                : "One click: read, then questions. Per topic: easy → medium → hard → advanced (pass ~80% to unlock)."}
            </p>
          </div>
          {phase === "read" && tag && (
            <Button size="sm" variant="ghost" className="h-8 text-xs gap-1" onClick={backToPicker}>
              <ArrowLeft className="h-3.5 w-3.5" /> Other tags
            </Button>
          )}
        </div>

        {error && <p className="text-xs text-destructive">{error}</p>}

        {phase === "pick_tag" && (
          <div className="space-y-3">
            {today?.state === "empty" || (today && today.tags.length === 0) ? (
              <p className="text-sm text-muted-foreground">
                Nothing to assign today — no questions on unmastered tags, or everything is at its
                bar.{" "}
                <Link to="/review?tab=due" className="text-primary underline">
                  Review due cards
                </Link>{" "}
                if any.
              </p>
            ) : today?.state === "done" ? (
              <div className="space-y-2">
                <p className="text-sm">Path done for {today.day}. Leftover misses stay in Due.</p>
                <Button size="sm" asChild>
                  <Link to="/review?tab=due">Go to Due</Link>
                </Button>
              </div>
            ) : (
              <div className="rounded-lg border border-primary/30 bg-primary/5 p-3 space-y-2">
                <p className="text-sm font-medium">
                  {today?.steps?.length
                    ? `Today: ${today.steps.map((s) => s.label || s.tag).join(" then ")} · one at a time`
                    : today?.tags?.length
                      ? `Today: ${today.tags.join(" then ")} · ${today.mode === "C" ? "combined" : "one at a time"}`
                      : "Today’s path"}
                </p>
                {today?.has_mathcore && (
                  <p className="text-xs text-muted-foreground">
                    Math Core is required daily (read + 20Q). Tables / divisibility are optional skim; finish the powers
                    worksheet cards, then keep going past 20 if you can.
                  </p>
                )}
                <Button size="sm" disabled={busy} onClick={() => void startDaily(false)} className="gap-1">
                  {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
                  {today?.state === "in_progress" ? "Continue today’s path" : "Start today’s path"}
                </Button>
              </div>
            )}
            <p className="text-xs text-muted-foreground pt-2">Or pick any tag:</p>
            <TagPicker onSelect={(id) => void pickTag(id)} disabled={busy} />
          </div>
        )}

        {phase === "read" && pathLabels && (
          <div className="space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-xs text-muted-foreground">
                Reading{" "}
                <span className="font-mono text-foreground">
                  {isMathCoreStep ? dailyMeta?.step_label || "Math Core" : pathLabels}
                </span>
                {isMathCoreStep ? (
                  <span className="ml-1 text-muted-foreground">
                    · optional reference + worksheet cards, then ≥{practiceTarget}Q
                  </span>
                ) : null}
                {dailyMeta?.difficulty_level ? (
                  <span className="ml-1 rounded border border-border/60 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-foreground">
                    {dailyMeta.difficulty_level}
                  </span>
                ) : null}
              </p>
              <Button
                size="sm"
                variant="outline"
                className="h-7 text-xs gap-1"
                onClick={() => {
                  setEditorOpen(true);
                  setPhase("edit_question");
                }}
              >
                <PenLine className="h-3 w-3" /> Open answers
              </Button>
            </div>

            <ReadCardPanel tag={tag || today?.current_tag || ""} cards={cards} onCardsChange={setCards} />

            {isMathCoreStep && (
              <p className="text-xs text-muted-foreground">
                Must: finish the read cards and {practiceTarget} questions. Encouraged: free extra drills after the floor.
              </p>
            )}
            <div className="flex flex-wrap gap-2 pt-1 border-t border-border/40">
              <Button size="sm" className="h-8 text-xs gap-1" disabled={busy} onClick={() => void markReadAndPractice()}>
                {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
                {isMathCoreStep ? `Mark read & practice (${practiceTarget})` : "Mark read & practice"}
              </Button>
            </div>
          </div>
        )}
      </div>

      {(tag || today?.current_tag) && (
        <QuestionEditor
          tag={tag || today?.current_tag || ""}
          open={editorOpen}
          onOpenChange={(next) => {
            setEditorOpen(next);
            if (!next && phase === "edit_question") setPhase("read");
          }}
        />
      )}
    </div>
  );
}
