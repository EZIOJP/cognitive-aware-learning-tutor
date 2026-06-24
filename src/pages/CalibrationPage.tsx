import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router";
import { ScanFace, ArrowLeft, Trash2, CheckCircle2 } from "lucide-react";
import { Card } from "../app/components/ui/card";
import { Button } from "../app/components/ui/button";
import { Input } from "../app/components/ui/input";
import { useHumanTracker, type FrameReading } from "../face-tracker/useHumanTracker";
import {
  buildProfile,
  deleteProfile,
  getActiveProfileName,
  listProfiles,
  saveProfile,
  setActiveProfileName,
  type CalibrationProfile,
  type DotSample,
} from "../face-tracker/calibration";

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

const SAMPLE_MS = 1500;

export function CalibrationPage() {
  const videoRef = useRef<HTMLVideoElement>(null);
  const { reading, status, error } = useHumanTracker(true, videoRef);

  const [profileName, setProfileName] = useState("desk");
  const [step, setStep] = useState(0);
  const [sampling, setSampling] = useState(false);
  const [sampleCount, setSampleCount] = useState(0);
  const [dotSamples, setDotSamples] = useState<Record<string, DotSample>>({});
  const [warning, setWarning] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const [profiles, setProfiles] = useState<CalibrationProfile[]>([]);
  const [activeName, setActiveName] = useState<string | null>(null);

  const bufferRef = useRef<FrameReading[]>([]);
  const samplingRef = useRef(false);

  const target = TARGETS[step];

  const refreshProfiles = useCallback(() => {
    setProfiles(listProfiles());
    setActiveName(getActiveProfileName());
  }, []);

  useEffect(() => {
    refreshProfiles();
  }, [refreshProfiles]);

  // While sampling, collect every detected-face reading into the buffer.
  useEffect(() => {
    if (!samplingRef.current || !reading) return;
    if (reading.faceDetected) {
      bufferRef.current.push(reading);
      setSampleCount(bufferRef.current.length);
    }
  }, [reading]);

  const finishSampling = useCallback(() => {
    samplingRef.current = false;
    setSampling(false);
    const frames = bufferRef.current;
    bufferRef.current = [];
    setSampleCount(0);

    if (!target) return;
    if (frames.length < 3) {
      setWarning("Face not detected during sampling — adjust camera/lighting and retry this dot.");
      return;
    }
    setWarning(null);

    const avg = (sel: (f: FrameReading) => number) =>
      frames.reduce((a, f) => a + sel(f), 0) / frames.length;
    const sample: DotSample = {
      yaw: avg((f) => f.yaw),
      pitch: avg((f) => f.pitch),
      gazeStrength: avg((f) => f.gazeStrength),
      eyeOpenness: avg((f) => f.eyeOpenness),
    };

    const nextSamples = { ...dotSamples, [target.label]: sample };
    setDotSamples(nextSamples);

    if (step + 1 >= TARGETS.length) {
      const name = profileName.trim() || "desk";
      const profile = buildProfile(name, nextSamples);
      saveProfile(profile);
      setActiveProfileName(name);
      refreshProfiles();
      setDone(true);
    } else {
      setStep((s) => s + 1);
    }
  }, [dotSamples, profileName, refreshProfiles, step, target]);

  const record = useCallback(() => {
    if (done || sampling || status !== "running") return;
    if (!reading?.faceDetected) {
      setWarning("No face detected — check the preview before sampling.");
      return;
    }
    setWarning(null);
    bufferRef.current = [];
    samplingRef.current = true;
    setSampling(true);
    setTimeout(finishSampling, SAMPLE_MS);
  }, [done, sampling, status, reading, finishSampling]);

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

  const restart = () => {
    setStep(0);
    setDotSamples({});
    setDone(false);
    setWarning(null);
  };

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
          Keep your head naturally oriented toward the screen and follow each dot with your eyes. Press Space
          (or click) on each dot — head pose and gaze are sampled for 1.5s per dot. Save one profile per
          physical setup (desk, couch, side camera…).
        </p>
      </header>

      <div className="flex flex-wrap items-center gap-3">
        <label className="text-sm text-muted-foreground" htmlFor="profile-name">
          Profile name
        </label>
        <Input
          id="profile-name"
          className="w-40 h-8"
          value={profileName}
          onChange={(e) => setProfileName(e.target.value)}
          disabled={step > 0 && !done}
        />
        <span
          className={`text-xs px-2 py-0.5 rounded-full ${
            reading?.faceDetected
              ? "bg-emerald-500/20 text-emerald-400"
              : "bg-amber-500/20 text-amber-400"
          }`}
        >
          {status === "loading"
            ? "loading models…"
            : status === "error"
              ? "camera error"
              : reading?.faceDetected
                ? "face detected"
                : "no face"}
        </span>
      </div>
      {error && <p className="text-sm text-destructive">{error}</p>}
      {warning && <p className="text-sm text-amber-500">{warning}</p>}

      <Card className="relative gloss-panel aspect-video max-h-[60vh] w-full overflow-hidden cursor-crosshair" onClick={record}>
        {!done && target && (
          <div
            className={`absolute w-8 h-8 rounded-full -translate-x-1/2 -translate-y-1/2 transition-all duration-300 ${
              sampling ? "bg-amber-400 animate-pulse" : "bg-primary"
            } shadow-[0_0_20px_rgba(var(--primary),0.8)]`}
            style={{ left: `${target.x * 100}%`, top: `${target.y * 100}%` }}
            aria-hidden
          />
        )}
        {done ? (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 text-emerald-400 font-medium">
            <CheckCircle2 className="w-8 h-8" />
            Profile “{profileName.trim() || "desk"}” saved and set active
            <Button size="sm" variant="outline" onClick={restart}>
              Calibrate again
            </Button>
          </div>
        ) : (
          <div className="absolute bottom-4 left-4 text-xs text-muted-foreground">
            Step {step + 1} / {TARGETS.length} — {target?.label}
            {sampling && ` · sampling… ${sampleCount} frames`}
          </div>
        )}
        <video
          ref={videoRef}
          muted
          playsInline
          className="absolute top-3 right-3 w-36 rounded-lg border border-border/60 shadow-lg -scale-x-100"
        />
      </Card>

      <Card className="gloss-panel p-4 space-y-2">
        <p className="text-sm font-medium">Saved profiles</p>
        {profiles.length === 0 ? (
          <p className="text-xs text-muted-foreground">None yet — finish a calibration run above.</p>
        ) : (
          <ul className="space-y-1">
            {profiles.map((p) => (
              <li key={p.name} className="flex items-center gap-2 text-xs">
                <button
                  type="button"
                  className={`px-2 py-1 rounded-md ${
                    activeName === p.name ? "bg-primary/15 text-primary font-medium" : "hover:bg-muted"
                  }`}
                  onClick={() => {
                    setActiveProfileName(p.name);
                    refreshProfiles();
                  }}
                >
                  {p.name}
                  {activeName === p.name && " (active)"}
                </button>
                <span className="text-muted-foreground">
                  yaw {p.range.yawMin.toFixed(0)}°…{p.range.yawMax.toFixed(0)}° · pitch{" "}
                  {p.range.pitchMin.toFixed(0)}°…{p.range.pitchMax.toFixed(0)}°
                </span>
                <button
                  type="button"
                  className="ml-auto text-muted-foreground hover:text-destructive"
                  aria-label={`Delete profile ${p.name}`}
                  onClick={() => {
                    deleteProfile(p.name);
                    refreshProfiles();
                  }}
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
