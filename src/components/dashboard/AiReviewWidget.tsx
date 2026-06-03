import { useEffect, useState } from "react";
import { Link } from "react-router";
import { useAuth } from "../../context/AuthContext";
import { fetchInsightsDaily, fetchInsightsReview, type InsightsDailyPayload } from "../../api/hubClient";

type Review = {
  comments: string;
  next_steps: string[];
  goals: string[];
  overall_performance: string;
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

  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!isAuthenticated) {
        setLoading(false);
        return;
      }
      const d = await fetchInsightsDaily();
      const r = await fetchInsightsReview();
      if (!cancelled) {
        setDaily(d);
        setReview(r);
        setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [isAuthenticated]);

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

  return (
    <div className="space-y-3 text-sm">
      <p className="text-lg font-semibold text-primary">{label}</p>
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
      <Link to="/life-tracker" className="text-xs text-primary hover:underline inline-block">
        Log sleep & goals →
      </Link>
    </div>
  );
}
