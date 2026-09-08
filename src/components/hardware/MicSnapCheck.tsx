import { useCallback, useEffect, useRef, useState } from "react";
import { Mic, MicOff, Volume2 } from "lucide-react";
import { Card } from "../../app/components/ui/card";

type SnapEvent = {
  id: number;
  at: string;
  peak: number;
};

/**
 * Laptop-mic dry run: detect finger snaps (transient loud peaks).
 * Proves audio capture + event UI without BioAmp / ESP32 wiring.
 */
export function MicSnapCheck() {
  const [listening, setListening] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [level, setLevel] = useState(0);
  const [snaps, setSnaps] = useState<SnapEvent[]>([]);
  const [lastMsg, setLastMsg] = useState("Idle — tap Start, allow mic, then snap your fingers");

  const audioCtxRef = useRef<AudioContext | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const rafRef = useRef<number>(0);
  const lastSnapMs = useRef(0);
  const idRef = useRef(0);
  // EMA of RMS so snaps stand out vs ambient
  const baselineRef = useRef(0.02);

  const stop = useCallback(() => {
    if (rafRef.current) cancelAnimationFrame(rafRef.current);
    rafRef.current = 0;
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    void audioCtxRef.current?.close();
    audioCtxRef.current = null;
    setListening(false);
    setLevel(0);
    setLastMsg("Stopped");
  }, []);

  useEffect(() => () => stop(), [stop]);

  const start = async () => {
    setError(null);
    setSnaps([]);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: false,
          noiseSuppression: false,
          autoGainControl: false,
        },
      });
      streamRef.current = stream;
      const ctx = new AudioContext();
      audioCtxRef.current = ctx;
      const source = ctx.createMediaStreamSource(stream);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 2048;
      analyser.smoothingTimeConstant = 0.2;
      source.connect(analyser);

      const buf = new Float32Array(analyser.fftSize);
      baselineRef.current = 0.02;
      lastSnapMs.current = 0;
      setListening(true);
      setLastMsg("Listening… snap near the mic");

      const tick = () => {
        analyser.getFloatTimeDomainData(buf);
        let sum = 0;
        let peak = 0;
        for (let i = 0; i < buf.length; i++) {
          const v = buf[i];
          const a = Math.abs(v);
          sum += v * v;
          if (a > peak) peak = a;
        }
        const rms = Math.sqrt(sum / buf.length);
        // Slow baseline (ambient); snaps are short high peak vs baseline
        baselineRef.current = baselineRef.current * 0.995 + rms * 0.005;
        const display = Math.min(100, Math.round(peak * 140));
        setLevel(display);

        const now = performance.now();
        const coolDownMs = 450;
        const isSnap =
          peak > 0.35 &&
          peak > baselineRef.current * 8 &&
          now - lastSnapMs.current > coolDownMs;

        if (isSnap) {
          lastSnapMs.current = now;
          idRef.current += 1;
          const stamp = new Date().toLocaleTimeString();
          const ev: SnapEvent = { id: idRef.current, at: stamp, peak: Math.round(peak * 1000) / 1000 };
          setSnaps((prev) => [ev, ...prev].slice(0, 12));
          setLastMsg(`SNAP #${ev.id} at ${stamp} · peak ${ev.peak}`);
          console.info("[mic-snap]", ev);
        }

        rafRef.current = requestAnimationFrame(tick);
      };
      rafRef.current = requestAnimationFrame(tick);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Mic permission denied or unavailable");
      setListening(false);
      setLastMsg("Mic unavailable");
    }
  };

  return (
    <Card className="p-5 gloss-panel border-white/10 space-y-3">
      <div className="flex items-start gap-3">
        <div className="w-10 h-10 rounded-xl bg-emerald-500/15 flex items-center justify-center shrink-0">
          <Volume2 className="w-5 h-5 text-emerald-400" />
        </div>
        <div className="min-w-0 flex-1 space-y-1">
          <p className="font-semibold text-foreground text-sm">Mic dry-run — finger snap check</p>
          <p className="text-xs text-muted-foreground">
            No ESP32 needed. Allow the mic, snap your fingers, and watch the meter + log. Same idea as
            EEG spikes: sudden peak → event with timestamp.
          </p>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {!listening ? (
          <button
            type="button"
            onClick={() => void start()}
            className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-600/90 px-3 py-1.5 text-xs font-medium text-white hover:bg-emerald-500"
          >
            <Mic className="w-3.5 h-3.5" /> Start mic
          </button>
        ) : (
          <button
            type="button"
            onClick={stop}
            className="inline-flex items-center gap-1.5 rounded-lg border border-white/15 bg-white/5 px-3 py-1.5 text-xs text-foreground hover:bg-white/10"
          >
            <MicOff className="w-3.5 h-3.5" /> Stop
          </button>
        )}
        <span className="text-[11px] text-muted-foreground tabular-nums">{lastMsg}</span>
      </div>

      {error ? <p className="text-xs text-red-400">{error}</p> : null}

      <div className="space-y-1">
        <div className="flex justify-between text-[10px] uppercase tracking-wider text-muted-foreground">
          <span>Level</span>
          <span className="tabular-nums">{level}%</span>
        </div>
        <div className="h-2.5 rounded-full bg-black/40 overflow-hidden">
          <div
            className={`h-full transition-[width] duration-75 ${
              level > 55 ? "bg-amber-400" : "bg-emerald-500/80"
            }`}
            style={{ width: `${level}%` }}
          />
        </div>
      </div>

      <div className="rounded-lg border border-white/10 bg-black/40 px-3 py-2 font-mono text-[11px] max-h-40 overflow-y-auto">
        {snaps.length === 0 ? (
          <p className="text-muted-foreground">Output log empty — snaps appear here</p>
        ) : (
          <ul className="space-y-1">
            {snaps.map((s) => (
              <li key={s.id} className="text-emerald-300/90">
                [{s.at}] SNAP #{s.id} peak={s.peak}
              </li>
            ))}
          </ul>
        )}
      </div>
    </Card>
  );
}
