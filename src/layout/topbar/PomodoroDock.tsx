import { Timer, Play, Pause, RotateCcw } from "lucide-react";
import { usePomodoro } from "../../context/PomodoroContext";
import { Button } from "../../app/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "../../app/components/ui/popover";

export function PomodoroDock({
  align = "end",
  side = "bottom",
  compact = false,
}: {
  align?: "start" | "center" | "end";
  side?: "top" | "right" | "bottom" | "left";
  /** Icon-only trigger for narrow rails (collapsed Focus sidebar). */
  compact?: boolean;
} = {}) {
  // Do not import StudySession here — Focus lean bundle must not pull math/EEG.
  // Study App wires pomodoro → session complete in StudySessionProvider.
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

  const onToggle = () => {
    if (!isRunning && timeLeft <= 1) {
      reset();
      return;
    }
    toggle();
  };

  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          type="button"
          className={
            compact
              ? "gloss-dock-btn flex h-9 w-9 items-center justify-center rounded-xl p-0"
              : "gloss-dock-btn flex items-center gap-2 rounded-full px-3 py-1.5 text-sm font-medium"
          }
          aria-label={`Pomodoro timer ${formatTime(timeLeft)}`}
          title={formatTime(timeLeft)}
        >
          <Timer className={`w-4 h-4 shrink-0 ${mode === "focus" ? "text-orange-500" : "text-sky-500"}`} />
          {!compact ? (
            <span className="font-mono tabular-nums">{formatTime(timeLeft)}</span>
          ) : null}
        </button>
      </PopoverTrigger>
      <PopoverContent className="gloss-popover w-72 p-4" align={align} side={side} sideOffset={8}>
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
          </div>
          <p className="text-xs text-muted-foreground">Focus sessions completed: {sessionCount}</p>
        </div>
      </PopoverContent>
    </Popover>
  );
}
