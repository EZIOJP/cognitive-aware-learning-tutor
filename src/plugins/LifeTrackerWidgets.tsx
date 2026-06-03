import { useState, useEffect } from "react";
import { Wifi, WifiOff, TrendingUp } from "lucide-react";
import { useGoalTracker } from "../context/GoalTrackerContext";

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
      const res = await fetch("http://localhost:8000/api/behavior/stats");
      if (res.ok) {
        const data = await res.json();
        setStats(data);
      }
    } catch {
      setStats(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStats();
    const interval = setInterval(fetchStats, 30_000);
    return () => clearInterval(interval);
  }, []);

  const scoreColor = (score: number) =>
    score >= 70 ? "text-emerald-400" : score >= 40 ? "text-amber-400" : "text-rose-400";

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <div className="w-3 h-3 rounded-full bg-muted animate-pulse" />
        Connecting to extension...
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
          Install the SelfTracker extension and make sure the backend is running.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-xs text-emerald-400">
          <Wifi className="w-3.5 h-3.5" />
          <span>Live · {stats.total_events} events today</span>
        </div>
        <div className={`text-sm font-semibold ${scoreColor(stats.avg_productivity_score)}`}>
          <TrendingUp className="w-3.5 h-3.5 inline mr-1" />
          {stats.avg_productivity_score}% productive
        </div>
      </div>

      <div className="text-xs font-medium text-foreground/80">
        Top mode: <span className="text-primary">{stats.top_category}</span>
      </div>

      {stats.top_domains.length > 0 && (
        <div className="space-y-1">
          {stats.top_domains.slice(0, 3).map(({ domain, seconds }) => (
            <div key={domain} className="flex items-center justify-between text-xs">
              <span className="text-muted-foreground truncate max-w-[140px]">{domain}</span>
              <span className="text-foreground/60 shrink-0">
                {Math.floor(seconds / 60)}m {seconds % 60}s
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
            <circle cx="30" cy="30" r={r} fill="none" stroke={scoreColor} strokeWidth="5" strokeLinecap="round"
              strokeDasharray={`${dash} ${circ}`} className="transition-all duration-700" />
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
      <p className="text-xs text-muted-foreground">Tap to log today's health, sleep & wellbeing →</p>
    </div>
  );
}
