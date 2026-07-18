import { useState, useEffect } from "react";
import { AppWindow, Link2Off, TrendingUp } from "lucide-react";
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

function fmtDuration(seconds: number): string {
  if (seconds >= 3600) {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    return m > 0 ? `${h}h ${m}m` : `${h}h`;
  }
  if (seconds >= 60) return `${Math.floor(seconds / 60)}m`;
  return `${seconds}s`;
}

function scoreTone(score: number): string {
  if (score >= 70) return "text-teal-300";
  if (score >= 40) return "text-amber-300";
  return "text-rose-300";
}

function scoreBar(score: number): string {
  if (score >= 70) return "bg-teal-400";
  if (score >= 40) return "bg-amber-400";
  return "bg-rose-400";
}

/** Hub card: desktop tracker + browser sessions (legacy export name kept). */
export function BrowserActivityWidget() {
  return <DesktopActivityWidget />;
}

export function DesktopActivityWidget() {
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
    const interval = setInterval(fetchStats, 90_000);
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground py-6">
        <div className="w-2 h-2 rounded-full bg-teal-400/80 animate-pulse" />
        Loading activity…
      </div>
    );
  }

  if (!stats || !stats.connected) {
    return (
      <div className="space-y-3 py-2">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Link2Off className="w-4 h-4 text-rose-400/90 shrink-0" />
          <span>No live activity feed</span>
        </div>
        <p className="text-xs text-muted-foreground/75 leading-relaxed">
          Start the desktop tracker (and optional browser extension) so apps and sites show up here.
        </p>
      </div>
    );
  }

  const cats = Object.entries(stats.category_breakdown || {})
    .sort(([, a], [, b]) => b - a)
    .slice(0, 4);
  const catMax = Math.max(1, ...cats.map(([, n]) => n));
  const score = Math.max(0, Math.min(100, Number(stats.avg_productivity_score) || 0));
  const rows = (stats.top_domains || []).slice(0, 5);

  return (
    <div className="flex flex-col gap-3 min-h-0 h-full">
      {/* Status + score */}
      <div className="flex items-center justify-between gap-2">
        <span className="inline-flex items-center gap-1.5 rounded-full border border-teal-500/25 bg-teal-500/10 px-2 py-0.5 text-[10px] font-medium text-teal-200/95">
          <span className="relative flex h-1.5 w-1.5">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-teal-400 opacity-40" />
            <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-teal-400" />
          </span>
          Live · {stats.total_events} events
        </span>
        <span className={`inline-flex items-center gap-1 text-xs font-semibold tabular-nums ${scoreTone(score)}`}>
          <TrendingUp className="w-3.5 h-3.5 opacity-80" />
          {score}%
        </span>
      </div>

      {/* Productivity bar */}
      <div>
        <div className="flex items-center justify-between text-[10px] text-muted-foreground mb-1">
          <span>Focus mix today</span>
          <span className="tabular-nums">{score}% productive</span>
        </div>
        <div className="h-1.5 rounded-full bg-black/35 overflow-hidden border border-white/5">
          <div
            className={`h-full rounded-full transition-all duration-500 ${scoreBar(score)}`}
            style={{ width: `${score}%` }}
          />
        </div>
      </div>

      {/* Top mode */}
      <div className="rounded-lg border border-white/10 bg-black/25 px-2.5 py-2">
        <p className="text-[10px] uppercase tracking-wider text-muted-foreground/80">Top mode</p>
        <p className="text-sm font-medium text-foreground/95 truncate mt-0.5">
          {stats.top_category || "—"}
        </p>
      </div>

      {/* Category chips with mini bars */}
      {cats.length > 0 && (
        <div className="space-y-1.5">
          {cats.map(([cat, n]) => (
            <div key={cat} className="space-y-0.5">
              <div className="flex items-center justify-between gap-2 text-[10px]">
                <span className="text-muted-foreground truncate">{cat}</span>
                <span className="text-foreground/55 tabular-nums shrink-0">{n}</span>
              </div>
              <div className="h-1 rounded-full bg-muted/25 overflow-hidden">
                <div
                  className="h-full rounded-full bg-teal-500/55"
                  style={{ width: `${Math.round((n / catMax) * 100)}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Apps / sites */}
      {rows.length > 0 && (
        <div className="flex-1 min-h-0 space-y-0.5 overflow-hidden">
          <p className="text-[10px] uppercase tracking-wider text-muted-foreground/80 mb-1 flex items-center gap-1">
            <AppWindow className="w-3 h-3" />
            Top apps & sites
          </p>
          {rows.map(({ domain, seconds }) => (
            <div
              key={domain}
              className="flex items-center justify-between gap-2 rounded-md px-1.5 py-1 hover:bg-white/[0.04] transition-colors"
            >
              <span className="text-xs text-foreground/75 truncate min-w-0">{domain}</span>
              <span className="text-[11px] font-mono text-muted-foreground tabular-nums shrink-0">
                {fmtDuration(seconds)}
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
  const r = 20;
  const circ = 2 * Math.PI * r;
  const dash = (lifeScore / 100) * circ;
  const rows = Object.entries(breakdown).slice(0, 4);
  const label =
    lifeScore >= 80
      ? "Thriving"
      : lifeScore >= 60
        ? "On track"
        : lifeScore >= 40
          ? "Needs attention"
          : "Reset today";

  return (
    <div className="h-full min-h-0 grid grid-cols-[4.5rem_1fr] items-center gap-4">
      <div className="min-w-0">
        <div className="relative w-14 h-14 mx-auto">
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
        <p className="mt-1 text-[10px] text-muted-foreground text-center leading-tight">{label}</p>
      </div>

      <div className="grid grid-cols-2 gap-2 min-w-0">
        {rows.map(([pillar, score]) => (
          <div key={pillar} className="rounded-lg border border-white/10 bg-black/20 px-2.5 py-2 min-w-0">
            <div className="flex items-center justify-between gap-2">
              <span className="text-[10px] text-muted-foreground truncate">{pillar}</span>
              <span className="text-[11px] font-mono text-foreground/70 tabular-nums">{score}</span>
            </div>
            <div className="mt-1.5 h-1.5 bg-muted/30 rounded-full overflow-hidden">
              <div
                className="h-full rounded-full transition-all duration-500"
                style={{ width: `${score}%`, background: scoreColor }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
