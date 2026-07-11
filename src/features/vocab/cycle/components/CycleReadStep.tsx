import { useCallback, useEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from "react";
import { ChevronLeft, ChevronRight, BookOpen, Loader2, Pencil, Sparkles } from "lucide-react";
import { Button } from "../../../../app/components/ui/button";
import { Progress } from "../../../../app/components/ui/progress";
import type { WordWithProgress, VocabWord } from "../../types";
import { WordCard } from "../../components/read/WordCard";
import { markWordRead } from "../../store/vocabStore";
import { useAuth } from "../../../../context/AuthContext";
import { authFetch } from "../../api/authClient";

const SWIPE_MIN_PX = 56;
const SWIPE_RATIO = 1.25;

interface CycleReadStepProps {
  words: WordWithProgress[];
  groupNumber: number;
  isLowMastery?: boolean;
  onComplete: (words: WordWithProgress[]) => void;
  onBack: () => void;
}

export function CycleReadStep({
  words,
  groupNumber,
  isLowMastery = false,
  onComplete,
  onBack,
}: CycleReadStepProps) {
  const { token, isAdmin } = useAuth();
  const [index, setIndex] = useState(0);
  const [localWords, setLocalWords] = useState(words);
  const [editing, setEditing] = useState(false);
  const [fillBusy, setFillBusy] = useState(false);
  const [dragX, setDragX] = useState(0);
  const [dragging, setDragging] = useState(false);
  const pointerRef = useRef<{ id: number; x: number; y: number; active: boolean } | null>(null);

  useEffect(() => {
    setLocalWords(words);
    setIndex(0);
    setEditing(false);
  }, [words]);

  const total = localWords.length;
  const current = localWords[index];
  const pct = total > 0 ? ((index + 1) / total) * 100 : 0;

  const patchWord = useCallback((updated: VocabWord) => {
    setLocalWords((prev) =>
      prev.map((w) =>
        w.id === updated.id
          ? {
              ...w,
              ...updated,
              mastery: w.mastery,
              times_asked: w.times_asked,
              times_correct: w.times_correct,
              accuracy_rate: w.accuracy_rate,
              is_due: w.is_due,
            }
          : w,
      ),
    );
  }, []);

  const go = useCallback(
    (dir: number) => {
      if (total === 0 || editing) return;
      if (dir > 0 && current) {
        void markWordRead(current.id).catch(() => undefined);
      }
      const next = index + dir;
      if (next >= total) {
        onComplete(localWords);
        return;
      }
      if (next < 0) return;
      setEditing(false);
      setIndex(next);
    },
    [index, total, localWords, onComplete, current, editing],
  );

  const fillEmpty = useCallback(async () => {
    if (!token || !isAdmin || !current || fillBusy || editing) return;
    setFillBusy(true);
    try {
      const { data } = await authFetch(
        `/words/${current.id}/enrich?overwrite=false`,
        token,
        { method: "POST" },
      );
      const updated = (data as { word?: VocabWord }).word;
      if (updated) patchWord(updated);
    } catch {
      /* non-blocking */
    } finally {
      setFillBusy(false);
    }
  }, [token, isAdmin, current, fillBusy, editing, patchWord]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (
        e.target instanceof HTMLInputElement ||
        e.target instanceof HTMLTextAreaElement
      ) {
        return;
      }
      if (e.key === "Escape") {
        onBack();
        return;
      }
      if (editing) return;
      if (e.key === "ArrowRight" || e.key === " ") {
        e.preventDefault();
        go(1);
      } else if (e.key === "ArrowLeft") {
        e.preventDefault();
        go(-1);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [go, onBack, editing]);

  const endSwipe = (dx: number, dy: number) => {
    setDragging(false);
    setDragX(0);
    if (editing) return;
    if (Math.abs(dx) < SWIPE_MIN_PX) return;
    if (Math.abs(dx) < Math.abs(dy) * SWIPE_RATIO) return;
    if (dx < 0) go(1);
    else go(-1);
  };

  const onPointerDown = (e: ReactPointerEvent<HTMLDivElement>) => {
    if (editing) return;
    if ((e.target as HTMLElement).closest("button, a, input, textarea, select, [data-no-swipe]")) {
      return;
    }
    pointerRef.current = { id: e.pointerId, x: e.clientX, y: e.clientY, active: true };
    setDragging(true);
    setDragX(0);
    e.currentTarget.setPointerCapture?.(e.pointerId);
  };

  const onPointerMove = (e: ReactPointerEvent<HTMLDivElement>) => {
    const p = pointerRef.current;
    if (!p?.active || p.id !== e.pointerId) return;
    const dx = e.clientX - p.x;
    const dy = e.clientY - p.y;
    if (Math.abs(dx) > Math.abs(dy)) {
      setDragX(Math.max(-120, Math.min(120, dx * 0.45)));
    }
  };

  const onPointerUp = (e: ReactPointerEvent<HTMLDivElement>) => {
    const p = pointerRef.current;
    if (!p?.active || p.id !== e.pointerId) return;
    endSwipe(e.clientX - p.x, e.clientY - p.y);
    pointerRef.current = null;
  };

  if (total === 0) {
    return (
      <div className="gloss-panel rounded-2xl p-8 text-center">
        <p className="text-muted-foreground mb-4">No words in this group.</p>
        <Button onClick={onBack}>Back to dashboard</Button>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col gap-2 min-h-0">
      <div className="gloss-panel rounded-2xl px-3 py-2 shrink-0 space-y-2" data-no-swipe>
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex items-center gap-2 min-w-0 flex-1">
            <BookOpen className="w-4 h-4 shrink-0" />
            <span className="text-sm font-semibold truncate">
              {isLowMastery ? "Low mastery" : "Read"} · G{groupNumber}
            </span>
          </div>
          <span className="text-xs font-mono tabular-nums shrink-0">
            {index + 1}/{total}
          </span>
          {isAdmin && (
            <>
              <Button
                type="button"
                size="sm"
                variant="outline"
                className="h-8 gap-1 text-xs"
                disabled={fillBusy || editing}
                onClick={() => setEditing(true)}
              >
                <Pencil className="w-3.5 h-3.5" />
                Edit
              </Button>
              <Button
                type="button"
                size="sm"
                variant="secondary"
                className="h-8 gap-1 text-xs"
                disabled={fillBusy || editing}
                onClick={() => void fillEmpty()}
              >
                {fillBusy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />}
                Gen AI
              </Button>
            </>
          )}
        </div>
        <Progress value={pct} className="h-1" />
      </div>

      <div className="relative flex-1 min-h-0 overflow-hidden rounded-2xl">
        <button
          type="button"
          aria-label="Previous"
          disabled={editing || index === 0}
          className="absolute left-0 top-0 bottom-0 z-20 w-10 sm:w-14 touch-manipulation opacity-0 hover:opacity-100 transition-opacity disabled:pointer-events-none"
          onClick={() => go(-1)}
        >
          <span className="flex h-full items-center justify-center bg-gradient-to-r from-background/50 to-transparent">
            <ChevronLeft className="w-7 h-7" />
          </span>
        </button>
        <button
          type="button"
          aria-label="Next"
          disabled={editing}
          className="absolute right-0 top-0 bottom-0 z-20 w-10 sm:w-14 touch-manipulation opacity-0 hover:opacity-100 transition-opacity disabled:pointer-events-none"
          onClick={() => go(1)}
        >
          <span className="flex h-full items-center justify-center bg-gradient-to-l from-background/50 to-transparent">
            <ChevronRight className="w-7 h-7" />
          </span>
        </button>

        <div
          className="h-full touch-pan-y"
          style={{
            transform: `translateX(${dragX}px)`,
            transition: dragging ? "none" : "transform 180ms ease-out",
          }}
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onPointerCancel={() => {
            pointerRef.current = null;
            setDragging(false);
            setDragX(0);
          }}
        >
          {current && (
            <WordCard
              key={current.id}
              word={current}
              onWordUpdated={patchWord}
              hideActions
              editing={editing}
              onEditingChange={setEditing}
              aiBusy={fillBusy}
            />
          )}
        </div>

        <p className="pointer-events-none absolute bottom-2 left-1/2 z-10 -translate-x-1/2 rounded-full bg-background/70 px-2.5 py-0.5 text-[10px] text-muted-foreground backdrop-blur-sm">
          Swipe ← → · Esc exit
        </p>
      </div>

      <footer className="shrink-0 flex gap-2 justify-between" data-no-swipe>
        <Button variant="outline" size="sm" onClick={onBack}>
          Exit
        </Button>
        <Button size="sm" onClick={() => go(1)} disabled={editing}>
          {index >= total - 1 ? "Start quiz" : "Next"}
          <ChevronRight className="w-4 h-4 ml-1" />
        </Button>
      </footer>
    </div>
  );
}
