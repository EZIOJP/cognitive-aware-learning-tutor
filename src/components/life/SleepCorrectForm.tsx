import { useEffect, useMemo, useState } from "react";
import { postManualSleepCorrection } from "../../api/wearablesClient";
import type { WearableDay } from "../../api/wearablesClient";

function clockFromMin(min: number | null | undefined): string {
  if (min == null || !Number.isFinite(min) || min < 0) return "";
  const m = ((Math.round(min) % 1440) + 1440) % 1440;
  return `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;
}

function fromIsoAt(at: string | null | undefined): string {
  if (!at || at.length < 16) return "";
  return at.slice(11, 16);
}

export function SleepCorrectForm({
  day,
  localDate,
  onSaved,
}: {
  day: WearableDay | null | undefined;
  localDate: string;
  onSaved?: () => void;
}) {
  const sleep = day?.sleep || (day?.payload as { sleep?: Record<string, unknown> } | undefined)?.sleep;
  const sleepObj = sleep && typeof sleep === "object" ? (sleep as Record<string, unknown>) : null;

  const defaults = useMemo(() => {
    const startAt =
      (typeof day?.sleep_start_at === "string" && day.sleep_start_at) ||
      (typeof sleepObj?.start_at === "string" ? String(sleepObj.start_at) : "");
    const endAt =
      (typeof day?.sleep_end_at === "string" && day.sleep_end_at) ||
      (typeof sleepObj?.end_at === "string" ? String(sleepObj.end_at) : "");
    const startMin =
      typeof day?.sleep_start_min === "number"
        ? day.sleep_start_min
        : typeof sleepObj?.start_min === "number"
          ? Number(sleepObj.start_min)
          : null;
    const endMin =
      typeof day?.sleep_end_min === "number"
        ? day.sleep_end_min
        : typeof sleepObj?.end_min === "number"
          ? Number(sleepObj.end_min)
          : null;
    const hours =
      typeof day?.sleep_hours === "number" && day.sleep_hours > 0
        ? day.sleep_hours
        : typeof sleepObj?.total_min === "number" && Number(sleepObj.total_min) > 0
          ? Number(sleepObj.total_min) / 60
          : null;
    const score =
      typeof day?.sleep_score === "number"
        ? day.sleep_score
        : typeof sleepObj?.score === "number"
          ? Number(sleepObj.score)
          : null;
    const deep =
      typeof day?.sleep_deep_min === "number"
        ? day.sleep_deep_min
        : typeof sleepObj?.deep_min === "number"
          ? Number(sleepObj.deep_min)
          : null;
    return {
      bedtime: fromIsoAt(startAt) || clockFromMin(startMin),
      wake: fromIsoAt(endAt) || clockFromMin(endMin),
      hours: hours != null ? hours.toFixed(2) : "",
      score: score != null && score > 0 ? String(Math.round(score)) : "",
      deepMin: deep != null && deep > 0 ? String(Math.round(deep)) : "",
    };
  }, [day, sleepObj]);

  const [open, setOpen] = useState(false);
  const [bedtime, setBedtime] = useState(defaults.bedtime);
  const [wake, setWake] = useState(defaults.wake);
  const [hours, setHours] = useState(defaults.hours);
  const [score, setScore] = useState(defaults.score);
  const [deepMin, setDeepMin] = useState(defaults.deepMin);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setBedtime(defaults.bedtime);
    setWake(defaults.wake);
    setHours(defaults.hours);
    setScore(defaults.score);
    setDeepMin(defaults.deepMin);
    setError(null);
    setOk(null);
  }, [open, defaults]);

  const preview = useMemo(() => {
    const parseHm = (s: string) => {
      const m = /^(\d{1,2}):(\d{2})$/.exec(s.trim());
      if (!m) return null;
      const h = Number(m[1]);
      const mm = Number(m[2]);
      if (h > 23 || mm > 59) return null;
      return h * 60 + mm;
    };
    const b = parseHm(bedtime);
    const w = parseHm(wake);
    if (b != null && w != null) {
      const dur = w > b ? w - b : w + 1440 - b;
      return `${(dur / 60).toFixed(2)}h from times`;
    }
    const h = Number(hours);
    if (Number.isFinite(h) && h > 0) return `${h.toFixed(2)}h duration only`;
    return "Enter bedtime + wake, or hours";
  }, [bedtime, wake, hours]);

  const save = async () => {
    setBusy(true);
    setError(null);
    setOk(null);
    try {
      const res = await postManualSleepCorrection({
        localDate,
        bedtime: bedtime.trim() || undefined,
        wake: wake.trim() || undefined,
        hours: hours.trim() ? Number(hours) : undefined,
        score: score.trim() ? Number(score) : undefined,
        deepMin: deepMin.trim() ? Number(deepMin) : undefined,
      });
      setOk(
        `Saved ${res.sleep_hours != null ? `${Number(res.sleep_hours).toFixed(2)}h` : "sleep"} · ${localDate}`,
      );
      onSaved?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="border-t border-border/30 pt-3">
      <button
        type="button"
        className="text-xs text-sky-200/90 underline-offset-2 hover:underline"
        onClick={() => setOpen((v) => !v)}
      >
        {open ? "Hide sleep correction" : "Correct sleep…"}
      </button>
      {open ? (
        <div className="mt-3 space-y-3 rounded-xl border border-sky-400/20 bg-sky-500/5 p-3">
          <p className="text-[11px] text-muted-foreground">
            Manual fix for {localDate}. Overwrites watch sleep for this day (keeps steps/HR).
          </p>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            <label className="block text-[10px] uppercase tracking-wide text-muted-foreground space-y-1">
              Bedtime
              <input
                type="time"
                value={bedtime}
                onChange={(e) => setBedtime(e.target.value)}
                className="w-full rounded-md border border-border/50 bg-background/40 px-2 py-1.5 text-sm tabular-nums"
              />
            </label>
            <label className="block text-[10px] uppercase tracking-wide text-muted-foreground space-y-1">
              Wake
              <input
                type="time"
                value={wake}
                onChange={(e) => setWake(e.target.value)}
                className="w-full rounded-md border border-border/50 bg-background/40 px-2 py-1.5 text-sm tabular-nums"
              />
            </label>
            <label className="block text-[10px] uppercase tracking-wide text-muted-foreground space-y-1">
              Hours
              <input
                type="number"
                step="0.25"
                min="0"
                max="16"
                placeholder="optional"
                value={hours}
                onChange={(e) => setHours(e.target.value)}
                className="w-full rounded-md border border-border/50 bg-background/40 px-2 py-1.5 text-sm tabular-nums"
              />
            </label>
            <label className="block text-[10px] uppercase tracking-wide text-muted-foreground space-y-1">
              Score
              <input
                type="number"
                min="0"
                max="100"
                placeholder="0–100"
                value={score}
                onChange={(e) => setScore(e.target.value)}
                className="w-full rounded-md border border-border/50 bg-background/40 px-2 py-1.5 text-sm tabular-nums"
              />
            </label>
          </div>
          <label className="block text-[10px] uppercase tracking-wide text-muted-foreground space-y-1 max-w-[10rem]">
            Deep (min)
            <input
              type="number"
              min="0"
              max="600"
              placeholder="optional"
              value={deepMin}
              onChange={(e) => setDeepMin(e.target.value)}
              className="w-full rounded-md border border-border/50 bg-background/40 px-2 py-1.5 text-sm tabular-nums"
            />
          </label>
          <p className="text-[11px] tabular-nums text-muted-foreground">{preview}</p>
          {error ? <p className="text-xs text-rose-300">{error}</p> : null}
          {ok ? <p className="text-xs text-emerald-300">{ok}</p> : null}
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              disabled={busy}
              onClick={() => void save()}
              className="rounded-lg border border-sky-400/40 bg-sky-500/15 px-3 py-1.5 text-xs font-medium text-sky-50 disabled:opacity-50"
            >
              {busy ? "Saving…" : "Save sleep"}
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() => setOpen(false)}
              className="rounded-lg border border-border/40 px-3 py-1.5 text-xs text-muted-foreground"
            >
              Cancel
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
