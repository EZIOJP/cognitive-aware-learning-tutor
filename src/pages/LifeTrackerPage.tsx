import { useCallback, useEffect, useMemo, useState } from "react";
import {
  computeScores,
  type DailyEntry,
} from "../context/GoalTrackerContext";
import { LifeClockWidget } from "../components/hub/LifeClockWidget";
import { FaceTrackerPanel } from "../components/face/FaceTrackerPanel";
import { usePluginsOptional } from "../plugins/registry";
import { fetchLifeDaily, fetchLifeHistory14, type LifeDailyApi } from "../api/hubClient";
import {
  fetchWearableDay,
  fetchWearableStatus,
  type WearableDay,
} from "../api/wearablesClient";
import { WatchDayDumpCard } from "../components/life/WatchDayDumpCard";
import { TrackerDayBoard } from "../components/life/TrackerDayBoard";
import { HealthServerToggle } from "../components/life/HealthServerToggle";
import { isFocusDesktopShell } from "../utils/focusDesktopShell";
import {
  ChevronLeft,
  ChevronRight,
  RefreshCw,
  TrendingUp,
  Watch,
} from "lucide-react";
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

/** Relative + clock for last Amazfit CALT Sync near the Life Score ring. */
function formatWatchSyncLabel(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const t = new Date(iso).getTime();
  if (!Number.isFinite(t)) return null;
  const mins = Math.max(0, Math.round((Date.now() - t) / 60_000));
  const clock = new Date(t).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
  if (mins < 1) return `just now · ${clock}`;
  if (mins < 60) return `${mins}m ago · ${clock}`;
  const hours = Math.floor(mins / 60);
  if (hours < 36) return `${hours}h ago · ${clock}`;
  return clock;
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

const PILLAR_COLORS: Record<string, string> = {
  Health: "#10b981",
  Productivity: "#6366f1",
  "Digital Wellbeing": "#f59e0b",
  Mental: "#ec4899",
};

export function LifeTrackerPage() {
  const { burst } = useEaster();
  const scoreEgg = useLongPress(700, () => burst("fireworks"));
  const [refreshing, setRefreshing] = useState(false);
  const [selectedDay, setSelectedDay] = useState(() => localDateKey());
  const [entry, setEntry] = useState<DailyEntry>(() => emptyEntry(localDateKey()));
  const [history, setHistory] = useState<DailyEntry[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [wearableDay, setWearableDay] = useState<WearableDay | null>(null);
  const [lastWatchSyncAt, setLastWatchSyncAt] = useState<string | null>(null);

  const todayKey = localDateKey();
  const isToday = selectedDay === todayKey;
  const canGoNext = selectedDay < todayKey;

  const { lifeScore, breakdown } = useMemo(() => computeScores(entry), [entry]);

  const loadDay = useCallback(async (day: string, opts?: { silent?: boolean; skipWearable?: boolean }) => {
    if (!opts?.silent) setLoadError(null);
    const apiDay = day === todayKey ? "today" : day;
    const remote = await fetchLifeDaily(apiDay);
    if (!opts?.skipWearable) {
      const [watch, status] = await Promise.all([
        fetchWearableDay(day).catch(() => null),
        fetchWearableStatus().catch(() => null),
      ]);
      const hasWatch =
        !!watch &&
        (watch.local_date ||
          watch.synced_at ||
          watch.steps != null ||
          watch.sleep_hours != null ||
          watch.hr_last != null ||
          watch.hr_avg != null);
      setWearableDay(hasWatch ? watch : null);
      const stamp =
        (hasWatch && (watch?.synced_at || watch?.last_captured_at || watch?.captured_at)) ||
        status?.last_sync?.last_ingest_at ||
        status?.last_sync?.updated_at ||
        status?.last_ping?.at ||
        null;
      setLastWatchSyncAt(typeof stamp === "string" && stamp ? stamp : null);
    }
    if (!remote || remote.empty) {
      setEntry(apiToEntry(remote, day));
      if (!opts?.silent && !remote) {
        setLoadError(
          isFocusDesktopShell()
            ? "No life mirror yet — Sync from Amazfit CALT Sync."
            : "Could not load that day from the API",
        );
      }
      return;
    }
    setEntry(apiToEntry(remote, day));
  }, [todayKey]);

  const loadHistory = useCallback(async () => {
    const rows = await fetchLifeHistory14();
    setHistory(rows.map((r) => apiToEntry(r, String(r.date || todayKey).slice(0, 10))));
  }, [todayKey]);

  useEffect(() => {
    void loadDay(selectedDay);
  }, [selectedDay, loadDay]);

  useEffect(() => {
    const onHub = () => {
      void loadDay(selectedDay, { silent: true });
      void loadHistory();
    };
    window.addEventListener("hub:refresh", onHub);
    return () => window.removeEventListener("hub:refresh", onHub);
  }, [selectedDay, loadDay, loadHistory]);

  useEffect(() => {
    if (!isToday) return;
    const id = window.setInterval(
      () => void loadDay(selectedDay, { silent: true, skipWearable: true }),
      60_000,
    );
    return () => window.clearInterval(id);
  }, [isToday, selectedDay, loadDay]);

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
  const focusShell = isFocusDesktopShell();
  const lastSyncLabel = formatWatchSyncLabel(lastWatchSyncAt);
  const plugins = usePluginsOptional();
  const enabledIds = plugins?.enabledIds ?? [];

  return (
    <div
      className={
        focusShell
          ? "life-tracker-page focus-shell-page-root h-full min-h-0 overflow-visible bg-background text-foreground"
          : "life-tracker-page h-full min-h-0 overflow-y-auto bg-background text-foreground"
      }
    >
      <div className="life-tracker-shell mx-auto w-full max-w-6xl space-y-5 pb-10">
        <header className="life-tracker-hero">
          <div className="life-tracker-hero__copy">
            <span className="life-tracker-hero__eyebrow">Life</span>
            <h1>Life Tracker</h1>
            <p>
              {focusShell
                ? "ZeppBridge day metrics (null ≠ 0) plus today’s focus balance."
                : "Sleep, movement, focus, and digital balance — one day at a time."}
            </p>
          </div>
          <div className="life-tracker-hero__controls flex flex-wrap items-center gap-2">
            <HealthServerToggle />
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

        {loadError && <p className="text-sm text-rose-300">{loadError}</p>}

        {isToday ? <TrackerDayBoard /> : null}

        <div className="life-tracker-overview grid gap-5 xl:grid-cols-[minmax(0,1.15fr)_minmax(20rem,0.85fr)]">
          <div className="space-y-5 min-w-0">
            <section className="life-tracker-watch gloss-panel rounded-2xl p-5">
              <div className="life-tracker-section-heading">
                <div>
                  <span>Watch</span>
                  <h2>{formatDayLabel(selectedDay)}</h2>
                </div>
                {lastSyncLabel ? (
                  <span className="life-tracker-section-heading__day inline-flex items-center gap-1">
                    <Watch className="w-3 h-3" />
                    {lastSyncLabel}
                  </span>
                ) : (
                  <span className="life-tracker-section-heading__day">Sync pending</span>
                )}
              </div>
              <WatchDayDumpCard
                day={wearableDay}
                localDate={selectedDay}
                onSleepCorrected={() => {
                  void loadDay(selectedDay);
                  void loadHistory();
                }}
              />
            </section>

            <section className="gloss-panel rounded-2xl p-5">
              <div className="life-tracker-section-heading life-tracker-section-heading--compact">
                <div>
                  <span>Day clock</span>
                  <h2>Time balance</h2>
                </div>
              </div>
              <LifeClockWidget embedded showLegend={false} day={selectedDay} />
            </section>

            {!focusShell && enabledIds.includes("focus-mirror") && <FaceTrackerPanel />}
          </div>

          <aside className="life-tracker-summary space-y-5 min-w-0">
            <div className="life-tracker-score gloss-panel rounded-2xl p-6">
              <span className="life-tracker-score__eyebrow">Balance</span>
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
                <div className="min-w-0">
                  <h2 className="text-2xl font-semibold">Life Score</h2>
                  <p className="text-muted-foreground text-sm">{scoreLabel}</p>
                </div>
              </div>

              <div className="life-tracker-score__pillars flex gap-4 justify-around flex-wrap">
                {Object.entries(breakdown).map(([pillar, score]) => (
                  <ScoreRing
                    key={pillar}
                    score={score}
                    label={pillar === "Digital Wellbeing" ? "Digital" : pillar}
                    color={PILLAR_COLORS[pillar] || "#6366f1"}
                  />
                ))}
              </div>
            </div>

            {chartDays.length >= 2 && (
              <div className="life-tracker-trend gloss-panel rounded-2xl p-4">
                <div className="flex items-center gap-2 mb-3">
                  <TrendingUp className="w-4 h-4 text-primary" />
                  <span className="text-sm font-medium">14-day trend</span>
                  <span className="text-[10px] text-muted-foreground ml-auto">tap a day</span>
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
      </div>
    </div>
  );
}
