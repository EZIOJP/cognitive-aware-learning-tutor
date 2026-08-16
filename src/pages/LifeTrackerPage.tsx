import { Children, useCallback, useEffect, useMemo, useState, type ComponentType, type ReactNode } from "react";
import {
  computeScores,
  type DailyEntry,
} from "../context/GoalTrackerContext";
import { LifeClockWidget } from "../components/hub/LifeClockWidget";
import { FaceTrackerPanel } from "../components/face/FaceTrackerPanel";
import { usePlugins } from "../plugins/registry";
import { fetchLifeDaily, type LifeDailyApi } from "../api/hubClient";
import { fetchWearableDay, type WearableDay } from "../api/wearablesClient";
import { WatchDayDumpCard } from "../components/life/WatchDayDumpCard";
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
  ChevronLeft,
  ChevronRight,
  Flame,
  RefreshCw,
  Watch,
} from "lucide-react";
import { Card } from "../app/components/ui/card";
import { useEaster, useLongPress } from "../easter";

function localDateKey(d = new Date()): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function shiftDay(key: string, delta: number): string {
  const [y, m, d] = key.split("-").map(Number);
  const dt = new Date(y, m - 1, d);
  dt.setDate(dt.getDate() + delta);
  return localDateKey(dt);
}

function formatDayLabel(key: string): string {
  const [y, m, d] = key.split("-").map(Number);
  const dt = new Date(y, m - 1, d);
  return dt.toLocaleDateString("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
  });
}

function emptyEntry(date: string): DailyEntry {
  return {
    date,
    sleepHours: 0,
    sleepQuality: 3,
    exerciseMinutes: 0,
    waterGlasses: 0,
    mealsHealthy: 0,
    studyMinutes: 0,
    tasksCompleted: 0,
    deepWorkBlocks: 0,
    screenTimeHours: 0,
    socialMediaMinutes: 0,
    outdoorMinutes: 0,
    moodScore: 3,
    stressLevel: 3,
    meditationMinutes: 0,
  };
}

function apiToEntry(row: LifeDailyApi | null, fallbackDate: string): DailyEntry {
  const base = emptyEntry(fallbackDate);
  if (!row || row.empty) return base;
  return {
    ...base,
    date: (row.date || fallbackDate).slice(0, 10),
    sleepHours: row.sleep_hours ?? 0,
    sleepQuality: row.sleep_quality ?? 3,
    exerciseMinutes: row.exercise_minutes ?? 0,
    waterGlasses: row.water_glasses ?? 0,
    mealsHealthy: row.meals_healthy ?? 0,
    studyMinutes: row.study_minutes ?? 0,
    tasksCompleted: row.tasks_completed ?? 0,
    deepWorkBlocks: row.deep_work_blocks ?? 0,
    screenTimeHours: row.screen_time_hours ?? 0,
    socialMediaMinutes: row.social_media_minutes ?? 0,
    outdoorMinutes: row.outdoor_minutes ?? 0,
    moodScore: row.mood_score ?? 3,
    stressLevel: row.stress_level ?? 3,
    meditationMinutes: row.meditation_minutes ?? 0,
  };
}

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
  icon: ComponentType<{ className?: string }>;
  label: string;
  value: number | string;
  unit?: string;
  source?: string;
}) {
  const unmarked = !source || source === "—";
  if (unmarked) return null;

  return (
    <div className="flex items-center gap-3">
      <Icon className="w-4 h-4 text-muted-foreground shrink-0" />
      <span className="text-xs text-muted-foreground w-28 shrink-0">{label}</span>
      <span className="text-sm font-semibold flex-1">
        {value}
        {unit ? <span className="text-xs font-normal text-muted-foreground ml-1">{unit}</span> : null}
      </span>
      <span className="text-[10px] uppercase tracking-wide text-muted-foreground">{source}</span>
    </div>
  );
}

function PillarEmptyHint() {
  return (
    <p className="text-xs text-muted-foreground py-1">
      No sourced inputs for this day yet — score uses defaults until sensors or habits fill in.
    </p>
  );
}

function PillarBody({ children }: { children: ReactNode }) {
  const rows = Children.toArray(children).filter(Boolean);
  if (rows.length === 0) return <PillarEmptyHint />;
  return <>{rows}</>;
}

const PILLAR_COLORS: Record<string, string> = {
  Health: "#10b981",
  Productivity: "#6366f1",
  "Digital Wellbeing": "#f59e0b",
  Mental: "#ec4899",
};

