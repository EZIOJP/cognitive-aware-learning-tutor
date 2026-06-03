import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  type ReactNode,
} from "react";
import { putLifeDaily } from "../api/hubClient";

// ─────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────

export interface DailyEntry {
  date: string; // YYYY-MM-DD
  // Health
  sleepHours: number;
  sleepQuality: number; // 1-5
  exerciseMinutes: number;
  waterGlasses: number;
  mealsHealthy: number; // out of 3
  // Productivity
  studyMinutes: number;
  tasksCompleted: number;
  deepWorkBlocks: number;
  // Digital Wellbeing
  screenTimeHours: number;
  socialMediaMinutes: number;
  outdoorMinutes: number;
  // Mental
  moodScore: number; // 1-5
  stressLevel: number; // 1-5
  meditationMinutes: number;
}

interface GoalTrackerContextValue {
  today: DailyEntry;
  history: DailyEntry[];
  updateToday: (patch: Partial<DailyEntry>) => void;
  lifeScore: number; // 0-100
  breakdown: Record<string, number>; // each pillar score 0-100
}

// ─────────────────────────────────────────────────────────
// Default empty entry
// ─────────────────────────────────────────────────────────

function todayKey(): string {
  return new Date().toISOString().slice(0, 10);
}

function emptyEntry(): DailyEntry {
  return {
    date: todayKey(),
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

// ─────────────────────────────────────────────────────────
// Scoring algorithm — each pillar 0-100
// ─────────────────────────────────────────────────────────

export function computeScores(entry: DailyEntry): {
  lifeScore: number;
  breakdown: Record<string, number>;
} {
  // Health pillar (sleep, exercise, water, food)
  const sleepScore = Math.min(100, (entry.sleepHours / 8) * 100);
  const sleepQualityScore = (entry.sleepQuality / 5) * 100;
  const exerciseScore = Math.min(100, (entry.exerciseMinutes / 45) * 100);
  const waterScore = Math.min(100, (entry.waterGlasses / 8) * 100);
  const mealsScore = Math.min(100, (entry.mealsHealthy / 3) * 100);
  const health = Math.round(
    sleepScore * 0.3 + sleepQualityScore * 0.2 + exerciseScore * 0.25 + waterScore * 0.15 + mealsScore * 0.1
  );

  // Productivity pillar (study, tasks, deep work)
  const studyScore = Math.min(100, (entry.studyMinutes / 180) * 100);
  const tasksScore = Math.min(100, (entry.tasksCompleted / 5) * 100);
  const deepWorkScore = Math.min(100, (entry.deepWorkBlocks / 4) * 100);
  const productivity = Math.round(studyScore * 0.5 + tasksScore * 0.3 + deepWorkScore * 0.2);

  // Digital Wellbeing pillar (less screen/social = better, more outdoor = better)
  const screenPenalty = Math.max(0, 100 - (entry.screenTimeHours / 8) * 100);
  const socialPenalty = Math.max(0, 100 - (entry.socialMediaMinutes / 120) * 100);
  const outdoorScore = Math.min(100, (entry.outdoorMinutes / 60) * 100);
  const digitalWellbeing = Math.round(screenPenalty * 0.35 + socialPenalty * 0.35 + outdoorScore * 0.3);

  // Mental pillar (mood, stress, meditation)
  const moodScore = (entry.moodScore / 5) * 100;
  const stressScore = ((5 - entry.stressLevel + 1) / 5) * 100; // inverted: low stress = high score
  const meditationScore = Math.min(100, (entry.meditationMinutes / 15) * 100);
  const mental = Math.round(moodScore * 0.4 + stressScore * 0.4 + meditationScore * 0.2);

  const lifeScore = Math.round(health * 0.3 + productivity * 0.25 + digitalWellbeing * 0.2 + mental * 0.25);

  return {
    lifeScore,
    breakdown: { Health: health, Productivity: productivity, "Digital Wellbeing": digitalWellbeing, Mental: mental },
  };
}

// ─────────────────────────────────────────────────────────
// Context
// ─────────────────────────────────────────────────────────

const GoalTrackerContext = createContext<GoalTrackerContextValue | null>(null);

export function useGoalTracker() {
  const ctx = useContext(GoalTrackerContext);
  if (!ctx) throw new Error("useGoalTracker must be used within GoalTrackerProvider");
  return ctx;
}

export function GoalTrackerProvider({ children }: { children: ReactNode }) {
  const [today, setToday] = useState<DailyEntry>(emptyEntry);
  const [history, setHistory] = useState<DailyEntry[]>([]);

  // Load from localStorage on mount
  useEffect(() => {
    try {
      const key = todayKey();
      const raw = localStorage.getItem(`life:${key}`);
      if (raw) setToday({ ...emptyEntry(), ...JSON.parse(raw) });

      const hist = JSON.parse(localStorage.getItem("life:history") || "[]");
      setHistory(hist);
    } catch {
      /* ignore */
    }
  }, []);

  const updateToday = useCallback((patch: Partial<DailyEntry>) => {
    setToday((prev) => {
      const updated = { ...prev, ...patch };
      localStorage.setItem(`life:${updated.date}`, JSON.stringify(updated));
      // also update history
      setHistory((h) => {
        const filtered = h.filter((e) => e.date !== updated.date);
        const newHist = [...filtered, updated].slice(-30);
        localStorage.setItem("life:history", JSON.stringify(newHist));
        return newHist;
      });
      const apiBody = {
        sleep_hours: updated.sleepHours,
        sleep_quality: updated.sleepQuality,
        exercise_minutes: updated.exerciseMinutes,
        water_glasses: updated.waterGlasses,
        meals_healthy: updated.mealsHealthy,
        study_minutes: updated.studyMinutes,
        tasks_completed: updated.tasksCompleted,
        deep_work_blocks: updated.deepWorkBlocks,
        screen_time_hours: updated.screenTimeHours,
        social_media_minutes: updated.socialMediaMinutes,
        outdoor_minutes: updated.outdoorMinutes,
        mood_score: updated.moodScore,
        stress_level: updated.stressLevel,
        meditation_minutes: updated.meditationMinutes,
      };
      void putLifeDaily(updated.date === todayKey() ? "today" : updated.date, apiBody);
      return updated;
    });
  }, []);

  const { lifeScore, breakdown } = computeScores(today);

  return (
    <GoalTrackerContext.Provider value={{ today, history, updateToday, lifeScore, breakdown }}>
      {children}
    </GoalTrackerContext.Provider>
  );
}
