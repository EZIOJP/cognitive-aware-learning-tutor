import { useState } from "react";
import { ArrowLeft, Loader2, PenLine, Play } from "lucide-react";
import { toast, Toaster } from "sonner";
import { Button } from "../../../app/components/ui/button";
import {
  createStudyLoopSession,
  fetchStudyLoopReadCards,
  markStudyLoopRead,
  startStudyLoopPractice,
  type StudyLoopReadCard,
} from "../../../api/globalQuizClient";
import { TagPicker } from "./TagPicker";
import { ReadCardPanel } from "./ReadCardPanel";
import { QuestionEditor } from "./QuestionEditor";

export type LoopPhase = "pick_tag" | "read" | "practice" | "edit_question";

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

  const pickTag = async (tagId: string) => {
    setBusy(true);
    setError(null);
    try {
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
    if (!loopSessionId) return;
    setBusy(true);
    setError(null);
    try {
      await markStudyLoopRead(loopSessionId);
      const practice = await startStudyLoopPractice(loopSessionId, 5);
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
  };

  return (
    <div className="space-y-4">
      <Toaster richColors position="top-center" />
      <div className="gloss-panel rounded-xl p-4 space-y-4">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <h2 className="text-sm font-semibold">Study Loop</h2>
            <p className="text-xs text-muted-foreground mt-0.5">
              Tag → read notes → mark read → practice (one FSRS queue).
            </p>
          </div>
          {phase === "read" && tag && (
            <Button size="sm" variant="ghost" className="h-8 text-xs gap-1" onClick={backToPicker}>
              <ArrowLeft className="h-3.5 w-3.5" /> Change tag
            </Button>
          )}
        </div>

        {error && <p className="text-xs text-destructive">{error}</p>}

        {phase === "pick_tag" && <TagPicker onSelect={(id) => void pickTag(id)} disabled={busy} />}

        {phase === "read" && tag && (
          <div className="space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-xs text-muted-foreground">
                Reading <span className="font-mono text-foreground">{tag}</span>
                {loopSessionId ? (
                  <span className="ml-1 opacity-70">· session {loopSessionId.slice(0, 8)}…</span>
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

            <ReadCardPanel tag={tag} cards={cards} onCardsChange={setCards} />

            <div className="flex flex-wrap gap-2 pt-1 border-t border-border/40">
              <Button
                size="sm"
                className="h-8 text-xs gap-1"
                disabled={busy || !loopSessionId}
                onClick={() => void markReadAndPractice()}
              >
                {busy ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Play className="h-3.5 w-3.5" />
                )}
                Mark read &amp; practice
              </Button>
            </div>
          </div>
        )}
      </div>

      {tag && (
        <QuestionEditor
          tag={tag}
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
