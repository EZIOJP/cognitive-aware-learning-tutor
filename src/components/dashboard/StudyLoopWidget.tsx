import { useEffect, useState } from "react";
import { Link } from "react-router";
import {
  BookOpen,
  Calculator,
  Loader2,
  Play,
  Sparkles,
} from "lucide-react";
import { Button } from "../../app/components/ui/button";
import { fetchQuizBacklog } from "../../api/globalQuizClient";
import type { QuizBacklog } from "../../features/quiz/types";
import { useAuth } from "../../context/AuthContext";

const FALLBACK_LINKS: Record<
  QuizBacklog["recommended_action"],
  { label: string; to: string; hint: string }
> = {
  sign_in: { label: "Lecture Notes", to: "/lecture-notes", hint: "Generate notes → quiz → auto-review loop." },
  review_due: { label: "Review due cards", to: "/review", hint: "Cards waiting in your FSRS queue." },
  start_vocab: { label: "Start GRE vocab", to: "/gre-vocab/read", hint: "Build your first review deck." },
  lecture_notes: {
    label: "Lecture Notes",
    to: "/lecture-notes",
    hint: "Generate notes → quiz → auto-review loop.",
  },
};

export function StudyLoopWidget() {
  const { user, sessionReady } = useAuth();
  const [backlog, setBacklog] = useState<QuizBacklog | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!sessionReady) return;
    if (!user) {
      setBacklog({
        total_cards: 0,
        due_count: 0,
        by_domain: {},
        deck_count: 0,
        recommended_action: "lecture_notes",
        next_step: {
          action: "lecture_notes",
          label: "Lecture Notes",
          to: "/lecture-notes",
          reason: "Start the local API to sync your review queue.",
        },
      });
      return;
    }
    setLoading(true);
    fetchQuizBacklog()
      .then(setBacklog)
      .catch(() =>
        setBacklog({
          total_cards: 0,
          due_count: 0,
          by_domain: {},
          deck_count: 0,
          recommended_action: "lecture_notes",
        })
      )
      .finally(() => setLoading(false));
  }, [user, sessionReady]);

  if (!backlog) return null;

  const next = backlog.next_step;
  const fallback =
    FALLBACK_LINKS[backlog.recommended_action] ?? FALLBACK_LINKS.lecture_notes;
  const primaryLabel = next?.label ?? fallback.label;
  const primaryTo = next?.to ?? fallback.to;
  const hint = next?.reason ?? fallback.hint;
  const domains = Object.entries(backlog.by_domain);

  return (
    <div className="space-y-3 text-sm">
      {loading ? (
        <div className="flex items-center gap-2 text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading study queue…
        </div>
      ) : (
        <>
          <div className="grid grid-cols-3 gap-2 text-center">
            <div className="rounded-lg bg-background/40 px-2 py-2">
              <p className="text-lg font-bold text-primary">{backlog.due_count}</p>
              <p className="text-[10px] text-muted-foreground">Due now</p>
            </div>
            <div className="rounded-lg bg-background/40 px-2 py-2">
              <p className="text-lg font-bold">{backlog.total_cards}</p>
              <p className="text-[10px] text-muted-foreground">In queue</p>
            </div>
            <div className="rounded-lg bg-background/40 px-2 py-2">
              <p className="text-lg font-bold">{backlog.deck_count}</p>
              <p className="text-[10px] text-muted-foreground">My decks</p>
            </div>
          </div>

          {domains.length > 0 ? (
            <div className="flex flex-wrap gap-1.5">
              {domains.map(([d, n]) => (
                <span
                  key={d}
                  className="text-[10px] px-2 py-0.5 rounded-full bg-background/50 border border-border/40"
                >
                  {d} · {n}
                </span>
              ))}
            </div>
          ) : (
            !loading && (
              <p className="text-[11px] text-muted-foreground">
                No review cards yet — quiz lecture notes, math, or GRE vocab to fill the shared queue.
              </p>
            )
          )}

          <p className="text-xs text-muted-foreground leading-relaxed">{hint}</p>

          <div className="flex flex-wrap gap-2">
            <Button size="sm" className="h-8 text-xs gap-1" asChild>
              <Link to={primaryTo}>
                <Play className="h-3.5 w-3.5" /> Next: {primaryLabel}
              </Link>
            </Button>
          </div>

          <div className="flex flex-wrap gap-1.5 pt-1">
            <Button size="sm" variant="outline" className="h-7 text-[10px] gap-1" asChild>
              <Link to="/lecture-notes">
                <BookOpen className="h-3 w-3" /> Notes
              </Link>
            </Button>
            <Button size="sm" variant="outline" className="h-7 text-[10px] gap-1" asChild>
              <Link to="/review?tab=start">
                <Sparkles className="h-3 w-3" /> Vocab quiz
              </Link>
            </Button>
            <Button size="sm" variant="outline" className="h-7 text-[10px] gap-1" asChild>
              <Link to="/review?tab=start">
                <Calculator className="h-3 w-3" /> Math
              </Link>
            </Button>
            <Button size="sm" variant="outline" className="h-7 text-[10px] gap-1" asChild>
              <Link to="/review?tab=due">Review</Link>
            </Button>
          </div>
        </>
      )}
    </div>
  );
}
