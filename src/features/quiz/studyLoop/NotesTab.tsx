import { useEffect, useState } from "react";
import { Loader2, Play } from "lucide-react";
import { toast } from "sonner";
import { Button } from "../../../app/components/ui/button";
import {
  createStudyLoopSession,
  fetchStudyLoopReadCards,
  markStudyLoopRead,
  startStudyLoopPractice,
  type StudyLoopReadCard,
  type StudyLoopTag,
} from "../../../api/globalQuizClient";
import { FolderTagTree } from "./FolderTagTree";
import { ShortsReader } from "./ShortsReader";

type Props = {
  tags: StudyLoopTag[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onStartPractice: (quizSessionId: string) => void;
};

export function NotesTab({ tags, selectedId, onSelect, onStartPractice }: Props) {
  const withCards = tags.filter((t) => Boolean(t.has_read_card));
  const selected =
    withCards.find((t) => String(t.id) === selectedId) ||
    withCards[0] ||
    null;
  const selectedTagId = selected ? String(selected.id) : "";

  const [cards, setCards] = useState<StudyLoopReadCard[]>([]);
  const [loopSessionId, setLoopSessionId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loadingCards, setLoadingCards] = useState(false);

  useEffect(() => {
    if (!selectedTagId) {
      setCards([]);
      setLoopSessionId(null);
      return;
    }
    let cancelled = false;
    setLoadingCards(true);
    Promise.all([
      fetchStudyLoopReadCards(selectedTagId),
      createStudyLoopSession(selectedTagId),
    ])
      .then(([cardRes, session]) => {
        if (cancelled) return;
        setCards(cardRes.items || []);
        setLoopSessionId(session.session_id);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          toast.error(err instanceof Error ? err.message : "Failed to load read cards");
          setCards([]);
          setLoopSessionId(null);
        }
      })
      .finally(() => {
        if (!cancelled) setLoadingCards(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedTagId]);

  const markRead = async (andPractice: boolean) => {
    if (!loopSessionId) return;
    setBusy(true);
    try {
      await markStudyLoopRead(loopSessionId);
      toast.success(`Marked read: ${selectedTagId}`);
      if (andPractice) {
        try {
          const practice = await startStudyLoopPractice(loopSessionId, 15);
          if (!practice.session_id) {
            toast.error("Questions are not present for this topic.");
            return;
          }
          onStartPractice(practice.session_id);
        } catch (err: unknown) {
          const msg = err instanceof Error ? err.message : "";
          const lower = msg.toLowerCase();
          if (
            lower.includes("no_practice") ||
            lower.includes("not present") ||
            lower.includes("no math questions") ||
            msg === "HTTP 400"
          ) {
            toast.error("Questions are not present for this topic.");
          } else {
            toast.error(msg || "Could not start questions");
          }
        }
      }
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Mark read failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold">Notes · Shorts</h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            Folders → tags → one card at a time ·{" "}
            <span className="font-mono text-foreground">{selectedTagId || "—"}</span>
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button size="sm" disabled={busy || !loopSessionId} onClick={() => void markRead(false)}>
            Mark read
          </Button>
          <Button
            size="sm"
            variant="secondary"
            className="gap-1"
            disabled={busy || !loopSessionId}
            onClick={() => void markRead(true)}
          >
            {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
            Finish cards → questions
          </Button>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,16rem)_1fr]">
        <div className="gloss-panel rounded-xl p-3 max-h-[min(72vh,640px)] overflow-y-auto">
          <p className="text-[11px] font-medium text-muted-foreground uppercase tracking-wide mb-2">
            Folders
          </p>
          <FolderTagTree
            tags={tags}
            selectedId={selectedTagId || selectedId}
            onSelect={onSelect}
            readCardsOnly
          />
        </div>

        <div className="min-h-[200px]">
          {!selectedTagId ? (
            <p className="text-sm text-muted-foreground gloss-panel rounded-xl p-6">
              Select a tag with a read card.
            </p>
          ) : loadingCards ? (
            <div className="flex items-center gap-2 text-sm text-muted-foreground py-8 gloss-panel rounded-xl p-6">
              <Loader2 className="h-4 w-4 animate-spin" /> Loading cards…
            </div>
          ) : (
            <ShortsReader
              tag={selectedTagId}
              cards={cards}
              onCardsChange={setCards}
              busy={busy}
              onMarkReadAndPractice={() => void markRead(true)}
            />
          )}
        </div>
      </div>
    </div>
  );
}
