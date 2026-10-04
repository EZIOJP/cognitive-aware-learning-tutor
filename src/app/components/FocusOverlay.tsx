import { useFaceTrackerOptional } from "../../face-tracker/FaceTrackerContext";
import { usePomodoroOptional } from "../../context/PomodoroContext";

export function FocusOverlay() {
  const face = useFaceTrackerOptional();
  const pomo = usePomodoroOptional();

  const notFocused = face?.focus.not_focused ?? false;
  const shouldFlash =
    notFocused &&
    pomo?.mode === "focus" &&
    (pomo?.isRunning ?? false) &&
    (face?.tracking ?? false);

  return (
    <div
      className={`focus-overlay ${shouldFlash ? "flash-red" : ""}`}
      aria-hidden={!shouldFlash}
      data-testid="focus-overlay"
    />
  );
}
