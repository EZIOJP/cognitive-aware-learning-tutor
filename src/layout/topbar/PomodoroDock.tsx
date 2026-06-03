import { useState, useEffect } from "react";
import { Timer, Play, Pause, RotateCcw } from "lucide-react";
import { useStudySession } from "../../context/StudySessionContext";
import { config } from "../../config";
import { Button } from "../../app/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "../../app/components/ui/popover";

const WORK_DURATION = config.pomodoro.workDuration * 60;

function formatTime(seconds: number) {
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
}

export function PomodoroDock() {
  const { handleSessionComplete } = useStudySession();
  const [open, setOpen] = useState(false);
  const [timeLeft, setTimeLeft] = useState(WORK_DURATION);
  const [isRunning, setIsRunning] = useState(false);
  const [sessionCount, setSessionCount] = useState(0);

  useEffect(() => {
    if (!isRunning) return;
    const id = setInterval(() => {
      setTimeLeft((prev) => {
        if (prev <= 1) {
          setIsRunning(false);
          setSessionCount((c) => c + 1);
          handleSessionComplete();
          return WORK_DURATION;
        }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(id);
  }, [isRunning, handleSessionComplete]);

  const progress = ((WORK_DURATION - timeLeft) / WORK_DURATION) * 100;

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          className="gloss-dock-btn flex items-center gap-2 rounded-full px-3 py-1.5 text-sm font-medium"
          aria-label="Pomodoro timer"
        >
          <Timer className="w-4 h-4 text-orange-500" />
          <span className="font-mono tabular-nums">{formatTime(timeLeft)}</span>
        </button>
      </PopoverTrigger>
      <PopoverContent
        className="gloss-popover w-72 p-4"
        align="end"
        sideOffset={8}
      >
        <div className="flex flex-col items-center gap-3">
          <p className="text-xs text-muted-foreground w-full">Focus session</p>
          <div className="text-4xl font-bold font-mono tabular-nums">
            {formatTime(timeLeft)}
          </div>
          <div className="w-full h-2 rounded-full bg-muted overflow-hidden">
            <div
              className="h-full bg-orange-500 transition-all duration-300"
              style={{ width: `${progress}%` }}
            />
          </div>
          <div className="flex gap-2">
            <Button
              size="sm"
              variant={isRunning ? "secondary" : "default"}
              onClick={() => setIsRunning(!isRunning)}
            >
              {isRunning ? (
                <Pause className="w-4 h-4" />
              ) : (
                <Play className="w-4 h-4" />
              )}
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => {
                setIsRunning(false);
                setTimeLeft(WORK_DURATION);
              }}
            >
              <RotateCcw className="w-4 h-4" />
            </Button>
          </div>
          <p className="text-xs text-muted-foreground">
            Sessions: {sessionCount}
          </p>
        </div>
      </PopoverContent>
    </Popover>
  );
}
