import { useState, useEffect } from "react";
import { Wifi, WifiOff, TrendingUp } from "lucide-react";
import { useGoalTracker } from "../context/GoalTrackerContext";

import { resolveApiUrl } from "../utils/resolveBackendUrl";
const TOKEN_KEY = "vocab:auth-token";

interface BehaviorStats {
  connected: boolean;
  total_events: number;
  top_category: string;
  avg_productivity_score: number;
  top_domains: { domain: string; seconds: number }[];
  recent_sites: string[];
  category_breakdown: Record<string, number>;
}

export function BrowserActivityWidget() {
  const [stats, setStats] = useState<BehaviorStats | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchStats = async () => {
    try {
      const headers: Record<string, string> = {};
      const token = localStorage.getItem(TOKEN_KEY);
      if (token) headers.Authorization = `Bearer ${token}`;
      const res = await fetch(`${resolveApiUrl()}/api/behavior/stats`, { headers });
      if (res.ok) {
        setStats(await res.json());
      } else {
        setStats(null);
      }
    } catch {
      setStats(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void fetchStats();
    const interval = setInterval(fetchStats, 30_000);
    return () => clearInterval(interval);
  }, []);

  const scoreColor = (score: number) =>
    score >= 70 ? "text-emerald-400" : score >= 40 ? "text-amber-400" : "text-rose-400";

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <div className="w-3 h-3 rounded-full bg-muted animate-pulse" />
        Loading browser activity…
      </div>
    );
  }

  if (!stats || !stats.connected) {
    return (
      <div className="space-y-2">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <WifiOff className="w-4 h-4 text-rose-400" />
          <span>Extension not connected</span>
        </div>
        <p className="text-xs text-muted-foreground/60">
          Install SelfTracker extension and sign in so events sync to the hub.
        </p>
      </div>
    );
  }

  const cats = Object.entries(stats.category_breakdown || {}).slice(0, 4);

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-xs text-emerald-400">
          <Wifi className="w-3.5 h-3.5" />
          <span>Live · {stats.total_events} events</span>
        </div>
        <div className={`text-sm font-semibold ${scoreColor(stats.avg_productivity_score)}`}>
          <TrendingUp className="w-3.5 h-3.5 inline mr-1" />
          {stats.avg_productivity_score}% productive
        </div>
      </div>

      <div className="text-xs font-medium text-foreground/80">
        Top mode: <span className="text-primary">{stats.top_category}</span>
      </div>

      {cats.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {cats.map(([cat, n]) => (
            <span key={cat} className="text-[10px] px-1.5 py-0.5 rounded bg-muted/50">
              {cat} {n}
            </span>
          ))}
        </div>
      )}

      {stats.top_domains.length > 0 && (
        <div className="space-y-1">
          {stats.top_domains.slice(0, 5).map(({ domain, seconds }) => (
            <div key={domain} className="flex items-center justify-between text-xs">
              <span className="text-muted-foreground truncate max-w-[160px]">{domain}</span>
              <span className="text-foreground/60 shrink-0">
                {seconds >= 60 ? `${Math.floor(seconds / 60)}m` : `${seconds}s`}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export function LifeScoreWidget() {
  const { lifeScore, breakdown } = useGoalTracker();
  const scoreColor = lifeScore >= 70 ? "#10b981" : lifeScore >= 45 ? "#f59e0b" : "#ef4444";
  const r = 24;
  const circ = 2 * Math.PI * r;
  const dash = (lifeScore / 100) * circ;

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-4">
        <div className="relative w-14 h-14 shrink-0">
          <svg className="w-full h-full -rotate-90" viewBox="0 0 60 60">
            <circle cx="30" cy="30" r={r} fill="none" stroke="currentColor" strokeWidth="5" className="text-muted/30" />
            <circle
              cx="30"
              cy="30"
              r={r}
              fill="none"
              stroke={scoreColor}
              strokeWidth="5"
              strokeLinecap="round"
              strokeDasharray={`${dash} ${circ}`}
              className="transition-all duration-700"
            />
          </svg>
          <span className="absolute inset-0 flex items-center justify-center text-sm font-bold">{lifeScore}</span>
        </div>
        <div className="space-y-1 flex-1">
          {Object.entries(breakdown).map(([pillar, score]) => (
            <div key={pillar} className="flex items-center gap-2 text-xs">
              <span className="text-muted-foreground w-24 shrink-0">{pillar}</span>
              <div className="flex-1 h-1.5 bg-muted/30 rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-500"
                  style={{ width: `${score}%`, background: scoreColor }}
                />
              </div>
              <span className="text-foreground/60 w-6 text-right">{score}</span>
            </div>
          ))}
        </div>
      </div>
      <p className="text-xs text-muted-foreground">Tap to log today&apos;s health, sleep & wellbeing →</p>
    </div>
  );
}
