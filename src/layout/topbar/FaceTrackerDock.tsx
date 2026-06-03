import { useEffect, useState } from "react";
import { ScanFace } from "lucide-react";
import { fetchFaceStatus, type FaceStatus } from "../../api/faceClient";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "../../app/components/ui/popover";

/** Live face/attention from Python `backend/face_tracker.py` (mirrored OpenCV window). */
export function FaceTrackerDock() {
  const [status, setStatus] = useState<FaceStatus | null>(null);

  useEffect(() => {
    let cancelled = false;
    const poll = async () => {
      const s = await fetchFaceStatus();
      if (!cancelled) setStatus(s);
    };
    void poll();
    const id = setInterval(poll, 2000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  const live = status?.face_detected;
  const label = live ? status?.attitude ?? "tracking" : "offline";

  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          type="button"
          className="gloss-dock-btn flex items-center gap-2 rounded-full px-3 py-1.5 text-sm"
          aria-label={`Face tracker: ${label}`}
        >
          <ScanFace className="w-4 h-4 shrink-0" />
          <span
            className={`w-2 h-2 shrink-0 rounded-full ${
              live ? "bg-emerald-500 shadow-[0_0_6px_rgba(16,185,129,0.7)]" : "bg-muted"
            }`}
          />
          <span className="hidden sm:inline text-xs text-muted-foreground capitalize">{label}</span>
        </button>
      </PopoverTrigger>
      <PopoverContent className="gloss-popover w-72 p-4" align="end" sideOffset={8}>
        <div className="space-y-3 text-sm">
          <p className="font-medium">Python focus mirror</p>
          <p className="text-xs text-muted-foreground">
            The mirrored preview runs in a desktop window (OpenCV), not in the browser. Video and on-screen
            labels are horizontally flipped like a real mirror.
          </p>
          {status?.face_detected ? (
            <ul className="text-xs space-y-1">
              <li>Attention: {status.attention}%</li>
              <li>Attitude: {status.attitude}</li>
              <li>Blinks: {status.blink_rate}/min</li>
            </ul>
          ) : (
            <p className="text-xs text-amber-400/90">Tracker not reporting — start the script below.</p>
          )}
          <code className="block text-[10px] bg-muted/50 p-2 rounded-md break-all">
            scripts\run_face_tracker.bat
          </code>
          <p className="text-[10px] text-muted-foreground">
            Requires camera + backend on :8000. Optional: set FACE_TRACKER_TOKEN in .env (login JWT) for hub
            readings.
          </p>
        </div>
      </PopoverContent>
    </Popover>
  );
}
