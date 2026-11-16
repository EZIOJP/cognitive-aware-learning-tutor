/**
 * Lean attention reader UI for Focus (no Study calibrate route dependency).
 */
import { Loader2, Play, ScanFace, Square } from "lucide-react";
import { useFaceTracker } from "../../face-tracker/FaceTrackerContext";
import { loadBodyCarePrefs } from "../../lib/bodyCarePrefs";

export function FocusAttentionPanel() {
  const {
    tracking,
    toggleTracking,
    status,
    error,
    payload,
    postureScore,
    focus,
    profileName,
    VideoElement,
  } = useFaceTracker();
  const live = Boolean(payload?.face_detected);
  const prefs = loadBodyCarePrefs();

  return (
    <div className="space-y-2 rounded-lg border border-border/40 bg-black/20 p-3">
      <VideoElement />
      <div className="flex flex-wrap items-center gap-2">
        <ScanFace size={15} className="text-primary" />
        <span className="text-sm font-medium">Attention reader</span>
        <span
          className={`ml-auto text-[10px] uppercase tracking-wide px-2 py-0.5 rounded-full ${
            live
              ? "bg-emerald-500/20 text-emerald-300"
              : tracking
                ? "bg-amber-500/20 text-amber-200"
                : "bg-muted text-muted-foreground"
          }`}
        >
          {live ? payload?.attitude : tracking ? (status === "loading" ? "loading" : "away") : "off"}
        </span>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={toggleTracking}
          className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs ${
            tracking
              ? "border border-rose-500/40 bg-rose-500/15 text-rose-100"
              : "border border-primary/30 bg-primary/15 text-primary"
          }`}
        >
          {tracking ? <Square size={12} /> : <Play size={12} />}
          {tracking ? "Stop" : "Start"}
        </button>
        {tracking && status === "loading" ? (
          <Loader2 size={14} className="animate-spin text-muted-foreground" />
        ) : null}
        <span className="text-[11px] text-muted-foreground">
          Profile: <span className="font-mono">{profileName ?? "default"}</span>
        </span>
      </div>
      {error ? <p className="text-xs text-rose-300">{error}</p> : null}
      {payload?.face_detected ? (
        <div className="space-y-1">
          <p className="text-sm">
            Attention <span className="font-mono text-primary">{payload.attention}%</span>
            {" · "}
            Blinks <span className="font-mono">{payload.blink_rate}/min</span>
            {postureScore != null ? (
              <>
                {" · "}
                Posture <span className="font-mono text-amber-200/90">{postureScore}</span>
              </>
            ) : null}
          </p>
          {prefs.postureCoachEnabled && postureScore != null && postureScore < prefs.postureScoreThreshold ? (
            <p className="text-[11px] text-amber-200/90">
              Lean/slouch hold — straighten to avoid a nudge after {prefs.postureWarnMinutes}m.
            </p>
          ) : null}
        </div>
      ) : tracking ? (
        <p className="text-[11px] text-amber-200/90">
          {focus.no_face
            ? prefs.presencePauseSit
              ? "Away — sit clock paused."
              : "Waiting for face…"
            : "Waiting for face…"}
        </p>
      ) : (
        <p className="text-[11px] text-muted-foreground">
          Start to score attention + posture from webcam (local). Camera stays on this machine.
        </p>
      )}
    </div>
  );
}

export default FocusAttentionPanel;
