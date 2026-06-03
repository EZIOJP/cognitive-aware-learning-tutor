import { useEffect, useState } from "react";
import { Link } from "react-router";
import { ScanFace, Terminal } from "lucide-react";
import { Card } from "../../app/components/ui/card";
import { fetchFaceStatus, type FaceStatus } from "../../api/faceClient";

/** Status card for Python mirror — no browser webcam. */
export function FaceTrackerPanel() {
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

  return (
    <Card className="p-4 gloss-panel space-y-3">
      <div className="flex items-center gap-2">
        <ScanFace className="w-5 h-5 text-primary" />
        <h3 className="font-semibold">Focus mirror (Python)</h3>
        <span
          className={`ml-auto text-xs px-2 py-0.5 rounded-full ${
            status?.face_detected ? "bg-emerald-500/20 text-emerald-400" : "bg-muted text-muted-foreground"
          }`}
        >
          {status?.face_detected ? status.attitude : "not running"}
        </span>
      </div>
      <p className="text-sm text-muted-foreground">
        Open the mirrored camera window on your desktop. Run the tracker script — the whole frame (including
        overlay text) is flipped horizontally like a mirror.
      </p>
      {status?.face_detected && (
        <p className="text-sm">
          Attention <span className="font-mono text-primary">{status.attention}%</span>
          {" · "}
          Blinks <span className="font-mono">{status.blink_rate}/min</span>
        </p>
      )}
      <Link to="/focus/calibrate" className="text-xs text-primary hover:underline block">
        Run screen calibration (follow the dot) →
      </Link>
      <div className="flex items-start gap-2 text-xs text-muted-foreground bg-muted/30 rounded-lg p-3">
        <Terminal className="w-4 h-4 shrink-0 mt-0.5" />
        <code className="break-all">scripts\run_face_tracker.bat</code>
      </div>
    </Card>
  );
}
