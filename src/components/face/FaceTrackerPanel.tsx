import { Link } from "react-router";
import { Loader2, Play, ScanFace, Square } from "lucide-react";
import { Card } from "../../app/components/ui/card";
import { Button } from "../../app/components/ui/button";
import { useFaceTracker } from "../../face-tracker/FaceTrackerContext";

/** Life Tracker panel — preview + controls over global FaceTrackerContext. */
export function FaceTrackerPanel() {
  const { tracking, toggleTracking, status, error, payload, profileName } = useFaceTracker();

  const shown = payload;
  const live = Boolean(shown?.face_detected);

  return (
    <Card className="p-4 gloss-panel space-y-3">
      <div className="flex items-center gap-2">
        <ScanFace className="w-5 h-5 text-primary" />
        <h3 className="font-semibold">Focus tracker</h3>
        <span
          className={`ml-auto text-xs px-2 py-0.5 rounded-full ${
            live ? "bg-emerald-500/20 text-emerald-400" : "bg-muted text-muted-foreground"
          }`}
        >
          {live
            ? shown?.attitude
            : tracking
              ? status === "loading"
                ? "loading…"
                : "no face"
              : "not running"}
        </span>
      </div>

      <div className="flex items-center gap-2">
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
        {tracking && status === "loading" && (
          <Loader2 className="w-4 h-4 animate-spin text-muted-foreground" />
        )}
        <span className="text-xs text-muted-foreground">
          Profile: <span className="font-mono">{profileName ?? "default (uncalibrated)"}</span>
        </span>
      </div>
      {error && <p className="text-xs text-destructive">{error}</p>}

      {shown?.face_detected && (
        <p className="text-sm">
          Attention <span className="font-mono text-primary">{shown.attention}%</span>
          {" · "}
          Blinks <span className="font-mono">{shown.blink_rate}/min</span>
        </p>
      )}

      <Link to="/focus/calibrate" className="text-xs text-primary hover:underline block">
        Calibrate for this setup (follow the dots) →
      </Link>
    </Card>
  );
}
