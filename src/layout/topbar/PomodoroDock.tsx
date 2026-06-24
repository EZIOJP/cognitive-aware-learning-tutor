import { useEffect, useRef } from "react";
import { Timer, Play, Pause, RotateCcw } from "lucide-react";
import { useStudySession } from "../../context/StudySessionContext";
import { usePomodoro } from "../../context/PomodoroContext";
import { Button } from "../../app/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "../../app/components/ui/popover";

export function PomodoroDock() {
  const { handleSessionComplete } = useStudySession();
  const {
    mode,
    isRunning,
    timeLeft,
    sessionCount,
    toggle,
    reset,
    formatTime,
    progress,
  } = usePomodoro();

  const prevCountRef = useRef(sessionCount);
  useEffect(() => {
    if (sessionCount > prevCountRef.current) {
      handleSessionComplete();
      prevCountRef.current = sessionCount;
    }
  }, [sessionCount, handleSessionComplete]);

  const onToggle = () => {
    if (!isRunning && timeLeft <= 1) {
      reset();
      return;
    }
    toggle();
  };

  const onCompleteFocus = () => {
    handleSessionComplete();
  };

  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          type="button"
          className="gloss-dock-btn flex items-center gap-2 rounded-full px-3 py-1.5 text-sm font-medium"
          aria-label="Pomodoro timer"
        >
          <Timer className={`w-4 h-4 ${mode === "focus" ? "text-orange-500" : "text-sky-500"}`} />
          <span className="font-mono tabular-nums">{formatTime(timeLeft)}</span>
        </button>
      </PopoverTrigger>
      <PopoverContent className="gloss-popover w-72 p-4" align="end" sideOffset={8}>
        <div className="flex flex-col items-center gap-3">
          <p className="text-xs text-muted-foreground w-full capitalize">
            {mode === "focus" ? "Focus session" : "Break"}
          </p>
          <div className="text-4xl font-bold font-mono tabular-nums">{formatTime(timeLeft)}</div>
          <div className="w-full h-2 rounded-full bg-muted overflow-hidden">
            <div
              className={`h-full transition-all duration-300 ${
                mode === "focus" ? "bg-orange-500" : "bg-sky-500"
              }`}
              style={{ width: `${progress}%` }}
            />
          </div>
          <div className="flex gap-2">
            <Button size="sm" variant={isRunning ? "secondary" : "default"} onClick={onToggle}>
              {isRunning ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
            </Button>
            <Button size="sm" variant="outline" onClick={reset}>
              <RotateCcw className="w-4 h-4" />
            </Button>
            {mode === "focus" && (
              <Button size="sm" variant="ghost" className="text-xs" onClick={onCompleteFocus}>
                Done
              </Button>
            )}
          </div>
          <p className="text-xs text-muted-foreground">Focus sessions completed: {sessionCount}</p>
        </div>
      </PopoverContent>
    </Popover>
  );
}
