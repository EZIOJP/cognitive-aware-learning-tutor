import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router";
import { Clock, Loader2, RotateCcw } from "lucide-react";
import {
  clearDemoClock,
  fetchDemoClock,
  fetchDistractionGate,
  setDemoClock,
  type DemoClockPayload,
  type DemoRealDay,
} from "../../api/behaviorClient";
import { formatHoursMins } from "../../utils/formatDuration";

type Props = {
  onChanged?: () => void;
  onJumpToDay?: (day: Date) => void;
};

const TIME_PRESETS: { label: string; hhmm: string; hint: string }[] = [
  { label: "05:30", hhmm: "05:30", hint: "Early — Bible window" },
  { label: "08:00", hhmm: "08:00", hint: "Plan window" },
  { label: "14:00", hhmm: "14:00", hint: "Midday STUDY" },
  { label: "21:30", hhmm: "21:30", hint: "After FREE hour" },
];

function toLocalInputValue(iso: string | null | undefined): string {
  const d = iso ? new Date(iso) : new Date();
  if (Number.isNaN(d.getTime())) return "";
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function fromLocalInputValue(local: string): string {
  const d = new Date(local);
  return d.toISOString();
}

function parseDay(day: string): Date {
  const [y, m, d] = day.split("-").map(Number);
  return new Date(y, (m || 1) - 1, d || 1, 12, 0, 0, 0);
}

export function DemoModePanel({ onChanged, onJumpToDay }: Props) {
  const [payload, setPayload] = useState<DemoClockPayload | null>(null);
  const [localWhen, setLocalWhen] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [gateHint, setGateHint] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchDemoClock();
      setPayload(data);
      setLocalWhen(toLocalInputValue(data.now_iso || data.real_now_iso));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load demo clock");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const refreshGateHint = useCallback(async () => {
    try {
      const g = await fetchDistractionGate();
      const mode = g.browser?.mode_label || g.browser_mode || "?";
      const next = g.morning?.next || "?";
      setGateHint(
        `Gate day ${g.day} · morning.next=${next} · browser=${mode} · productive=${formatHoursMins(g.productive_minutes)} / ${formatHoursMins(g.daily_goal_minutes)} (real)`,
      );
    } catch {
      setGateHint(null);
    }
  }, []);

  useEffect(() => {
    if (payload?.enabled) void refreshGateHint();
  }, [payload?.enabled, payload?.now_iso, refreshGateHint]);

  const realDays: DemoRealDay[] = useMemo(() => payload?.real_days || [], [payload]);

  const apply = async (enabled: boolean, whenLocal: string) => {
    setBusy(true);
    setError(null);
    try {
      if (!enabled) {
        const cleared = await clearDemoClock();
        setPayload((prev) => ({ ...(prev || cleared), ...cleared, real_days: prev?.real_days }));
        setGateHint(null);
      } else {
        const st = await setDemoClock({ enabled: true, now_iso: fromLocalInputValue(whenLocal) });
        setPayload((prev) => ({ ...(prev || st), ...st, real_days: prev?.real_days }));
        await refreshGateHint();
      }
      onChanged?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Demo clock update failed");
    } finally {
      setBusy(false);
    }
  };

  const setPresetTime = async (hhmm: string) => {
    const base = localWhen || toLocalInputValue(new Date().toISOString());
    const dayPart = base.slice(0, 10);
    const next = `${dayPart}T${hhmm}`;
    setLocalWhen(next);
    await apply(true, next);
  };

  const jumpRealDay = async (day: string) => {
    const timePart = (localWhen || "12:00").slice(11, 16) || "12:00";
    const next = `${day}T${timePart}`;
    setLocalWhen(next);
    await apply(true, next);
    onJumpToDay?.(parseDay(day));
  };

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <Loader2 size={14} className="animate-spin" /> Loading demo clock…
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-medium text-foreground flex items-center gap-2">
            <Clock size={14} className="text-amber-300" />
            Demo clock
          </h3>
          <p className="text-[11px] text-muted-foreground mt-1 max-w-xl">
            Scrub wall time to show Bible → Plan → STUDY → FREE. Uses{" "}
            <strong className="text-foreground/90 font-medium">real</strong> tracked / plan data for
            that day. No fake productive minutes. Read-only — confirms and auto-plan writes are
            blocked while demo is on.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            disabled={busy}
            onClick={() => void apply(true, localWhen)}
            className="text-xs px-3 py-1.5 rounded-md bg-amber-500/25 text-amber-50 border border-amber-400/40 hover:bg-amber-500/35 disabled:opacity-50"
          >
            {payload?.enabled ? "Update clock" : "Enable demo"}
          </button>
          <button
            type="button"
            disabled={busy || !payload?.enabled}
            onClick={() => void apply(false, localWhen)}
            className="text-xs px-3 py-1.5 rounded-md border border-white/15 text-foreground/90 hover:bg-white/5 disabled:opacity-40 inline-flex items-center gap-1"
          >
            <RotateCcw size={12} />
            Real time
          </button>
        </div>
      </div>

      {payload?.enabled && (
        <p className="text-[11px] rounded-lg border border-amber-400/40 bg-amber-500/15 text-amber-50 px-3 py-2">
          DEMO ON — clock {payload.now_iso ? new Date(payload.now_iso).toLocaleString() : "?"}
          {payload.real_now_iso
            ? ` · real ${new Date(payload.real_now_iso).toLocaleString()}`
            : ""}
        </p>
      )}

      <label className="block space-y-1">
        <span className="text-[11px] text-muted-foreground">Demo date & time (local)</span>
        <input
          type="datetime-local"
          value={localWhen}
          onChange={(e) => setLocalWhen(e.target.value)}
          className="w-full max-w-sm text-sm px-3 py-1.5 rounded-lg bg-black/30 border border-white/10"
        />
      </label>

      <div className="flex flex-wrap gap-2">
        {TIME_PRESETS.map((p) => (
          <button
            key={p.hhmm}
            type="button"
            disabled={busy || !localWhen}
            title={p.hint}
            onClick={() => void setPresetTime(p.hhmm)}
            className="text-[11px] px-2.5 py-1 rounded-md border border-white/15 hover:bg-white/5 disabled:opacity-40"
          >
            {p.label}
          </button>
        ))}
      </div>

      {gateHint && <p className="text-[11px] text-sky-200/90 font-mono">{gateHint}</p>}

      <div className="space-y-2">
        <p className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
          Real days with data (open calendar)
        </p>
        <p className="text-[10px] text-muted-foreground">
          No October sample in this DB — pick a day that already has planner / tracked sessions (e.g.
          2026-08-04, 2026-07-04).
        </p>
        <div className="flex flex-wrap gap-1.5 max-h-28 overflow-y-auto">
          {realDays.length === 0 ? (
            <span className="text-[11px] text-muted-foreground">No days found yet.</span>
          ) : (
            realDays.slice(0, 16).map((d) => (
              <button
                key={d.day}
                type="button"
                disabled={busy}
                onClick={() => void jumpRealDay(d.day)}
                className="text-[11px] px-2 py-1 rounded-md border border-white/12 hover:bg-white/5 tabular-nums disabled:opacity-40"
                title={d.sources.join(", ")}
              >
                {d.day}
                <span className="text-muted-foreground ml-1">{d.events}</span>
              </button>
            ))
          )}
        </div>
        <Link
          to="/productivity"
          className="text-[11px] text-sky-300 underline underline-offset-2 hover:text-white"
        >
          Open Productivity calendar
        </Link>
      </div>

      {error && (
        <p className="text-sm text-red-300 bg-red-500/10 border border-red-500/30 rounded-lg px-3 py-2">
          {error}
        </p>
      )}
    </div>
  );
}

export default DemoModePanel;
