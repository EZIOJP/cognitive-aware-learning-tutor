import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router";
import { RefreshCw } from "lucide-react";
import { useAuth } from "../../context/AuthContext";
import { fetchInsightsDaily, fetchInsightsReview, type InsightsDailyPayload } from "../../api/hubClient";
import { Button } from "../../app/components/ui/button";

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

  const loadReview = useCallback(async (isRefresh = false) => {
    if (!isAuthenticated) {
      setLoading(false);
      return;
    }
    if (isRefresh) setRefreshing(true);
    else setLoading(true);
    const d = await fetchInsightsDaily();
    const r = await fetchInsightsReview();
    setDaily(d);
    setReview(r);
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
    <div className="space-y-3 text-sm">
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
      <p className="text-muted-foreground leading-relaxed">
        {review?.comments ?? "Log activity in Life Tracker or complete a quiz to build your review."}
      </p>
      {daily && (
        <p className="text-xs text-muted-foreground">
          Life {daily.life_score} · Study {daily.study_minutes}m · Vocab {daily.vocab_events} · Math{" "}
          {daily.math_attempts}
        </p>
      )}
      {review?.next_steps?.length ? (
        <ul className="text-xs space-y-1 list-disc list-inside text-foreground/80">
          {review.next_steps.slice(0, 3).map((s) => (
            <li key={s}>{s}</li>
          ))}
        </ul>
      ) : null}
      <div className="flex items-center justify-between gap-2">
        <Link to="/life-tracker" className="text-xs text-primary hover:underline">
          Log sleep & goals →
        </Link>
        <span className="text-[10px] text-muted-foreground uppercase tracking-wide">
          {source === "gemma" ? "Gemma" : "Template"}
        </span>
      </div>
    </div>
  );
}
