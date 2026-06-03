import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router";
import {
  BookOpen,
  Layers,
  Clock,
  AlertTriangle,
  FileJson,
  Map,
  Route,
  Play,
  Target,
  Trophy,
  TrendingUp,
  Loader2,
  RefreshCw,
  Shield,
} from "lucide-react";
import { Card } from "../app/components/ui/card";
import { Button } from "../app/components/ui/button";
import { Badge } from "../app/components/ui/badge";
import { DashboardWidgetGrid } from "../components/dashboard/DashboardWidgetGrid";
import type { DashboardWidget } from "../components/dashboard/dashboardWidgetUtils";
import { CheckpointRoadmap, type CheckpointItem } from "../components/roadmap/CheckpointRoadmap";
import { getGroupsDetailed, getDashboardStats } from "../features/vocab/cycle/cycleService";
import type { GroupSummary } from "../features/vocab/cycle/types";
import { useAuth } from "../context/AuthContext";
import { hasVocabApi } from "../api/vocabClient";

const VOCAB_MODULES = [
  {
    key: "read",
    name: "Read Mode",
    icon: BookOpen,
    status: "live" as const,
    to: "/gre-vocab/read",
    description: "Browse all words with search, groups, and keyboard nav",
  },
  {
    key: "read-low",
    name: "Low Mastery",
    icon: AlertTriangle,
    status: "live" as const,
    to: "/gre-vocab/read/low-mastery",
    description: "Mastery 0 or below",
  },
  {
    key: "read-due",
    name: "Due Reviews",
    icon: Clock,
    status: "live" as const,
    to: "/gre-vocab/read/due",
    description: "Spaced repetition queue",
  },
  {
    key: "add-words",
    name: "Add Words (JSON)",
    icon: FileJson,
    status: "live" as const,
    to: "/gre-vocab/add-words",
    description: "Paste JSON — preview, validate, import (admin)",
  },
  {
    key: "cycle",
    name: "Cycle Manager",
    icon: Layers,
    status: "live" as const,
    to: "/gre-vocab/cycle",
    description: "Read → Quiz → Report per group, with low-mastery loops",
  },
];

function groupToCheckpoint(g: GroupSummary, i: number, groups: GroupSummary[]): CheckpointItem {
  const progress = g.total_words > 0 ? (g.words_mastered / g.total_words) * 100 : 0;
  const prev = groups[i - 1];
  const prevOk = !prev || prev.is_completed || prev.words_started >= prev.total_words * 0.5;
  let status: CheckpointItem["status"] = "available";
  if (g.is_completed || progress >= 90) status = "complete";
  else if (g.words_started > 0 || i === 0) status = "current";
  else if (!prevOk) status = "locked";
  return {
    id: String(g.group_number),
    label: `G${g.group_number}`,
    subtitle: `${g.words_mastered}/${g.total_words}`,
    progress,
    status,
    href: status !== "locked" ? "/gre-vocab/cycle" : undefined,
  };
}

