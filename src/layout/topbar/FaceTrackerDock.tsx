import { Link } from "react-router";
import { Loader2, Play, ScanFace, Square } from "lucide-react";
import { useFaceTrackerOptional } from "../../face-tracker/FaceTrackerContext";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "../../app/components/ui/popover";
import { Button } from "../../app/components/ui/button";

/** Top-bar face tracker — Start/Stop + live status from global context. */
export function FaceTrackerDock() {
  const ft = useFaceTrackerOptional();
  if (!ft) return null;

  const { tracking, toggleTracking, payload, focus, status, profileName, lastSnapshotMarker } = ft;
  const live = payload?.face_detected;
  const label = tracking
    ? live
      ? (payload?.attitude ?? "tracking")
      : status === "loading"
        ? "loading"
        : "no face"
    : "offline";

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
              tracking && live
                ? "bg-emerald-500 shadow-[0_0_6px_rgba(16,185,129,0.7)]"
                : tracking
                  ? "bg-amber-500"
                  : "bg-muted"
            }`}
          />
          <span className="hidden sm:inline text-xs text-muted-foreground capitalize">{label}</span>
        </button>
      </PopoverTrigger>
      <PopoverContent className="gloss-popover w-72 p-4" align="end" sideOffset={8}>
        <div className="space-y-3 text-sm">
          <p className="font-medium">Focus tracker</p>
          <Button size="sm" variant={tracking ? "destructive" : "default"} onClick={toggleTracking}>
            {tracking ? (
              <>
                <Square className="w-3.5 h-3.5 mr-1" /> Stop
              </>
            ) : (
              <>
                <Play className="w-3.5 h-3.5 mr-1" /> Start tracking
              </>
            )}
          </Button>
          {status === "loading" && (
            <p className="text-xs text-muted-foreground flex items-center gap-1">
              <Loader2 className="w-3 h-3 animate-spin" /> Loading models…
            </p>
          )}
          {payload?.face_detected ? (
            <ul className="text-xs space-y-1">
              <li>Attention: {payload.attention}%</li>
              <li>Attitude: {payload.attitude}</li>
              <li>Blinks: {payload.blink_rate}/min</li>
              {focus.not_focused && <li className="text-red-400">Unfocused (5s+)</li>}
            </ul>
          ) : tracking ? (
            <p className="text-xs text-amber-400/90">Waiting for face…</p>
          ) : (
            <p className="text-xs text-muted-foreground">Start tracking to monitor attention globally.</p>
          )}
          {lastSnapshotMarker && (
            <p className="text-[10px] text-emerald-500">Wave saved {lastSnapshotMarker}</p>
          )}
          <p className="text-[10px] text-muted-foreground">
            Profile: {profileName ?? "default"} ·{" "}
            <Link to="/focus/calibrate" className="text-primary hover:underline">
              Calibrate
            </Link>
          </p>
        </div>
      </PopoverContent>
    </Popover>
  );
}
