import { useState } from "react";
import { useGoalTracker, computeScores } from "../context/GoalTrackerContext";
import { LifeClockWidget } from "../components/hub/LifeClockWidget";
import { FaceTrackerPanel } from "../components/face/FaceTrackerPanel";
import { usePlugins } from "../plugins/registry";
import {
  Moon,
  Dumbbell,
  Droplets,
  Brain,
  Monitor,
  TreePine,
  Smile,
  Clock,
  CheckSquare,
  TrendingUp,
  ChevronDown,
  ChevronUp,
  Flame,
  RefreshCw,
  Watch,
} from "lucide-react";
import { Card } from "../app/components/ui/card";
import { useEaster, useLongPress } from "../easter";

function ScoreRing({ score, label, color }: { score: number; label: string; color: string }) {
  const r = 28;
  const circ = 2 * Math.PI * r;
  const dash = (score / 100) * circ;

  return (
    <div className="flex flex-col items-center gap-1">
      <div className="relative w-16 h-16">
        <svg className="w-full h-full -rotate-90" viewBox="0 0 70 70">
          <circle cx="35" cy="35" r={r} fill="none" stroke="currentColor" strokeWidth="6" className="text-muted/30" />
          <circle
            cx="35"
            cy="35"
            r={r}
            fill="none"
            stroke={color}
            strokeWidth="6"
            strokeLinecap="round"
            strokeDasharray={`${dash} ${circ}`}
            className="transition-all duration-700"
          />
        </svg>
        <span className="absolute inset-0 flex items-center justify-center text-sm font-bold">{score}</span>
      </div>
      <span className="text-xs text-muted-foreground text-center leading-tight">{label}</span>
    </div>
  );
}

function StatRow({
  icon: Icon,
  label,
  value,
  unit,
  source,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: number | string;
  unit?: string;
  source?: string;
}) {
  return (
    <div className="flex items-center gap-3">
      <Icon className="w-4 h-4 text-muted-foreground shrink-0" />
      <span className="text-xs text-muted-foreground w-28 shrink-0">{label}</span>
      <span className="text-sm font-semibold flex-1">
        {value}
        {unit ? <span className="text-xs font-normal text-muted-foreground ml-1">{unit}</span> : null}
      </span>
      {source ? (
        <span className="text-[10px] uppercase tracking-wide text-muted-foreground">{source}</span>
      ) : null}
    </div>
  );
}

const PILLAR_COLORS: Record<string, string> = {
  Health: "#10b981",
  Productivity: "#6366f1",
  "Digital Wellbeing": "#f59e0b",
  Mental: "#ec4899",
};

