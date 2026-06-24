import { useEffect, useState } from "react";
import { Link } from "react-router";
import {
  BookOpen,
  Loader2,
  Play,
  Sparkles,
} from "lucide-react";
import { Button } from "../../app/components/ui/button";
import { fetchQuizBacklog } from "../../api/globalQuizClient";
import type { QuizBacklog } from "../../features/quiz/types";
import { useAuth } from "../../context/AuthContext";

const ACTION_LINKS: Record<
  QuizBacklog["recommended_action"],
  { label: string; to: string; hint: string }
> = {
  sign_in: { label: "Sign in", to: "/login", hint: "Sync quizzes and spaced repetition." },
  review_due: { label: "Review due cards", to: "/review", hint: "Cards waiting in your FSRS queue." },
  start_vocab: { label: "Start GRE vocab", to: "/gre-vocab/read", hint: "Build your first review deck." },
  lecture_notes: {
    label: "Lecture Notes",
    to: "/lecture-notes",
    hint: "Generate notes → quiz → auto-review loop.",
  },
};

export function StudyLoopWidget() {
  const { user } = useAuth();
  const [backlog, setBacklog] = useState<QuizBacklog | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!user) {
      setBacklog({
        total_cards: 0,
        due_count: 0,
        by_domain: {},
        deck_count: 0,
        recommended_action: "sign_in",
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
  }, [user]);

  if (!backlog) return null;

  const action = ACTION_LINKS[backlog.recommended_action];
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

          {domains.length > 0 && (
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
          )}

          <p className="text-xs text-muted-foreground leading-relaxed">{action.hint}</p>

          <div className="flex flex-wrap gap-2">
            {user && backlog.due_count > 0 && (
              <Button size="sm" className="h-8 text-xs gap-1" asChild>
                <Link to="/review?tab=due">
                  <Play className="h-3.5 w-3.5" /> Review {backlog.due_count} due
                </Link>
              </Button>
            )}
            <Button size="sm" variant="outline" className="h-8 text-xs gap-1" asChild>
              <Link to={action.to}>
                <Sparkles className="h-3.5 w-3.5" /> {action.label}
              </Link>
            </Button>
          </div>

          <div className="text-[10px] text-muted-foreground space-y-1 pt-1 border-t border-border/30">
            <p className="flex items-center gap-1">
              <BookOpen className="h-3 w-3" /> Vocab · Math · Lecture notes · Code
            </p>
            <p>One handler · FSRS scheduling · time-bound sessions</p>
          </div>
        </>
      )}
    </div>
  );
}
