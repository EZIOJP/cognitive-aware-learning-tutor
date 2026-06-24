import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router";
import { Bot, Maximize2, MessageSquare, RefreshCw } from "lucide-react";
import { useAuth } from "../../context/AuthContext";
import {
  fetchCoachContext,
  fetchInsightsDaily,
  fetchInsightsReview,
  type CoachContextPayload,
  type InsightsDailyPayload,
} from "../../api/hubClient";
import { Button } from "../../app/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "../../app/components/ui/sheet";
import { AiCoachChat } from "./AiCoachChat";

type Review = {
  comments: string;
  next_steps: string[];
  goals: string[];
  overall_performance: string;
  source?: "gemma" | "template";
};

const OFFLINE_TIPS = [
  "Sign in to sync plugins and get a daily review from your hub.",
  "Enable Life Tracker and log sleep + study minutes.",
  "Turn on the browser extension to feed productivity data.",
];

export function AiReviewWidget() {
  const { isAuthenticated } = useAuth();
  const [daily, setDaily] = useState<InsightsDailyPayload | null>(null);
  const [review, setReview] = useState<Review | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [chatOpen, setChatOpen] = useState(false);
  const [coachContext, setCoachContext] = useState<CoachContextPayload | null>(null);

  const loadReview = useCallback(async (isRefresh = false) => {
    if (!isAuthenticated) {
      setLoading(false);
      return;
    }
    if (isRefresh) setRefreshing(true);
    else setLoading(true);
    const [d, r, ctx] = await Promise.all([
      fetchInsightsDaily(),
      fetchInsightsReview(),
      fetchCoachContext(),
    ]);
    setDaily(d);
    setReview(r);
    setCoachContext(ctx);
    setLoading(false);
    setRefreshing(false);
  }, [isAuthenticated]);

  useEffect(() => {
    void loadReview();
  }, [loadReview]);

  if (!isAuthenticated) {
    return (
      <div className="space-y-2 text-sm">
        <p className="text-muted-foreground">{OFFLINE_TIPS[0]}</p>
        <Link to="/login" className="text-primary text-xs hover:underline">
          Sign in →
        </Link>
      </div>
    );
  }

  if (loading) {
    return <p className="text-sm text-muted-foreground animate-pulse">Loading review…</p>;
  }

  const perf = daily?.overall_performance ?? review?.overall_performance ?? "good";
  const label =
    perf === "excellent" ? "Excellent" : perf === "good" ? "On Track" : "Needs Focus";
  const source = review?.source ?? "template";

  return (
    <div className="space-y-3 text-sm h-full flex flex-col">
      <div className="flex items-start justify-between gap-2">
        <p className="text-lg font-semibold text-primary">{label}</p>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="h-7 px-2 text-xs shrink-0"
          disabled={refreshing}
          onClick={() => void loadReview(true)}
          title="Refresh review"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? "animate-spin" : ""}`} />
        </Button>
      </div>
      <p className="text-muted-foreground leading-relaxed line-clamp-4">
        {review?.comments ?? "Log activity in Life Tracker or complete a quiz to build your review."}
      </p>
      {daily && (
        <p className="text-xs text-muted-foreground">
          Life {daily.life_score} · Study {daily.study_minutes}m · Vocab {daily.vocab_events} · Math{" "}
          {daily.math_attempts}
        </p>
      )}
      {review?.next_steps?.length ? (
        <ul className="text-xs space-y-1 list-disc list-inside text-foreground/80 line-clamp-3">
          {review.next_steps.slice(0, 3).map((s) => (
            <li key={s}>{s}</li>
          ))}
        </ul>
      ) : null}

      {coachContext?.knowledge_index ? (
        <p className="text-[10px] text-muted-foreground line-clamp-2">
          Knowledge base: {coachContext.knowledge_index.lecture_notes} notes ·{" "}
          {coachContext.knowledge_index.vocab_progress_rows} vocab ·{" "}
          {coachContext.knowledge_index.math_attempts} math ·{" "}
          {coachContext.knowledge_index.browser_events_today ?? 0} browser events.
        </p>
      ) : null}

      <div className="flex flex-wrap gap-2 pt-1 mt-auto">
        <Sheet open={chatOpen} onOpenChange={setChatOpen}>
          <SheetTrigger asChild>
            <Button type="button" size="sm" className="h-8 text-xs gap-1.5">
              <MessageSquare className="w-3.5 h-3.5" />
              Chat with coach
            </Button>
          </SheetTrigger>
          <SheetContent side="right" className="w-full sm:max-w-md flex flex-col">
            <SheetHeader>
              <SheetTitle className="flex items-center gap-2">
                <Bot className="w-5 h-5 text-primary" />
                AI Study Coach
              </SheetTitle>
              <SheetDescription>
                Uses your logged-in hub data (vocab, life, math, notes, focus) plus an overview of
                this app. Ask about progress, what to do next, or how a feature works.
              </SheetDescription>
            </SheetHeader>
            <AiCoachChat
              compact={false}
              className="flex-1 mt-4 min-h-0"
              initialAssistantMessage={review?.comments}
            />
            <Link
              to="/ai-coach"
              className="text-xs text-primary hover:underline mt-3 inline-flex items-center gap-1"
              onClick={() => setChatOpen(false)}
            >
              <Maximize2 className="w-3 h-3" />
              Open full chat page
            </Link>
          </SheetContent>
        </Sheet>
        <Button type="button" size="sm" variant="outline" className="h-8 text-xs" asChild>
          <Link to="/ai-coach">
            <Maximize2 className="w-3.5 h-3.5 mr-1" />
            Full chat
          </Link>
        </Button>
      </div>

      <div className="flex items-center justify-between gap-2 text-[10px] text-muted-foreground uppercase tracking-wide">
        <Link to="/life-tracker" className="normal-case text-xs text-primary hover:underline">
          Log sleep & goals →
        </Link>
        <span>{source === "gemma" ? "Gemma / local AI" : "Template"}</span>
      </div>
    </div>
  );
}