export function LifeTrackerPage() {
  const { today, history, refreshToday, lifeScore, breakdown } = useGoalTracker();
  const { burst } = useEaster();
  const scoreEgg = useLongPress(700, () => burst("fireworks"));
  const [expandedPillar, setExpandedPillar] = useState<string | null>("Health");
  const [refreshing, setRefreshing] = useState(false);

  const scoreLabel =
    lifeScore >= 80
      ? "Thriving"
      : lifeScore >= 60
        ? "On Track"
        : lifeScore >= 40
          ? "Needs Attention"
          : "Rest & Reset";

  const last7 = history.slice(-7);
  const { enabledIds } = usePlugins();

  const onRefresh = async () => {
    setRefreshing(true);
    try {
      await refreshToday();
    } finally {
      setRefreshing(false);
    }
  };

  return (
    <div className="h-full min-h-0 overflow-y-auto bg-background text-foreground">
      <div className="mx-auto w-full max-w-7xl space-y-6 pb-10">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h1 className="text-2xl font-bold">Life Tracker</h1>
            <p className="text-sm text-muted-foreground">
              Read-only dashboard — sleep &amp; exercise from Amazfit sync; study from Pomodoro.
              Manual entry is off.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => void onRefresh()}
              className="inline-flex items-center gap-1.5 rounded-lg border border-border/50 px-3 py-1.5 text-xs hover:bg-muted/40"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? "animate-spin" : ""}`} />
              Refresh
            </button>
            <p className="text-xs text-muted-foreground">
              {new Date().toLocaleDateString("en-US", {
                weekday: "long",
                month: "long",
                day: "numeric",
              })}
            </p>
          </div>
        </div>

        <div className="rounded-xl border border-primary/20 bg-primary/5 px-4 py-3 text-xs text-muted-foreground flex flex-wrap gap-2 items-center">
          <Watch className="w-4 h-4 text-primary shrink-0" />
          <span>
            Health numbers update when the watch posts to{" "}
            <code className="text-foreground">/api/wearables/zepp</code>. Check{" "}
            <strong className="text-foreground font-medium">Productivity → Settings → Amazfit</strong>{" "}
            for live sync proof (source must be <code className="text-foreground">mini_program</code>
            , not <code className="text-foreground">web_test</code>).
          </span>
        </div>

        <div className="grid gap-6 xl:grid-cols-[minmax(0,1.15fr)_minmax(22rem,0.85fr)]">
          <div className="space-y-6 min-w-0">
            <section className="gloss-panel rounded-2xl p-5">
              <LifeClockWidget embedded showLegend={false} />
            </section>

            {enabledIds.includes("focus-mirror") && <FaceTrackerPanel />}
          </div>

          <div className="space-y-6 min-w-0">
            <div className="gloss-panel rounded-2xl p-6">
              <div className="flex items-center gap-3 mb-4">
                <div className="relative w-20 h-20 cursor-pointer select-none" {...scoreEgg} title="Long-press…">
                  <svg className="w-full h-full -rotate-90" viewBox="0 0 80 80">
                    <circle
                      cx="40"
                      cy="40"
                      r="34"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="7"
                      className="text-muted/30"
                    />
                    <circle
                      cx="40"
                      cy="40"
                      r="34"
                      fill="none"
                      stroke={lifeScore >= 70 ? "#10b981" : lifeScore >= 45 ? "#f59e0b" : "#ef4444"}
                      strokeWidth="7"
                      strokeLinecap="round"
                      strokeDasharray={`${(lifeScore / 100) * (2 * Math.PI * 34)} ${2 * Math.PI * 34}`}
                      className="transition-all duration-1000"
                    />
                  </svg>
                  <div className="absolute inset-0 flex flex-col items-center justify-center">
                    <span className="text-xl font-bold leading-none">{lifeScore}</span>
                    <span className="text-[10px] text-muted-foreground">/ 100</span>
                  </div>
                </div>
                <div>
                  <h2 className="text-2xl font-semibold">Life Score</h2>
                  <p className="text-muted-foreground text-sm">{scoreLabel}</p>
                </div>
              </div>

              <div className="flex gap-4 justify-around flex-wrap">
                {Object.entries(breakdown).map(([pillar, score]) => (
                  <ScoreRing
                    key={pillar}
                    score={score}
                    label={pillar}
                    color={PILLAR_COLORS[pillar] || "#6366f1"}
                  />
                ))}
              </div>
            </div>

            {last7.length >= 2 && (
              <div className="gloss-panel rounded-2xl p-4">
                <div className="flex items-center gap-2 mb-3">
                  <TrendingUp className="w-4 h-4 text-primary" />
                  <span className="text-sm font-medium">7-Day Life Score Trend</span>
                </div>
                <div className="flex items-end gap-1 h-12">
                  {last7.map((entry) => {
                    const { lifeScore: s } = computeScores(entry);
                    return (
                      <div key={entry.date} className="flex-1 flex flex-col items-center gap-1">
                        <div
                          className="w-full rounded-sm transition-all duration-500"
                          style={{
                            height: `${Math.max(4, (s / 100) * 40)}px`,
                            background: s >= 70 ? "#10b981" : s >= 45 ? "#f59e0b" : "#ef4444",
                            opacity: 0.8,
                          }}
                          title={`${entry.date}: ${s}`}
                        />
                        <span className="text-[9px] text-muted-foreground">{entry.date.slice(5)}</span>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        </div>

        <div className="grid gap-4 lg:grid-cols-2">
          <Card className="gloss-panel rounded-2xl overflow-hidden min-w-0">
            <button
              type="button"
              className="w-full flex items-center justify-between p-4 hover:bg-muted/20 transition-colors"
              onClick={() => setExpandedPillar(expandedPillar === "Health" ? null : "Health")}
            >
              <div className="flex items-center gap-2">
                <Flame className="w-5 h-5 text-emerald-400" />
                <span className="font-semibold">Health</span>
                <span className="text-sm text-muted-foreground">— {breakdown.Health}/100</span>
              </div>
              {expandedPillar === "Health" ? (
                <ChevronUp className="w-4 h-4" />
              ) : (
                <ChevronDown className="w-4 h-4" />
              )}
            </button>
            {expandedPillar === "Health" && (
              <div className="px-4 pb-4 space-y-3 border-t border-border/40 pt-3">
                <StatRow
                  icon={Moon}
                  label="Sleep hours"
                  value={today.sleepHours}
                  unit="h"
                  source="watch"
                />
                <StatRow
                  icon={Moon}
                  label="Sleep quality"
                  value={`${today.sleepQuality}/5`}
                  source="watch"
                />
                <StatRow
                  icon={Dumbbell}
                  label="Exercise"
                  value={today.exerciseMinutes}
                  unit="min"
                  source="steps est."
                />
                <StatRow icon={Droplets} label="Water glasses" value={today.waterGlasses} source="—" />
                <StatRow icon={Smile} label="Healthy meals" value={today.mealsHealthy} source="—" />
              </div>
            )}
          </Card>

          <Card className="gloss-panel rounded-2xl overflow-hidden min-w-0">
            <button
              type="button"
              className="w-full flex items-center justify-between p-4 hover:bg-muted/20 transition-colors"
              onClick={() =>
                setExpandedPillar(expandedPillar === "Productivity" ? null : "Productivity")
              }
            >
              <div className="flex items-center gap-2">
                <Brain className="w-5 h-5 text-indigo-400" />
                <span className="font-semibold">Productivity</span>
                <span className="text-sm text-muted-foreground">— {breakdown.Productivity}/100</span>
              </div>
              {expandedPillar === "Productivity" ? (
                <ChevronUp className="w-4 h-4" />
              ) : (
                <ChevronDown className="w-4 h-4" />
              )}
            </button>
            {expandedPillar === "Productivity" && (
              <div className="px-4 pb-4 space-y-3 border-t border-border/40 pt-3">
                <StatRow
                  icon={Clock}
                  label="Study time"
                  value={today.studyMinutes}
                  unit="min"
                  source="pomodoro"
                />
                <StatRow icon={CheckSquare} label="Tasks done" value={today.tasksCompleted} source="—" />
                <StatRow
                  icon={Brain}
                  label="Deep work blocks"
                  value={today.deepWorkBlocks}
                  source="—"
                />
              </div>
            )}
          </Card>

          <Card className="gloss-panel rounded-2xl overflow-hidden min-w-0">
            <button
              type="button"
              className="w-full flex items-center justify-between p-4 hover:bg-muted/20 transition-colors"
              onClick={() =>
                setExpandedPillar(
                  expandedPillar === "Digital Wellbeing" ? null : "Digital Wellbeing",
                )
              }
            >
              <div className="flex items-center gap-2">
                <Monitor className="w-5 h-5 text-amber-400" />
                <span className="font-semibold">Digital Wellbeing</span>
                <span className="text-sm text-muted-foreground">
                  — {breakdown["Digital Wellbeing"]}/100
                </span>
              </div>
              {expandedPillar === "Digital Wellbeing" ? (
                <ChevronUp className="w-4 h-4" />
              ) : (
                <ChevronDown className="w-4 h-4" />
              )}
            </button>
            {expandedPillar === "Digital Wellbeing" && (
              <div className="px-4 pb-4 space-y-3 border-t border-border/40 pt-3">
                <StatRow
                  icon={Monitor}
                  label="Screen time"
                  value={today.screenTimeHours}
                  unit="h"
                  source="—"
                />
                <StatRow
                  icon={Monitor}
                  label="Social media"
                  value={today.socialMediaMinutes}
                  unit="min"
                  source="—"
                />
                <StatRow
                  icon={TreePine}
                  label="Outdoors"
                  value={today.outdoorMinutes}
                  unit="min"
                  source="—"
                />
              </div>
            )}
          </Card>

          <Card className="gloss-panel rounded-2xl overflow-hidden min-w-0">
            <button
              type="button"
              className="w-full flex items-center justify-between p-4 hover:bg-muted/20 transition-colors"
              onClick={() => setExpandedPillar(expandedPillar === "Mental" ? null : "Mental")}
            >
              <div className="flex items-center gap-2">
                <Smile className="w-5 h-5 text-pink-400" />
                <span className="font-semibold">Mental & Mindfulness</span>
                <span className="text-sm text-muted-foreground">— {breakdown.Mental}/100</span>
              </div>
              {expandedPillar === "Mental" ? (
                <ChevronUp className="w-4 h-4" />
              ) : (
                <ChevronDown className="w-4 h-4" />
              )}
            </button>
            {expandedPillar === "Mental" && (
              <div className="px-4 pb-4 space-y-3 border-t border-border/40 pt-3">
                <StatRow icon={Smile} label="Mood" value={`${today.moodScore}/5`} source="—" />
                <StatRow icon={Smile} label="Stress level" value={`${today.stressLevel}/5`} source="—" />
                <StatRow
                  icon={Brain}
                  label="Meditation"
                  value={today.meditationMinutes}
                  unit="min"
                  source="—"
                />
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}