export function LifeTrackerPage() {
  const { burst } = useEaster();
  const scoreEgg = useLongPress(700, () => burst("fireworks"));
  const [expandedPillar, setExpandedPillar] = useState<string | null>("Health");
  const [refreshing, setRefreshing] = useState(false);
  const [selectedDay, setSelectedDay] = useState(() => localDateKey());
  const [entry, setEntry] = useState<DailyEntry>(() => emptyEntry(localDateKey()));
  const [history, setHistory] = useState<DailyEntry[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [wearableDay, setWearableDay] = useState<WearableDay | null>(null);

  const todayKey = localDateKey();
  const isToday = selectedDay === todayKey;
  const canGoNext = selectedDay < todayKey;

  const { lifeScore, breakdown } = useMemo(() => computeScores(entry), [entry]);

  const loadDay = useCallback(async (day: string) => {
    setLoadError(null);
    const apiDay = day === todayKey ? "today" : day;
    const [remote, watch] = await Promise.all([
      fetchLifeDaily(apiDay),
      fetchWearableDay(day).catch(() => null),
    ]);
    setWearableDay(watch);
    if (!remote) {
      setLoadError("Could not load that day from the API");
      setEntry(emptyEntry(day));
      return;
    }
    setEntry(apiToEntry(remote, day));
  }, [todayKey]);

  const loadHistory = useCallback(async () => {
    const days: string[] = [];
    for (let i = 13; i >= 0; i--) {
      days.push(shiftDay(todayKey, -i));
    }
    const rows = await Promise.all(
      days.map(async (d) => {
        const remote = await fetchLifeDaily(d === todayKey ? "today" : d);
        return apiToEntry(remote, d);
      }),
    );
    setHistory(rows);
  }, [todayKey]);

  useEffect(() => {
    void loadDay(selectedDay);
  }, [selectedDay, loadDay]);

  useEffect(() => {
    void loadHistory();
  }, [loadHistory]);

  const onRefresh = async () => {
    setRefreshing(true);
    try {
      await Promise.all([loadDay(selectedDay), loadHistory()]);
      window.dispatchEvent(new CustomEvent("hub:refresh"));
    } finally {
      setRefreshing(false);
    }
  };

  const scoreLabel =
    lifeScore >= 80
      ? "Thriving"
      : lifeScore >= 60
        ? "On Track"
        : lifeScore >= 40
          ? "Needs Attention"
          : "Rest & Reset";

  const chartDays = history.slice(-14);
  const { enabledIds } = usePlugins();

  return (
    <div className="life-tracker-page h-full min-h-0 overflow-y-auto bg-background text-foreground">
      <div className="life-tracker-shell mx-auto w-full max-w-7xl space-y-6 pb-10">
        <header className="life-tracker-hero">
          <div className="life-tracker-hero__copy">
            <span className="life-tracker-hero__eyebrow">Daily wellbeing</span>
            <h1>Life Tracker</h1>
            <p>
              Your sleep, movement, focus, and digital balance — organized around one day at a time.
            </p>
          </div>
          <div className="life-tracker-hero__controls flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => void onRefresh()}
              className="inline-flex items-center gap-1.5 rounded-lg border border-border/50 px-3 py-1.5 text-xs hover:bg-muted/40"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? "animate-spin" : ""}`} />
              Refresh
            </button>
            <div className="life-tracker-daynav inline-flex items-center gap-1 rounded-lg border border-border/50 p-0.5">
              <button
                type="button"
                aria-label="Previous day"
                className="life-tracker-daynav__btn rounded-md p-1.5"
                onClick={() => setSelectedDay((d) => shiftDay(d, -1))}
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <button
                type="button"
                className="life-tracker-daynav__btn min-w-[11rem] px-2 py-1 text-xs tabular-nums rounded-md"
                onClick={() => setSelectedDay(todayKey)}
                title="Jump to today"
              >
                {formatDayLabel(selectedDay)}
                {!isToday ? (
                  <span className="ml-1 text-muted-foreground">(not today)</span>
                ) : null}
              </button>
              <button
                type="button"
                aria-label="Next day"
                className="life-tracker-daynav__btn rounded-md p-1.5 disabled:opacity-30"
                disabled={!canGoNext}
                onClick={() => setSelectedDay((d) => shiftDay(d, 1))}
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
            {!isToday && (
              <button
                type="button"
                className="rounded-lg border border-primary/40 bg-primary/10 px-2.5 py-1.5 text-xs text-primary"
                onClick={() => setSelectedDay(todayKey)}
              >
                Today
              </button>
            )}
          </div>
        </header>

        {loadError && (
          <p className="text-sm text-rose-300">{loadError}</p>
        )}

        <div className="life-tracker-source">
          <Watch className="w-4 h-4 shrink-0" />
          <span>Watch-connected day</span>
          <span className="life-tracker-source__dot" />
          <span>Sleep &amp; activity update from Amazfit sync</span>
        </div>

        <section className="life-tracker-watch gloss-panel rounded-2xl p-5">
          <div className="life-tracker-section-heading">
            <div>
              <span>Watch insights</span>
              <h2>Day from your watch</h2>
            </div>
            <span className="life-tracker-section-heading__day">{formatDayLabel(selectedDay)}</span>
          </div>
          <p className="life-tracker-watch__hint">
            Sleep, steps, and vitals for this day in one view. Zeros and missing sensors stay hidden.
          </p>
          <WatchDayDumpCard day={wearableDay} />
        </section>

        <div className="life-tracker-overview grid gap-6 xl:grid-cols-[minmax(0,1.25fr)_minmax(22rem,0.75fr)]">
          <div className="life-tracker-clock min-w-0">
            <section className="gloss-panel rounded-2xl p-5">
              <div className="life-tracker-section-heading life-tracker-section-heading--compact">
                <div>
                  <span>Day in view</span>
                  <h2>Time balance</h2>
                </div>
              </div>
              <LifeClockWidget embedded showLegend={false} day={selectedDay} />
            </section>

            {enabledIds.includes("focus-mirror") && <FaceTrackerPanel />}
          </div>

          <aside className="life-tracker-summary space-y-6 min-w-0">
            <div className="life-tracker-score gloss-panel rounded-2xl p-6">
              <span className="life-tracker-score__eyebrow">Today’s balance</span>
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

              <div className="life-tracker-score__pillars flex gap-4 justify-around flex-wrap">
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

            {chartDays.length >= 2 && (
              <div className="life-tracker-trend gloss-panel rounded-2xl p-4">
                <div className="flex items-center gap-2 mb-3">
                  <TrendingUp className="w-4 h-4 text-primary" />
                  <span className="text-sm font-medium">14-Day Life Score Trend</span>
                  <span className="text-[10px] text-muted-foreground">click a bar to open that day</span>
                </div>
                <div className="flex items-end gap-1 h-12">
                  {chartDays.map((histEntry) => {
                    const { lifeScore: s } = computeScores(histEntry);
                    const active = histEntry.date === selectedDay;
                    return (
                      <button
                        key={histEntry.date}
                        type="button"
                        className="flex-1 flex flex-col items-center gap-1 group"
                        onClick={() => setSelectedDay(histEntry.date)}
                        title={`${histEntry.date}: ${s}`}
                      >
                        <div
                          className={`w-full rounded-sm transition-all duration-300 ${active ? "ring-2 ring-primary" : "opacity-80 group-hover:opacity-100"}`}
                          style={{
                            height: `${Math.max(4, (s / 100) * 40)}px`,
                            background: s >= 70 ? "#10b981" : s >= 45 ? "#f59e0b" : "#ef4444",
                          }}
                        />
                        <span className="text-[9px] text-muted-foreground">{histEntry.date.slice(5)}</span>
                      </button>
                    );
                  })}
                </div>
              </div>
            )}
          </aside>
        </div>

        <section className="life-tracker-pillars">
          <div className="life-tracker-section-heading">
            <div>
              <span>Your systems</span>
              <h2>Daily pillars</h2>
            </div>
            <p>Open a pillar to see the inputs behind its score.</p>
          </div>
        <div className="life-tracker-pillars__grid grid gap-4 lg:grid-cols-2">
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
                <PillarBody>
                  <StatRow icon={Moon} label="Sleep hours" value={entry.sleepHours} unit="h" source="watch" />
                  <StatRow
                    icon={Moon}
                    label="Sleep quality"
                    value={`${entry.sleepQuality}/5`}
                    source="watch"
                  />
                  <StatRow
                    icon={Dumbbell}
                    label="Exercise"
                    value={entry.exerciseMinutes}
                    unit="min"
                    source="steps est."
                  />
                  <StatRow icon={Droplets} label="Water glasses" value={entry.waterGlasses} source="—" />
                  <StatRow icon={Smile} label="Healthy meals" value={entry.mealsHealthy} source="—" />
                </PillarBody>
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
                <PillarBody>
                  <StatRow
                    icon={Clock}
                    label="Study time"
                    value={entry.studyMinutes}
                    unit="min"
                    source="pomodoro"
                  />
                  <StatRow icon={CheckSquare} label="Tasks done" value={entry.tasksCompleted} source="—" />
                  <StatRow
                    icon={Brain}
                    label="Deep work blocks"
                    value={entry.deepWorkBlocks}
                    source="—"
                  />
                </PillarBody>
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
                <PillarBody>
                  <StatRow
                    icon={Monitor}
                    label="Screen time"
                    value={entry.screenTimeHours}
                    unit="h"
                    source="—"
                  />
                  <StatRow
                    icon={Monitor}
                    label="Social media"
                    value={entry.socialMediaMinutes}
                    unit="min"
                    source="—"
                  />
                  <StatRow
                    icon={TreePine}
                    label="Outdoors"
                    value={entry.outdoorMinutes}
                    unit="min"
                    source="—"
                  />
                </PillarBody>
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
                <PillarBody>
                  <StatRow icon={Smile} label="Mood" value={`${entry.moodScore}/5`} source="—" />
                  <StatRow icon={Smile} label="Stress level" value={`${entry.stressLevel}/5`} source="—" />
                  <StatRow
                    icon={Brain}
                    label="Meditation"
                    value={entry.meditationMinutes}
                    unit="min"
                    source="—"
                  />
                </PillarBody>
              </div>
            )}
          </Card>
        </div>
        </section>
      </div>
    </div>
  );
}
