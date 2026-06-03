import { useEffect, useState } from "react";
import { Link } from "react-router";
import { Layers, Loader2, ArrowLeft, Play } from "lucide-react";
import { Button } from "../../../../app/components/ui/button";
import { Card } from "../../../../app/components/ui/card";
import { Progress } from "../../../../app/components/ui/progress";
import {
  getDashboardStats,
  getGroupsDetailed,
  loadGroupWords,
} from "../cycleService";
import type { CycleGroupStart, GroupSummary } from "../types";

interface CycleDashboardProps {
  onStartCycle: (data: CycleGroupStart) => void;
}

export function CycleDashboard({ onStartCycle }: CycleDashboardProps) {
  const [groups, setGroups] = useState<GroupSummary[]>([]);
  const [stats, setStats] = useState<{
    total_groups: number;
    total_words: number;
    studied_words: number;
    mastered: number;
    due_reviews: number;
    low_mastery: number;
    struggling: number;
    suspended_words: number;
    overall_accuracy: number;
    study_coverage_pct: number;
    last_activity?: string | null;
  } | null>(null);
  const [loading, setLoading] = useState(true);
  const [startingGroup, setStartingGroup] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const [g, s] = await Promise.all([
        getGroupsDetailed(),
        getDashboardStats(),
      ]);
      setGroups(g);
      setStats(s);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleStart = async (group: GroupSummary) => {
    setStartingGroup(group.group_number);
    try {
      const words = await loadGroupWords(group.group_number);
      onStartCycle({
        groupNumber: group.group_number,
        totalWords: group.total_words,
        wordsStarted: group.words_started,
        wordsMastered: group.words_mastered,
        isCompleted: group.is_completed,
        words,
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load group");
    } finally {
      setStartingGroup(null);
    }
  };

  if (loading) {
    return (
      <div className="h-full flex flex-col items-center justify-center gap-3">
        <Loader2 className="w-8 h-8 animate-spin" />
        <p className="text-sm text-muted-foreground">Loading groups…</p>
      </div>
    );
  }

  if (error && groups.length === 0) {
    return (
      <div className="text-center p-8">
        <p className="text-destructive mb-4">{error}</p>
        <Button onClick={load}>Retry</Button>
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto space-y-4 pb-6">
      <div className="gloss-panel rounded-2xl p-4 flex flex-wrap items-center gap-3">
        <Link
          to="/gre-vocab"
          className="gloss-dock-btn inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          GRE Vocab
        </Link>
        <div className="flex items-center gap-2 flex-1 min-w-0">
          <Layers className="w-5 h-5 text-primary shrink-0" />
          <div>
            <h1 className="text-lg font-semibold">Cycle Manager</h1>
            <p className="text-xs text-muted-foreground">
              Read → Quiz → Report → repeat low mastery
            </p>
          </div>
        </div>
      </div>

      {stats && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {[
            { label: "Words", value: stats.total_words },
            { label: "Studied", value: stats.studied_words },
            { label: "Mastered", value: stats.mastered },
            { label: "Due", value: stats.due_reviews },
            { label: "Low mastery", value: stats.low_mastery },
            { label: "Accuracy %", value: stats.overall_accuracy },
            { label: "Coverage %", value: stats.study_coverage_pct },
            { label: "Suspended", value: stats.suspended_words },
          ].map(({ label, value }) => (
            <Card key={label} className="gloss-panel p-3 text-center">
              <div className="text-xl font-bold font-mono">{value}</div>
              <div className="text-[11px] text-muted-foreground">{label}</div>
            </Card>
          ))}
        </div>
      )}

      {stats?.last_activity && (
        <Card className="gloss-panel p-3 text-sm text-muted-foreground">
          Last activity: {new Date(stats.last_activity).toLocaleString()}
        </Card>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {groups.map((group) => {
          const status =
            group.completion_percentage >= 80
              ? "completed"
              : group.words_started > 0
                ? "in-progress"
                : "new";

          return (
            <Card key={group.group_number} className="gloss-panel p-4 flex flex-col">
              <div className="flex items-start justify-between mb-3">
                <div>
                  <h3 className="font-semibold">Group {group.group_number}</h3>
                  <p className="text-xs text-muted-foreground">
                    {group.total_words} words
                  </p>
                </div>
                <span className="text-lg">
                  {status === "completed" ? "✅" : status === "in-progress" ? "🔄" : "📚"}
                </span>
              </div>

              <div className="mb-3">
                <div className="flex justify-between text-xs mb-1">
                  <span>Progress</span>
                  <span className="font-mono">{group.completion_percentage}%</span>
                </div>
                <Progress value={group.completion_percentage} className="h-2" />
              </div>

              <div className="grid grid-cols-2 gap-2 text-center text-xs mb-4">
                <div className="rounded-lg bg-green-500/10 p-2">
                  <div className="font-bold text-green-600 dark:text-green-400">
                    {group.stats.mastered}
                  </div>
                  <div className="text-muted-foreground">Mastered</div>
                </div>
                <div className="rounded-lg bg-amber-500/10 p-2">
                  <div className="font-bold text-amber-600 dark:text-amber-400">
                    {group.stats.needPractice}
                  </div>
                  <div className="text-muted-foreground">Practice</div>
                </div>
              </div>

              <Button
                className="w-full mt-auto"
                disabled={startingGroup === group.group_number}
                onClick={() => handleStart(group)}
              >
                {startingGroup === group.group_number ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <>
                    <Play className="w-4 h-4 mr-2" />
                    {status === "completed" ? "Review" : status === "in-progress" ? "Continue" : "Start"}
                  </>
                )}
              </Button>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
