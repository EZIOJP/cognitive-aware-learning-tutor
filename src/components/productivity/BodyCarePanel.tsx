/**
 * Focus Body care — sit/stand + eye rest + optional attention reader.
 * Client-only timers/notifications; SoftLand/Arm untouched.
 */
import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { Armchair, Eye, Loader2, ScanFace, PersonStanding, Crosshair } from "lucide-react";
import {
  requestBodyCareCalibrate,
  type BodyCareCalibrateMode,
} from "../../api/bodyCareClient";
import {
  DEFAULT_BODY_CARE,
  loadBodyCarePrefs,
  saveBodyCarePrefs,
  type BodyCarePrefs,
} from "../../lib/bodyCarePrefs";
import { focusDataUrl } from "../../utils/focusDataUrl";
import { isFocusDesktopShell } from "../../utils/focusDesktopShell";

function notificationSupported(): boolean {
  return typeof window !== "undefined" && "Notification" in window;
}

function Toggle({
  on,
  onChange,
  label,
}: {
  on: boolean;
  onChange: (v: boolean) => void;
  label: string;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      aria-label={label}
      onClick={() => onChange(!on)}
      className={`relative h-6 w-11 shrink-0 rounded-full transition-colors ${
        on ? "bg-emerald-500/80" : "bg-white/15"
      }`}
    >
      <span
        className={`absolute top-0.5 left-0.5 size-5 rounded-full bg-white transition-transform ${
          on ? "translate-x-5" : ""
        }`}
      />
    </button>
  );
}

function Num({
  value,
  onChange,
  min,
  max,
  suffix,
}: {
  value: number;
  onChange: (n: number) => void;
  min: number;
  max: number;
  suffix: string;
}) {
  return (
    <label className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
      <input
        type="number"
        min={min}
        max={max}
        value={value}
        onChange={(e) => onChange(Number(e.target.value) || min)}
        className="w-14 rounded border border-border/50 bg-background/50 px-1.5 py-1 text-xs text-foreground"
      />
      {suffix}
    </label>
  );
}

/** Renders panel with shell context if present; otherwise owns a provider. */
function AttentionPanelMount({
  Provider,
  Panel,
  useOptional,
}: {
  Provider: (p: { children: ReactNode; autoStart?: boolean }) => ReactNode;
  Panel: () => ReactNode;
  useOptional: () => unknown;
}) {
  const shell = useOptional();
  if (shell) return <Panel />;
  return (
    <Provider autoStart>
      <Panel />
    </Provider>
  );
}

