import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router";
import { ArrowLeft, Bot, RefreshCw } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { fetchCoachContext, fetchInsightsDaily, fetchInsightsReview } from "../api/hubClient";
import { AiCoachChat } from "../components/dashboard/AiCoachChat";
import { Button } from "../app/components/ui/button";
import { Card } from "../app/components/ui/card";

export function AiCoachPage() {
  const { isAuthenticated } = useAuth();
  const [intro, setIntro] = useState<string | undefined>();
  const [loading, setLoading] = useState(true);
  const [priorities, setPriorities] = useState<string[]>([]);
  const [quizDue, setQuizDue] = useState(0);
  const [stats, setStats] = useState<string | null>(null);
  const [kbHint, setKbHint] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!isAuthenticated) {
      setLoading(false);
      return;
    }
    setLoading(true);
    const [daily, review, ctx] = await Promise.all([
      fetchInsightsDaily(),
      fetchInsightsReview(),
      fetchCoachContext(),
    ]);
    setIntro(review?.comments);
    setPriorities(ctx?.suggested_priorities ?? []);
    setQuizDue(ctx?.quiz_backlog?.due_count ?? 0);
    const idx = ctx?.knowledge_index;
    setKbHint(
      idx
        ? `${idx.lecture_notes} notes · ${idx.vocab_progress_rows} vocab · ${idx.math_attempts} math · ${idx.browser_events_today ?? 0} browser events`
        : null,
    );
    if (daily) {
      setStats(
        `Life ${daily.life_score} · Study ${daily.study_minutes}m · Vocab ${daily.vocab_events} · Math ${daily.math_attempts}`,
      );
    }
    setLoading(false);
  }, [isAuthenticated]);

  useEffect(() => {
    void load();
  }, [load]);

  if (!isAuthenticated) {
    return (
      <div className="p-8 max-w-lg mx-auto text-center space-y-4">
        <p className="text-muted-foreground">Sign in to chat with your AI study coach.</p>
        <Button asChild>
          <Link to="/login">Sign in</Link>
        </Button>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col min-h-0 p-4 md:p-6 max-w-3xl mx-auto w-full">
      <div className="flex items-center gap-3 mb-4 shrink-0">
        <Button variant="ghost" size="sm" asChild>
          <Link to="/">
            <ArrowLeft className="w-4 h-4 mr-1" />
            Dashboard
          </Link>
        </Button>
        <div className="flex-1 min-w-0">
          <h1 className="text-xl font-semibold flex items-center gap-2">
            <Bot className="w-5 h-5 text-primary" />
            AI Study Coach
          </h1>
          {stats && <p className="text-xs text-muted-foreground truncate">{stats}</p>}
          {priorities[0] && (
            <p className="text-[10px] text-muted-foreground truncate">Next: {priorities[0]}</p>
          )}
          {kbHint && <p className="text-[10px] text-muted-foreground truncate">{kbHint}</p>}
          {quizDue > 0 && (
            <p className="text-[10px] text-amber-600 truncate">
              {quizDue} review card{quizDue !== 1 ? "s" : ""} due —{" "}
              <Link to="/review?tab=due" className="underline hover:text-amber-500">
                open Review Hub
              </Link>
            </p>
          )}
        </div>
        <Button variant="outline" size="sm" disabled={loading} onClick={() => void load()}>
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
        </Button>
        <Button variant="ghost" size="sm" asChild>
          <Link to="/project-agent">Project Agent</Link>
        </Button>
      </div>

      <Card className="gloss-panel flex-1 flex flex-col min-h-0 p-4 md:p-5">
        {loading ? (
          <p className="text-sm text-muted-foreground animate-pulse">Loading your hub context…</p>
        ) : (
          <>
            {priorities.length > 0 && (
              <ul className="text-xs text-muted-foreground mb-3 list-disc list-inside shrink-0">
                {priorities.slice(0, 3).map((p) => (
                  <li key={p}>{p}</li>
                ))}
              </ul>
            )}
            <AiCoachChat initialAssistantMessage={intro} className="flex-1 min-h-0" />
          </>
        )}
      </Card>
    </div>
  );
}