export function GreVocabPage() {
  const { isAuthenticated, isAdmin } = useAuth();
  const [groups, setGroups] = useState<GroupSummary[]>([]);
  const [stats, setStats] = useState<Awaited<ReturnType<typeof getDashboardStats>> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [g, s] = await Promise.all([getGroupsDetailed(), getDashboardStats()]);
      setGroups(g);
      setStats(s);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load vocabulary data");
      setGroups([]);
      setStats(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload, isAuthenticated]);

  const roadmapItems = useMemo(
    () => groups.map((g, i) => groupToCheckpoint(g, i, groups)),
    [groups]
  );

  const widgets: DashboardWidget[] = useMemo(
    () => [
      {
        id: "vocab-hero",
        title: "Progress",
        icon: TrendingUp,
        accent: "from-violet-500/20 to-purple-500/10",
        defaultColSpan: 2,
        component: loading ? (
          <div className="flex items-center gap-2 text-sm text-muted-foreground py-4">
            <Loader2 className="w-4 h-4 animate-spin" />
            Loading stats…
          </div>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {[
              { label: "Studied", value: stats?.studied_words ?? "—", icon: Target },
              { label: "Mastered", value: stats?.mastered ?? "—", icon: Trophy },
              { label: "Due", value: stats?.due_reviews ?? "—", icon: Clock },
              {
                label: "Accuracy",
                value: stats != null ? `${stats.overall_accuracy}%` : "—",
                icon: TrendingUp,
              },
            ].map(({ label, value, icon: Icon }) => (
              <div
                key={label}
                className="rounded-xl border border-border/40 bg-background/30 p-3 text-center"
              >
                <Icon className="w-4 h-4 mx-auto mb-1 text-primary opacity-80" />
                <p className="text-lg font-bold tabular-nums">{value}</p>
                <p className="text-[10px] uppercase tracking-wide text-muted-foreground">
                  {label}
                </p>
              </div>
            ))}
          </div>
        ),
      },
      {
        id: "vocab-cta",
        title: "Study cycle",
        icon: Play,
        accent: "from-violet-500/25 to-indigo-500/15",
        defaultColSpan: 2,
        component: (
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 h-full">
            <div>
              <p className="text-sm text-muted-foreground mb-1">
                Read → quiz → report for each group of 30 words
              </p>
              <p className="text-xs text-muted-foreground">
                {stats?.study_coverage_pct ?? 0}% coverage · {groups.length} groups
                {hasVocabApi() ? " · synced to server" : " · offline demo"}
              </p>
            </div>
            <Button asChild size="lg" className="shrink-0" disabled={!!error && groups.length === 0}>
              <Link to="/gre-vocab/cycle">
                <Play className="w-4 h-4 mr-2" />
                Start study cycle
              </Link>
            </Button>
          </div>
        ),
      },
      {
        id: "vocab-checkpoints",
        title: "Group checkpoints",
        icon: Route,
        accent: "from-teal-500/15 to-emerald-500/10",
        defaultColSpan: 2,
        component: loading ? (
          <p className="text-sm text-muted-foreground flex items-center gap-2">
            <Loader2 className="w-4 h-4 animate-spin" />
            Loading groups…
          </p>
        ) : groups.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No word groups yet. Sign in and ensure the API is running, or import words in Admin.
          </p>
        ) : (
          <CheckpointRoadmap layout="horizontal" compact items={roadmapItems} />
        ),
      },
      {
        id: "vocab-modules",
        title: "Study modules",
        icon: Map,
        accent: "from-blue-500/15 to-indigo-500/10",
        defaultColSpan: 2,
        defaultRowSpan: 2,
        component: (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {VOCAB_MODULES.map(({ key, name, icon: Icon, status, to, description }) => (
              <Card key={key} className="p-3 flex flex-col border bg-background/40 gloss-panel">
                <div className="flex items-start justify-between mb-2">
                  <Icon className="w-5 h-5 text-violet-600 dark:text-violet-400" />
                  <Badge variant={status === "live" ? "default" : "secondary"} className="text-[10px]">
                    {status === "live" ? "Ready" : "Planned"}
                  </Badge>
                </div>
                <h4 className="font-medium text-sm mb-1">{name}</h4>
                <p className="text-xs text-muted-foreground mb-2 flex-1">{description}</p>
                {to ? (
                  <Link to={to} className="text-xs font-medium text-primary hover:underline">
                    Open →
                  </Link>
                ) : null}
              </Card>
            ))}
          </div>
        ),
      },
    ],
    [roadmapItems, stats, groups.length, loading, error]
  );

  return (
    <div className="space-y-3">
      {!isAuthenticated ? (
        <div className="mx-1 px-4 py-3 rounded-xl border border-primary/30 bg-primary/5 text-sm flex flex-wrap items-center justify-between gap-2">
          <span>Sign in so read progress, quizzes, and stats sync to your account.</span>
          <Link to="/login" className="font-medium text-primary hover:underline">
            Sign in
          </Link>
        </div>
      ) : null}

      {error ? (
        <div className="mx-1 px-4 py-3 rounded-xl border border-destructive/40 bg-destructive/10 text-sm flex flex-wrap items-center justify-between gap-2">
          <span>{error}</span>
          <Button type="button" size="sm" variant="outline" onClick={() => void reload()}>
            <RefreshCw className="w-3.5 h-3.5 mr-1" />
            Retry
          </Button>
        </div>
      ) : null}

      {isAdmin ? (
        <div className="mx-1 px-4 py-2 rounded-xl border border-border/50 flex items-center justify-between gap-2 text-sm">
          <span className="flex items-center gap-2 text-muted-foreground">
            <Shield className="w-4 h-4" />
            Admin: import words, reset users, export groups
          </span>
          <Link to="/admin" className="font-medium text-primary hover:underline">
            Open Admin Panel →
          </Link>
        </div>
      ) : null}

      <DashboardWidgetGrid
        storageKey="vocab-dash"
        title="GRE Vocabulary"
        subtitle="Adaptive quizzes, checkpoints, and read modes"
        widgets={widgets}
      />
    </div>
  );
}
