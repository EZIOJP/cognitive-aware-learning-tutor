import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { config } from "../config";
import { fetchLifeDaily, putLifeDaily } from "../api/hubClient";

export type PomodoroMode = "focus" | "break";

type PomodoroContextValue = {
  mode: PomodoroMode;
  isRunning: boolean;
  timeLeft: number;
  sessionCount: number;
  start: () => void;
  pause: () => void;
  toggle: () => void;
  reset: () => void;
  formatTime: (seconds: number) => string;
  progress: number;
};

const PomodoroContext = createContext<PomodoroContextValue | null>(null);

const WORK_SEC = config.pomodoro.workDuration * 60;
const SHORT_BREAK_SEC = config.pomodoro.shortBreak * 60;
const LONG_BREAK_SEC = config.pomodoro.longBreak * 60;

function formatTime(seconds: number) {
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
}

export function PomodoroProvider({ children }: { children: ReactNode }) {
  const [mode, setMode] = useState<PomodoroMode>("focus");
  const [timeLeft, setTimeLeft] = useState(WORK_SEC);
  const [isRunning, setIsRunning] = useState(false);
  const [sessionCount, setSessionCount] = useState(0);

  const durationForMode = useCallback(
    (m: PomodoroMode, completedSessions: number) => {
      if (m === "focus") return WORK_SEC;
      const isLong =
        completedSessions > 0 &&
        completedSessions % config.pomodoro.sessionsBeforeLongBreak === 0;
      return isLong ? LONG_BREAK_SEC : SHORT_BREAK_SEC;
    },
    [],
  );

  const logFocusMinutes = useCallback(async (minutes: number) => {
    if (minutes <= 0) return;
    const life = await fetchLifeDaily("today");
    const current = life?.study_minutes ?? 0;
    await putLifeDaily("today", { study_minutes: current + minutes });
  }, []);

  useEffect(() => {
    if (!isRunning) return;
    const id = setInterval(() => {
      setTimeLeft((prev) => {
        if (prev > 1) return prev - 1;
        if (mode === "focus") {
          const nextCount = sessionCount + 1;
          void logFocusMinutes(config.pomodoro.workDuration);
          setSessionCount(nextCount);
          setMode("break");
          setIsRunning(false);
          return durationForMode("break", nextCount);
        }
        setMode("focus");
        setIsRunning(false);
        return WORK_SEC;
      });
    }, 1000);
    return () => clearInterval(id);
  }, [isRunning, mode, sessionCount, durationForMode, logFocusMinutes]);

  const reset = useCallback(() => {
    setIsRunning(false);
    setMode("focus");
    setTimeLeft(WORK_SEC);
  }, []);

  const total = mode === "focus" ? WORK_SEC : durationForMode("break", sessionCount);
  const progress = ((total - timeLeft) / total) * 100;

  const value = useMemo(
    () => ({
      mode,
      isRunning,
      timeLeft,
      sessionCount,
      start: () => setIsRunning(true),
      pause: () => setIsRunning(false),
      toggle: () => setIsRunning((r) => !r),
      reset,
      formatTime,
      progress,
    }),
    [mode, isRunning, timeLeft, sessionCount, reset, progress],
  );

  return <PomodoroContext.Provider value={value}>{children}</PomodoroContext.Provider>;
}

export function usePomodoro() {
  const ctx = useContext(PomodoroContext);
  if (!ctx) throw new Error("usePomodoro must be used within PomodoroProvider");
  return ctx;
}
