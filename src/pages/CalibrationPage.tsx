import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router";
import { ScanFace, ArrowLeft } from "lucide-react";
import { Card } from "../app/components/ui/card";

const LS_CALIB = "focus_mirror:calibration_v1";

type Point = { x: number; y: number; label: string };

const TARGETS: Point[] = [
  { x: 0.1, y: 0.1, label: "top-left" },
  { x: 0.5, y: 0.1, label: "top-center" },
  { x: 0.9, y: 0.1, label: "top-right" },
  { x: 0.1, y: 0.5, label: "mid-left" },
  { x: 0.5, y: 0.5, label: "center" },
  { x: 0.9, y: 0.5, label: "mid-right" },
  { x: 0.1, y: 0.9, label: "bottom-left" },
  { x: 0.5, y: 0.9, label: "bottom-center" },
  { x: 0.9, y: 0.9, label: "bottom-right" },
];

export function CalibrationPage() {
  const [step, setStep] = useState(0);
  const [samples, setSamples] = useState<Record<string, { t: number }>>({});
  const [done, setDone] = useState(false);
  const areaRef = useRef<HTMLDivElement>(null);

  const target = TARGETS[step];

  const record = useCallback(() => {
    if (!target) return;
    setSamples((prev) => ({
      ...prev,
      [target.label]: { t: Date.now() },
    }));
    if (step + 1 >= TARGETS.length) {
      const payload = { points: TARGETS.map((p) => p.label), completed_at: new Date().toISOString() };
      localStorage.setItem(LS_CALIB, JSON.stringify(payload));
      setDone(true);
    } else {
      setStep((s) => s + 1);
    }
  }, [step, target]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === " " || e.key === "Enter") {
        e.preventDefault();
        record();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [record]);

  return (
    <div className="h-full overflow-y-auto max-w-3xl mx-auto p-4 space-y-6">
      <Link to="/life-tracker" className="inline-flex items-center gap-2 text-sm text-primary hover:underline">
        <ArrowLeft className="w-4 h-4" /> Back
      </Link>
      <header>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <ScanFace className="w-7 h-7 text-emerald-400" />
          Focus mirror calibration
        </h1>
        <p className="text-muted-foreground mt-2 text-sm">
          Follow the dot across your screen(s). Press Space when your eyes are on the dot. Saved locally for this
          browser; Python tracker can read the same file path later.
        </p>
      </header>

      <Card
        ref={areaRef}
        className="relative gloss-panel aspect-video max-h-[60vh] w-full overflow-hidden cursor-crosshair"
        onClick={record}
      >
        {!done && target && (
          <div
            className="absolute w-8 h-8 rounded-full bg-primary shadow-[0_0_20px_rgba(var(--primary),0.8)] -translate-x-1/2 -translate-y-1/2 transition-all duration-300"
            style={{ left: `${target.x * 100}%`, top: `${target.y * 100}%` }}
            aria-hidden
          />
        )}
        {done ? (
          <div className="absolute inset-0 flex items-center justify-center text-emerald-400 font-medium">
            Calibration saved ({Object.keys(samples).length} points)
          </div>
        ) : (
          <div className="absolute bottom-4 left-4 text-xs text-muted-foreground">
            Step {step + 1} / {TARGETS.length} — {target?.label}
          </div>
        )}
      </Card>

      <p className="text-xs text-muted-foreground">
        Then run <code>scripts\run_face_tracker.bat</code> for the mirrored Python window.
      </p>
    </div>
  );
}
