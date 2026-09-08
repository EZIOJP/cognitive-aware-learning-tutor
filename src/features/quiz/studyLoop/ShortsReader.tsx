import { useCallback, useEffect, useRef, useState } from "react";
import { ChevronDown, ChevronUp, Loader2, Play, Save } from "lucide-react";
import { toast } from "sonner";
import { Button } from "../../../app/components/ui/button";
import {
  QuizApiError,
  fetchStudyLoopReadCards,
  patchStudyLoopReadCard,
  type StudyLoopReadCard,
} from "../../../api/globalQuizClient";

type Props = {
  tag: string;
  cards: StudyLoopReadCard[];
  onCardsChange: (cards: StudyLoopReadCard[]) => void;
  busy?: boolean;
  onMarkReadAndPractice?: () => void;
};

/** Full-bleed one-card stack — Shorts-style Learn reader. */
export function ShortsReader({
  tag,
  cards,
  onCardsChange,
  busy = false,
  onMarkReadAndPractice,
}: Props) {
  const [index, setIndex] = useState(0);
  const [draft, setDraft] = useState("");
  const [title, setTitle] = useState("");
  const [mtime, setMtime] = useState<number | undefined>(undefined);
  const [saving, setSaving] = useState(false);
  const touchY = useRef<number | null>(null);
  const paneRef = useRef<HTMLDivElement>(null);

  const total = cards.length;
  const safeIndex = total === 0 ? 0 : Math.min(index, total - 1);
  const card = total > 0 ? cards[safeIndex] : null;
  const isLast = total > 0 && safeIndex >= total - 1;

  useEffect(() => {
    setIndex(0);
  }, [tag]);

  useEffect(() => {
    if (!card) {
      setDraft("");
      setTitle("");
      setMtime(undefined);
      return;
    }
    setDraft(String(card.body_markdown || ""));
    setTitle(String(card.title || ""));
    setMtime(typeof card.mtime === "number" ? card.mtime : undefined);
  }, [card?.card_id, card?.body_markdown, card?.title, card?.mtime]);

  const go = useCallback(
    (delta: number) => {
      if (total === 0) return;
      setIndex((i) => Math.max(0, Math.min(total - 1, i + delta)));
    },
    [total]
  );

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null;
      if (t && (t.tagName === "TEXTAREA" || t.tagName === "INPUT" || t.isContentEditable)) {
        return;
      }
      if (e.key === "ArrowDown" || e.key === "j" || e.key === " ") {
        e.preventDefault();
        go(1);
      } else if (e.key === "ArrowUp" || e.key === "k") {
        e.preventDefault();
        go(-1);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [go]);

  const save = async () => {
    if (!card?.card_id) return;
    setSaving(true);
    try {
      const body: { body_markdown: string; title?: string; expected_mtime?: number } = {
        body_markdown: draft,
      };
      if (title.trim()) body.title = title.trim();
      if (typeof mtime === "number") body.expected_mtime = mtime;
      const updated = await patchStudyLoopReadCard(card.card_id, body);
      onCardsChange(
        cards.map((c) => (c.card_id === updated.card_id ? { ...c, ...updated } : c))
      );
      if (typeof updated.mtime === "number") setMtime(updated.mtime);
      toast.success("Saved to notes");
    } catch (err: unknown) {
      if (err instanceof QuizApiError && err.status === 409) {
        toast.error("Conflict — reload and try again");
        const res = await fetchStudyLoopReadCards(tag);
        onCardsChange(res.items || []);
      } else {
        toast.error(err instanceof Error ? err.message : "Save failed");
      }
    } finally {
      setSaving(false);
    }
  };

  if (total === 0) {
    return (
      <div className="flex h-[min(70vh,560px)] items-center justify-center rounded-xl border border-dashed border-border/60 text-sm text-muted-foreground">
        No read cards for {tag || "this tag"}.
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
        <span className="font-mono text-foreground">{tag}</span>
        <span>
          Card {safeIndex + 1} / {total}
        </span>
      </div>

      <div
        ref={paneRef}
        className="relative flex h-[min(72vh,640px)] flex-col rounded-xl border border-border/50 bg-background overflow-hidden shadow-sm"
        onTouchStart={(e) => {
          touchY.current = e.touches[0]?.clientY ?? null;
        }}
        onTouchEnd={(e) => {
          if (touchY.current == null) return;
          const y = e.changedTouches[0]?.clientY ?? touchY.current;
          const dy = touchY.current - y;
          touchY.current = null;
          if (Math.abs(dy) < 48) return;
          go(dy > 0 ? 1 : -1);
        }}
      >
        <div className="absolute inset-x-0 top-0 z-10 flex items-center justify-between gap-2 bg-gradient-to-b from-background/95 to-transparent px-4 pt-3 pb-8">
          <div className="min-w-0">
            <p className="text-[10px] uppercase tracking-wide text-muted-foreground">Read</p>
            <h3 className="text-base font-semibold truncate">{title || card?.title || "Card"}</h3>
          </div>
          <div className="flex gap-1 shrink-0">
            <Button
              size="sm"
              variant="ghost"
              className="h-8 w-8 p-0"
              disabled={safeIndex <= 0}
              onClick={() => go(-1)}
              aria-label="Previous card"
            >
              <ChevronUp className="h-4 w-4" />
            </Button>
            <Button
              size="sm"
              variant="ghost"
              className="h-8 w-8 p-0"
              disabled={isLast}
              onClick={() => go(1)}
              aria-label="Next card"
            >
              <ChevronDown className="h-4 w-4" />
            </Button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto px-4 pt-16 pb-28">
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            className="min-h-[50vh] w-full resize-none border-0 bg-transparent text-sm leading-relaxed focus:outline-none focus:ring-0"
            spellCheck={false}
          />
        </div>

        <div className="absolute inset-x-0 bottom-0 z-10 flex flex-wrap items-center justify-between gap-2 border-t border-border/40 bg-background/95 px-4 py-3 backdrop-blur-sm">
          <p className="text-[10px] text-muted-foreground hidden sm:block">
            ↓ / Space next · ↑ prev · swipe
          </p>
          <div className="flex flex-wrap gap-2 ml-auto">
            <Button size="sm" variant="outline" className="h-8 text-xs gap-1" disabled={saving} onClick={() => void save()}>
              {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />}
              Save
            </Button>
            {!isLast ? (
              <Button size="sm" className="h-8 text-xs gap-1" onClick={() => go(1)}>
                Next <ChevronDown className="h-3.5 w-3.5" />
              </Button>
            ) : onMarkReadAndPractice ? (
              <Button
                size="sm"
                className="h-8 text-xs gap-1"
                disabled={busy}
                onClick={onMarkReadAndPractice}
              >
                {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
                Finish cards → questions
              </Button>
            ) : (
              <span className="text-xs text-muted-foreground self-center">Last card</span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