/** Lazy attention reader — reuses shell FaceTracker when present; else mounts one. */
function AttentionReaderBlock({ enabled }: { enabled: boolean }) {
  const [mod, setMod] = useState<{
    Provider: (p: { children: ReactNode; autoStart?: boolean }) => ReactNode;
    Panel: () => ReactNode;
    useOptional: () => unknown;
  } | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!enabled) {
      setMod(null);
      setErr(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    void (async () => {
      try {
        const [ctx, panel] = await Promise.all([
          import("../../face-tracker/FaceTrackerContext"),
          import("./FocusAttentionPanel"),
        ]);
        if (cancelled) return;
        setMod({
          Provider: ctx.FaceTrackerProvider as (p: {
            children: ReactNode;
            autoStart?: boolean;
          }) => ReactNode,
          Panel: panel.FocusAttentionPanel as () => ReactNode,
          useOptional: ctx.useFaceTrackerOptional,
        });
        setErr(null);
      } catch (e: unknown) {
        if (!cancelled) {
          setErr(e instanceof Error ? e.message : "Could not load attention models");
          setMod(null);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [enabled]);

  if (!enabled) {
    return (
      <p className="text-[11px] text-muted-foreground">
        Off — turn on to load the webcam attention reader (models download once). Enables posture
        coach + sit-clock pause when you step away.
      </p>
    );
  }
  if (loading) {
    return (
      <p className="text-xs text-muted-foreground flex items-center gap-1.5">
        <Loader2 size={13} className="animate-spin" /> Loading attention models…
      </p>
    );
  }
  if (err || !mod) {
    return (
      <div className="space-y-2">
        <p className="text-xs text-rose-300">{err || "Attention reader unavailable"}</p>
        <p className="text-[11px] text-muted-foreground">
          Usually a stale UI build after an update. Reload Focus UI, then turn attention back on.
        </p>
        <button
          type="button"
          className="rounded-md border border-border/50 bg-background/40 px-2.5 py-1 text-[11px] hover:bg-accent/40"
          onClick={() => {
            try {
              const w = window as Window & {
                chrome?: { webview?: { postMessage: (m: unknown) => void } };
              };
              if (w.chrome?.webview?.postMessage) {
                w.chrome.webview.postMessage({ type: "focus_shell", v: 1, action: "reload_ui" });
                return;
              }
            } catch {
              /* fall through */
            }
            window.location.reload();
          }}
        >
          Reload Focus UI
        </button>
      </div>
    );
  }
  return <AttentionPanelMount {...mod} />;
}

export function BodyCarePanel() {
  const [prefs, setPrefs] = useState<BodyCarePrefs>(() => loadBodyCarePrefs());
  const [perm, setPerm] = useState<NotificationPermission | "unsupported">(
    notificationSupported() ? Notification.permission : "unsupported",
  );
  const [standHint, setStandHint] = useState<string | null>(null);
  const [sidecarLive, setSidecarLive] = useState<{
    attention_pct?: number;
    posture_score?: number;
    distance_proxy?: number | null;
    present?: boolean;
    sit_stand_hint?: string;
    sit_stand_ready?: boolean;
    sit_samples?: number;
    stand_samples?: number;
    blink_rate?: number;
    blink_just_now?: boolean;
    calibrating?: string | null;
    remain_sec?: number;
    control_port?: number;
    gaze_ready?: boolean;
    gaze_samples?: number;
  } | null>(null);
  const [calBusy, setCalBusy] = useState(false);
  const [calMsg, setCalMsg] = useState<string | null>(null);

  const patch = useCallback((partial: Partial<BodyCarePrefs>) => {
    setPrefs((prev) => {
      const next = { ...prev, ...partial };
      saveBodyCarePrefs(next);
      return next;
    });
  }, []);

  const runCalibrate = useCallback(
    async (mode: BodyCareCalibrateMode) => {
      setCalBusy(true);
      setCalMsg(
        mode === "neutral"
          ? "Hold a neutral gaze ~12s…"
          : mode === "sit"
            ? "Sit still ~4s…"
            : "Stand at desk ~4s…",
      );
      const r = await requestBodyCareCalibrate(mode, sidecarLive?.control_port);
      if (!r.ok) {
        setCalMsg(r.detail || "Calibrate failed");
        setCalBusy(false);
        return;
      }
      setCalMsg(`Running ${mode}…`);
      // Mirror poll will clear busy when calibrating ends.
      window.setTimeout(() => setCalBusy(false), mode === "neutral" ? 13_000 : 5_000);
    },
    [sidecarLive?.control_port],
  );

  const requestPerm = async () => {
    if (!notificationSupported()) return;
    const p = await Notification.requestPermission();
    setPerm(p);
  };

  // Wearable stand hint (optional).
  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const res = await fetch(`${focusDataUrl("wearable_day.json")}?t=${Date.now()}`, {
          cache: "no-store",
        });
        if (!res.ok || cancelled) return;
        const j = (await res.json()) as { stand_hours?: number; steps?: number };
        if (cancelled) return;
        if (typeof j.stand_hours === "number" && j.stand_hours > 0) {
          setStandHint(`Watch stand hours today: ${j.stand_hours}`);
        } else if (typeof j.steps === "number") {
          setStandHint(`Watch steps today: ${j.steps}`);
        }
      } catch {
        /* optional */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // Sidecar live strip (prefs + readout only — BodyCareRuntime owns nudges).
  useEffect(() => {
    let cancelled = false;
    const pull = async () => {
      try {
        const res = await fetch(`${focusDataUrl("body_care.json")}?t=${Date.now()}`, {
          cache: "no-store",
        });
        if (!res.ok || cancelled) {
          if (!cancelled && !res.ok) setSidecarLive(null);
          return;
        }
        const j = (await res.json()) as {
          sample?: {
            attention_pct?: number;
            posture_score?: number;
            distance_proxy?: number | null;
            present?: boolean;
            sit_stand_hint?: string;
            sit_stand_ready?: boolean;
            blink_rate?: number;
            blink_just_now?: boolean;
            calibrating?: string | null;
          };
          calibration?: {
            sit_stand_ready?: boolean;
            sit_samples?: number;
            stand_samples?: number;
            ready?: boolean;
            samples?: number;
          };
          control?: {
            port?: number;
            calibrating?: string | null;
            remain_sec?: number;
            sit_stand_ready?: boolean;
            sit_samples?: number;
            stand_samples?: number;
            gaze_ready?: boolean;
            gaze_samples?: number;
          };
          updated_at?: string;
        };
        if (cancelled) return;
        const live = j.sample
          ? {
              ...j.sample,
              sit_stand_ready:
                j.control?.sit_stand_ready ??
                j.sample.sit_stand_ready ??
                j.calibration?.sit_stand_ready,
              sit_samples: j.control?.sit_samples ?? j.calibration?.sit_samples,
              stand_samples: j.control?.stand_samples ?? j.calibration?.stand_samples,
              calibrating: j.control?.calibrating ?? j.sample.calibrating,
              remain_sec: j.control?.remain_sec,
              control_port: j.control?.port,
              gaze_ready: j.control?.gaze_ready ?? j.calibration?.ready,
              gaze_samples: j.control?.gaze_samples ?? j.calibration?.samples,
            }
          : null;
        setSidecarLive(live);
        if (live && !live.calibrating) {
          setCalBusy(false);
        }
      } catch {
        if (!cancelled) setSidecarLive(null);
      }
    };
    void pull();
    const id = window.setInterval(() => void pull(), 4_000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, []);

  const focusShell = isFocusDesktopShell();
  const summary = useMemo(() => {
    const bits: string[] = [];
    if (prefs.sitStandEnabled) bits.push(`Sit ${prefs.sitMinutes}m`);
    if (prefs.eyeRestEnabled) bits.push(`Eyes ${prefs.eyeRestMinutes}m`);
    if (prefs.attentionEnabled) {
      bits.push("Cam on");
      if (prefs.presencePauseSit) bits.push("pause away");
      if (prefs.postureCoachEnabled) bits.push(`posture ${prefs.postureWarnMinutes}m`);
    }
    return bits.length ? bits.join(" · ") : "All body care off";
  }, [prefs]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-2">
            <PersonStanding size={14} /> Body care
          </h3>
          <p className="mt-1 text-[11px] text-muted-foreground leading-relaxed max-w-lg">
            Sit/stand + eye rest run in the background (BodyCareRuntime). Opt-in webcam or the
            Python body-care sidecar adds posture/attention. Does not touch SoftLand or Arm.
          </p>
          <p className="mt-1 text-[11px] text-sky-300/90">{summary}</p>
          {sidecarLive ? (
            <p className="mt-1 text-[11px] tabular-nums text-emerald-200/90">
              Sidecar
              {sidecarLive.present === false ? " · away" : " · present"}
              {typeof sidecarLive.attention_pct === "number"
                ? ` · attn ${Math.round(sidecarLive.attention_pct)}%`
                : ""}
              {typeof sidecarLive.posture_score === "number"
                ? ` · posture ${Math.round(sidecarLive.posture_score)}`
                : ""}
              {typeof sidecarLive.distance_proxy === "number"
                ? ` · dist ~${sidecarLive.distance_proxy.toFixed(2)}`
                : ""}
              {typeof sidecarLive.blink_rate === "number"
                ? ` · blink ${Math.round(sidecarLive.blink_rate)}/m${
                    sidecarLive.blink_just_now ? " *" : ""
                  }`
                : ""}
              {sidecarLive.sit_stand_hint && sidecarLive.sit_stand_hint !== "unknown"
                ? ` · ${sidecarLive.sit_stand_hint}`
                : ""}
              {sidecarLive.calibrating
                ? ` · cal ${sidecarLive.calibrating}${
                    typeof sidecarLive.remain_sec === "number"
                      ? ` ${sidecarLive.remain_sec.toFixed(0)}s`
                      : ""
                  }`
                : ""}
            </p>
          ) : (
            <p className="mt-1 text-[10px] text-muted-foreground/80">
              Sidecar offline — Human.js fallback when attention is on. Run{" "}
              <span className="font-mono">scripts\run\run_bodycare_sidecar.bat</span>
            </p>
          )}
        </div>
        {perm !== "granted" && perm !== "unsupported" ? (
          <button
            type="button"
            onClick={() => void requestPerm()}
            className="rounded-lg border border-border/50 bg-background/35 px-3 py-1.5 text-xs hover:bg-accent/50"
          >
            Allow notifications
          </button>
        ) : null}
      </div>

      <div className="rounded-xl border border-border/50 bg-background/30 p-3 space-y-3">
        <div className="flex items-center gap-2 text-sm">
          <Crosshair size={15} className="text-emerald-300/90" />
          Recalibrate (sidecar)
        </div>
        <p className="text-[10px] text-muted-foreground leading-relaxed pl-6">
          Sidecar must be running. Gaze ~12s (eyes open, look at screen). Sit then Stand ~4s each
          (same screen angle).{" "}
          {sidecarLive
            ? `Gaze ${sidecarLive.gaze_ready ? "ready" : `${sidecarLive.gaze_samples ?? 0}/15`} · sit ${
                sidecarLive.sit_samples ?? 0
              }/6 · stand ${sidecarLive.stand_samples ?? 0}/6${
                sidecarLive.sit_stand_ready ? " · sit/stand ready" : ""
              }`
            : "Start scripts\\run\\run_bodycare_sidecar.bat first."}
        </p>
        <div className="flex flex-wrap gap-2 pl-6">
          <button
            type="button"
            disabled={calBusy || !sidecarLive || Boolean(sidecarLive?.calibrating)}
            onClick={() => void runCalibrate("neutral")}
            className="rounded-lg border border-border/50 bg-background/40 px-3 py-1.5 text-xs hover:bg-accent/40 disabled:opacity-40"
          >
            Gaze
          </button>
          <button
            type="button"
            disabled={calBusy || !sidecarLive || Boolean(sidecarLive?.calibrating)}
            onClick={() => void runCalibrate("sit")}
            className="rounded-lg border border-border/50 bg-background/40 px-3 py-1.5 text-xs hover:bg-accent/40 disabled:opacity-40"
          >
            Sit pose
          </button>
          <button
            type="button"
            disabled={calBusy || !sidecarLive || Boolean(sidecarLive?.calibrating)}
            onClick={() => void runCalibrate("stand")}
            className="rounded-lg border border-border/50 bg-background/40 px-3 py-1.5 text-xs hover:bg-accent/40 disabled:opacity-40"
          >
            Stand pose
          </button>
          {calMsg ? (
            <span className="self-center text-[11px] text-sky-300/90" role="status">
              {calMsg}
            </span>
          ) : null}
        </div>
      </div>

      <div className="rounded-xl border border-border/50 bg-background/30 p-3 space-y-3">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2 text-sm">
            <Armchair size={15} className="text-amber-200/90" />
            Sit / stand
          </div>
          <Toggle
            label="Sit stand reminders"
            on={prefs.sitStandEnabled}
            onChange={(v) => patch({ sitStandEnabled: v })}
          />
        </div>
        {prefs.sitStandEnabled ? (
          <div className="flex flex-wrap items-center gap-3 pl-6">
            <Num
              value={prefs.sitMinutes}
              onChange={(n) => patch({ sitMinutes: n })}
              min={10}
              max={120}
              suffix="min sit → stand"
            />
            <Num
              value={prefs.standMinutes}
              onChange={(n) => patch({ standMinutes: n })}
              min={1}
              max={15}
              suffix="min stand"
            />
            <span className="text-[11px] text-muted-foreground">Nudges via runtime</span>
          </div>
        ) : null}
        {standHint ? <p className="pl-6 text-[11px] text-muted-foreground">{standHint}</p> : null}
        <p className="pl-6 text-[10px] text-muted-foreground leading-relaxed">
          Webcam sit/stand uses upper-body Y-shift + face scale. Use the Recalibrate buttons above
          (or bats). Frames stay in RAM only.
        </p>
        {prefs.sitStandEnabled && prefs.attentionEnabled ? (
          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border/30 pt-3 pl-6">
            <div>
              <p className="text-xs text-foreground/90">Pause sit clock when away / standing</p>
              <p className="text-[10px] text-muted-foreground">
                No face for {prefs.presenceAwaySec}s, or sidecar hint = stand, freezes the timer.
              </p>
            </div>
            <Toggle
              label="Presence pause sit"
              on={prefs.presencePauseSit}
              onChange={(v) => patch({ presencePauseSit: v })}
            />
          </div>
        ) : null}
      </div>

      <div className="rounded-xl border border-border/50 bg-background/30 p-3 space-y-3">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2 text-sm">
            <Eye size={15} className="text-sky-300" />
            Eye rest (20–20–20)
          </div>
          <Toggle
            label="Eye rest reminders"
            on={prefs.eyeRestEnabled}
            onChange={(v) => patch({ eyeRestEnabled: v })}
          />
        </div>
        {prefs.eyeRestEnabled ? (
          <div className="flex flex-wrap items-center gap-3 pl-6">
            <Num
              value={prefs.eyeRestMinutes}
              onChange={(n) => patch({ eyeRestMinutes: n })}
              min={10}
              max={60}
              suffix="min between"
            />
            <Num
              value={prefs.eyeRestSeconds}
              onChange={(n) => patch({ eyeRestSeconds: n })}
              min={10}
              max={60}
              suffix="sec look away"
            />
            <span className="text-[11px] text-muted-foreground">Nudges via runtime</span>
          </div>
        ) : null}
      </div>

      <div className="rounded-xl border border-border/50 bg-background/30 p-3 space-y-3">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2 text-sm">
            <ScanFace size={15} className="text-primary" />
            Eye focus — attention reader
          </div>
          <Toggle
            label="Attention reader"
            on={prefs.attentionEnabled}
            onChange={(v) => patch({ attentionEnabled: v })}
          />
        </div>
        <AttentionReaderBlock enabled={prefs.attentionEnabled} />
        {prefs.attentionEnabled ? (
          <div className="space-y-2 border-t border-border/30 pt-3">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-xs text-foreground/90">Posture coach</p>
                <p className="text-[10px] text-muted-foreground">
                  Uses the same webcam: scores neck/lean. If you stay slumped past the minutes
                  below, Focus nudges you to sit tall. SoftLand/Arm untouched.
                </p>
              </div>
              <Toggle
                label="Posture coach"
                on={prefs.postureCoachEnabled}
                onChange={(v) => patch({ postureCoachEnabled: v })}
              />
            </div>
            {prefs.postureCoachEnabled ? (
              <div className="flex flex-wrap items-center gap-3">
                <Num
                  value={prefs.postureWarnMinutes}
                  onChange={(n) => patch({ postureWarnMinutes: n })}
                  min={1}
                  max={15}
                  suffix="min poor posture"
                />
                <Num
                  value={prefs.postureScoreThreshold}
                  onChange={(n) => patch({ postureScoreThreshold: n })}
                  min={25}
                  max={80}
                  suffix="score floor"
                />
              </div>
            ) : null}
          </div>
        ) : null}
        {!focusShell ? (
          <p className="text-[10px] text-muted-foreground">
            Works in design host and Focus desktop. Grant camera when prompted.
          </p>
        ) : null}
      </div>

      <button
        type="button"
        className="text-[11px] text-muted-foreground underline-offset-2 hover:underline"
        onClick={() => {
          saveBodyCarePrefs(DEFAULT_BODY_CARE);
          setPrefs({ ...DEFAULT_BODY_CARE });
        }}
      >
        Reset body care defaults
      </button>
    </div>
  );
}

export default BodyCarePanel;
