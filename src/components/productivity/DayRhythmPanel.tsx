import { useEffect, useMemo, useState } from "react";
import { Moon } from "lucide-react";
import { setBedtime } from "../../api/dayLoopClient";
import { subscribeFocusStatus } from "../../lib/focusStatusBus";

/** Minutes before bedtime when wind-down should start (guidance only). */
const WIND_DOWN_BEFORE_MIN = 30;

function parseHm(hm: string): number | null {
  const m = /^(\d{1,2}):(\d{2})$/.exec((hm || "").trim());
  if (!m) return null;
  const h = Number(m[1]);
  const min = Number(m[2]);
  if (h < 0 || h > 23 || min < 0 || min > 59) return null;
  return h * 60 + min;
}

/** Overnight-aware duration bed → wake (minutes). */
function sleepMinutes(bedHm: string, wakeHm: string): number | null {
  const bed = parseHm(bedHm);
  const wake = parseHm(wakeHm);
  if (bed == null || wake == null) return null;
  let dur = wake - bed;
  if (dur <= 0) dur += 24 * 60;
  return dur;
}

function formatSleepHours(mins: number): string {
  const h = mins / 60;
  if (Number.isInteger(h)) return `${h}h`;
  const rounded = Math.round(h * 10) / 10;
  return `${rounded}h`;
}

function formatClock(hm: string): string {
  const total = parseHm(hm);
  if (total == null) return hm;
  const h24 = Math.floor(total / 60);
  const min = total % 60;
  const am = h24 < 12;
  let h12 = h24 % 12;
  if (h12 === 0) h12 = 12;
  return `${h12}:${String(min).padStart(2, "0")} ${am ? "AM" : "PM"}`;
}

function subtractMinutesHm(hm: string, mins: number): string | null {
  const total = parseHm(hm);
  if (total == null) return null;
  let t = (total - mins) % (24 * 60);
  if (t < 0) t += 24 * 60;
  const h = Math.floor(t / 60);
  const m = t % 60;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
}

/**
 * Compact sleep / wake targets — Routines (fixed day anchors).
 * Rhythm strip (not a nested card): sleep length + bed/wake/Save.
 */
export function DayRhythmPanel() {
  const [bedtimeHm, setBedtimeHm] = useState("23:00");
  const [wakeHm, setWakeHm] = useState("06:30");
  const [hint, setHint] = useState<string | null>(null);
  const [hintOk, setHintOk] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    // Prefer shared status bus — avoid a second cold-start day.loop_snapshot on the pipe.
    const unsub = subscribeFocusStatus((snap) => {
      const loop = snap.dayLoop;
      if (!loop) return;
      if (loop.bedtime_hm) setBedtimeHm(loop.bedtime_hm);
      if (loop.wake_hm) setWakeHm(loop.wake_hm);
    });
    return unsub;
  }, []);

  const sleepMins = useMemo(() => sleepMinutes(bedtimeHm, wakeHm), [bedtimeHm, wakeHm]);
  const windDownHm = useMemo(
    () => subtractMinutesHm(bedtimeHm, WIND_DOWN_BEFORE_MIN),
    [bedtimeHm],
  );

  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 py-2 mt-1 border-t border-white/[0.07]">
      <div className="inline-flex items-center gap-1.5 shrink-0">
        <Moon size={13} className="text-sky-300/80" aria-hidden />
        <span className="text-[11px] font-medium text-foreground/90">Sleep</span>
        {sleepMins != null ? (
          <span className="text-[11px] font-mono tabular-nums text-sky-200/80">
            {formatSleepHours(sleepMins)}
          </span>
        ) : null}
        {windDownHm ? (
          <span className="text-[10px] text-muted-foreground/70 hidden sm:inline">
            · wind-down {formatClock(windDownHm)}
          </span>
        ) : null}
      </div>

      <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px] min-w-0">
        <label className="inline-flex items-center gap-1 text-muted-foreground">
          Bed
          <input
            type="time"
            className="rounded border border-white/10 bg-black/30 px-1 py-0.5 text-[11px] text-foreground"
            value={bedtimeHm}
            onChange={(e) => {
              setBedtimeHm(e.target.value);
              setHint(null);
            }}
          />
        </label>
        <label className="inline-flex items-center gap-1 text-muted-foreground">
          Wake
          <input
            type="time"
            className="rounded border border-white/10 bg-black/30 px-1 py-0.5 text-[11px] text-foreground"
            value={wakeHm}
            onChange={(e) => {
              setWakeHm(e.target.value);
              setHint(null);
            }}
          />
        </label>
        <button
          type="button"
          disabled={saving || sleepMins == null}
          className="rounded-md border border-white/10 bg-white/[0.06] hover:bg-white/10 px-2 py-0.5 text-[10px] font-medium text-foreground/90 disabled:opacity-50"
          onClick={() => {
            void (async () => {
              setSaving(true);
              const res = await setBedtime(bedtimeHm, wakeHm);
              setHintOk(res.ok);
              setHint(
                res.ok
                  ? `Saved · ${formatSleepHours(sleepMins!)} · bedtime blocks Focus sites + Armed apps`
                  : res.error === "enforcer_unreachable"
                    ? "Enforcer unreachable — open CALT Focus, then save again."
                    : "Could not save sleep.",
              );
              setSaving(false);
            })();
          }}
        >
          {saving ? "…" : "Save"}
        </button>
        {hint ? (
          <span
            className={
              hintOk
                ? "text-[10px] text-emerald-200/80 truncate"
                : "text-[10px] text-red-300/90 truncate"
            }
          >
            {hint}
          </span>
        ) : null}
      </div>
    </div>
  );
}

export default DayRhythmPanel;
