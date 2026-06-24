import { useFaceTrackerOptional } from "../../face-tracker/FaceTrackerContext";
import { usePomodoro } from "../../context/PomodoroContext";

export function FocusOverlay() {
  const face = useFaceTrackerOptional();
  const { mode, isRunning } = usePomodoro();

  const notFocused = face?.focus.not_focused ?? false;
  const shouldFlash = notFocused && mode === "focus" && isRunning && (face?.tracking ?? false);

  return (
    <div
      className={`focus-overlay ${shouldFlash ? "flash-red" : ""}`}
      aria-hidden={!shouldFlash}
      data-testid="focus-overlay"
    />
  );
}
