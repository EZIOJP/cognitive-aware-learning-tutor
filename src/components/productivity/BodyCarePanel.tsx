/**
 * Focus Body care — sit/stand + eye rest + optional attention reader.
 * Client-only timers/notifications; SoftLand/Arm untouched.
 */
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Armchair, Eye, Loader2, ScanFace, PersonStanding } from "lucide-react";
import {
  DEFAULT_BODY_CARE,
  loadBodyCarePrefs,
  saveBodyCarePrefs,
  type BodyCarePrefs,
} from "../../lib/bodyCarePrefs";
import { focusDataUrl } from "../../utils/focusDataUrl";
import { isFocusDesktopShell } from "../../utils/focusDesktopShell";

function notify(title: string, body: string) {
  if (typeof Notification === "undefined") return;
  if (Notification.permission !== "granted") return;
  try {
    new Notification(title, { body, silent: false });
  } catch {
    /* ignore */
  }
}

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

/** Lazy attention reader — only mounts Human.js when user enables it. */
function AttentionReaderBlock({ enabled }: { enabled: boolean }) {
  const [mod, setMod] = useState<{
    Provider: (p: { children: ReactNode }) => ReactNode;
    Panel: () => ReactNode;
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
        const [{ FaceTrackerProvider }, { FocusAttentionPanel }] = await Promise.all([
          import("../../face-tracker/FaceTrackerContext"),
          import("./FocusAttentionPanel"),
        ]);
        if (cancelled) return;
        setMod({
          Provider: FaceTrackerProvider as (p: { children: ReactNode }) => ReactNode,
          Panel: FocusAttentionPanel as () => ReactNode,
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
        Off — turn on to load the webcam attention reader (models download once).
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
    return <p className="text-xs text-rose-300">{err || "Attention reader unavailable"}</p>;
  }
  const { Provider, Panel } = mod;
  return (
    <Provider>
      <Panel />
    </Provider>
  );
}

export function BodyCarePanel() {
  const [prefs, setPrefs] = useState<BodyCarePrefs>(() => loadBodyCarePrefs());
  const [perm, setPerm] = useState<NotificationPermission | "unsupported">(
    notificationSupported() ? Notification.permission : "unsupported",
  );
  const [sitLeftMin, setSitLeftMin] = useState<number | null>(null);
  const [eyeLeftMin, setEyeLeftMin] = useState<number | null>(null);
  const [standHint, setStandHint] = useState<string | null>(null);
  const lastInputRef = useRef(Date.now());
  const lastSitNotifyRef = useRef(0);
  const lastEyeNotifyRef = useRef(Date.now());
  const prefsRef = useRef(prefs);
  prefsRef.current = prefs;

  const patch = useCallback((partial: Partial<BodyCarePrefs>) => {
    setPrefs((prev) => {
      const next = { ...prev, ...partial };
      saveBodyCarePrefs(next);
      return next;
    });
  }, []);

  const requestPerm = async () => {
    if (!notificationSupported()) return;
    const p = await Notification.requestPermission();
    setPerm(p);
  };

  // Presence = any input resets sit clock.
  useEffect(() => {
    const bump = () => {
      lastInputRef.current = Date.now();
    };
    const evs = ["mousemove", "keydown", "pointerdown", "wheel", "touchstart"] as const;
    for (const e of evs) window.addEventListener(e, bump, { passive: true });
    return () => {
      for (const e of evs) window.removeEventListener(e, bump);
    };
  }, []);

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

  // Timers.
  useEffect(() => {
    const id = window.setInterval(() => {
      const p = prefsRef.current;
      const now = Date.now();
      const seatedMs = now - lastInputRef.current;

      if (p.sitStandEnabled) {
        const limit = p.sitMinutes * 60_000;
        const left = Math.max(0, Math.ceil((limit - seatedMs) / 60_000));
        setSitLeftMin(left);
        if (seatedMs >= limit && now - lastSitNotifyRef.current > 5 * 60_000) {
          lastSitNotifyRef.current = now;
          notify(
            "CALT — stand up",
            `You've been still ~${p.sitMinutes} min. Stand ${p.standMinutes} min, then sit.`,
          );
          lastInputRef.current = now; // avoid spam until next sit window
        }
      } else {
        setSitLeftMin(null);
      }

      if (p.eyeRestEnabled) {
        const elapsed = now - lastEyeNotifyRef.current;
        const limit = p.eyeRestMinutes * 60_000;
        setEyeLeftMin(Math.max(0, Math.ceil((limit - elapsed) / 60_000)));
        if (elapsed >= limit) {
          lastEyeNotifyRef.current = now;
          notify(
            "CALT — eye rest",
            `Look away ${p.eyeRestSeconds}s (20–20–20). Soften focus, then return.`,
          );
        }
      } else {
        setEyeLeftMin(null);
      }
    }, 15_000);
    return () => window.clearInterval(id);
  }, []);

  const focusShell = isFocusDesktopShell();
  const summary = useMemo(() => {
    const bits: string[] = [];
    if (prefs.sitStandEnabled) bits.push(`Sit ${prefs.sitMinutes}m`);
    if (prefs.eyeRestEnabled) bits.push(`Eyes ${prefs.eyeRestMinutes}m`);
    if (prefs.attentionEnabled) bits.push("Attention on");
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
            Sit/stand + eye rest run locally in Focus. Attention reader is opt-in webcam (same models
            as Study Focus tracker). Does not touch SoftLand or Arm.
          </p>
          <p className="mt-1 text-[11px] text-sky-300/90">{summary}</p>
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
            {sitLeftMin != null ? (
              <span className="text-[11px] text-muted-foreground">
                Next stand nudge in ~{sitLeftMin}m
              </span>
            ) : null}
          </div>
        ) : null}
        {standHint ? <p className="pl-6 text-[11px] text-muted-foreground">{standHint}</p> : null}
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
            {eyeLeftMin != null ? (
              <span className="text-[11px] text-muted-foreground">Next eye rest ~{eyeLeftMin}m</span>
            ) : null}
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
          lastEyeNotifyRef.current = Date.now();
          lastInputRef.current = Date.now();
        }}
      >
        Reset body care defaults
      </button>
    </div>
  );
}

export default BodyCarePanel;
