import { useState, useEffect } from "react";
import { Timer, Play, Pause, RotateCcw } from "lucide-react";
import { Button } from "./ui/button";
import { Card } from "./ui/card";
import { Progress } from "./ui/progress";

interface PomodoroTimerProps {
  onSessionComplete: () => void;
}

export function PomodoroTimer({ onSessionComplete }: PomodoroTimerProps) {
  const WORK_DURATION = 25 * 60; // 25 minutes in seconds
  const [timeLeft, setTimeLeft] = useState(WORK_DURATION);
  const [isRunning, setIsRunning] = useState(false);
  const [sessionCount, setSessionCount] = useState(0);

  useEffect(() => {
    let interval: NodeJS.Timeout | null = null;

    if (isRunning && timeLeft > 0) {
      interval = setInterval(() => {
        setTimeLeft((prev) => {
          if (prev <= 1) {
            setIsRunning(false);
            setSessionCount((count) => count + 1);
            onSessionComplete();
            return WORK_DURATION;
          }
          return prev - 1;
        });
      }, 1000);
    }

    return () => {
      if (interval) clearInterval(interval);
    };
  }, [isRunning, timeLeft, onSessionComplete]);

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
  };

  const progress = ((WORK_DURATION - timeLeft) / WORK_DURATION) * 100;

  const handleReset = () => {
    setIsRunning(false);
    setTimeLeft(WORK_DURATION);
  };

  return (
    <Card className="p-4">
      <div className="flex items-center gap-2 mb-4">
        <Timer className="w-5 h-5" />
        <h3>Focus Session</h3>
      </div>

      <div className="flex flex-col items-center gap-4">
        <div className="text-6xl font-bold tracking-tight">{formatTime(timeLeft)}</div>

        <Progress value={progress} className="w-full" />

        <div className="flex gap-2">
          <Button
            onClick={() => setIsRunning(!isRunning)}
            variant={isRunning ? "secondary" : "default"}
            size="sm"
          >
            {isRunning ? (
              <>
                <Pause className="w-4 h-4 mr-2" />
                Pause
              </>
            ) : (
              <>
                <Play className="w-4 h-4 mr-2" />
                Start
              </>
            )}
          </Button>
          <Button onClick={handleReset} variant="outline" size="sm">
            <RotateCcw className="w-4 h-4 mr-2" />
            Reset
          </Button>
        </div>

        <div className="text-sm text-muted-foreground">
          Sessions completed: {sessionCount}
        </div>
      </div>
    </Card>
  );
}
