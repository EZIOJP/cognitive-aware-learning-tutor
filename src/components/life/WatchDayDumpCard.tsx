import { useMemo, useState } from "react";
import type { WearableDay } from "../../api/wearablesClient";
import { formatHoursMins } from "../../utils/formatDuration";
import { SleepCorrectForm } from "./SleepCorrectForm";

type Fallback = {
  last_steps?: number | null;
  last_sleep_hours?: number | null;
  last_calories?: number | null;
  last_distance_m?: number | null;
  last_hr?: number | null;
  last_spo2?: number | null;
  last_stress?: number | null;
  last_pai?: number | null;
  last_stand?: number | null;
  last_sitting_min?: number | null;
  last_battery?: number | null;
};

type SleepStage = {
  model?: number;
  start: number;
  stop: number;
  label: string;
};

type SleepInstant = {
  /** Absolute minutes on continuous timeline (origin = anchor midnight). */
  absMin: number;
  date: string;
  clock: string;
  label: string;
  at: string;
};

type SleepBlock = {
  score?: number | null;
  total_min?: number | null;
  deep_min?: number | null;
  start_min?: number | null;
  end_min?: number | null;
  start?: SleepInstant | null;
  end?: SleepInstant | null;
  windowLabel?: string | null;
  stages?: SleepStage[];
  naps?: Array<{ start?: number; stop?: number; length?: number }>;
};

const STAGE_COLORS: Record<string, string> = {
  wake: "#f59e0b",
  awake: "#f59e0b",
  light: "#60a5fa",
  rem: "#a78bfa",
  deep: "#312e81",
  asleep: "#38bdf8",
  stage: "#64748b",
};

const STAGE_ORDER = ["deep", "light", "rem", "wake"] as const;

/** Positive amount (durations, counts that should not render empty as 0). */
function presentNum(n: number | null | undefined): n is number {
  return typeof n === "number" && Number.isFinite(n) && n > 0;
}

/** Finite including 0 — Zepp empty cells stay null, never coerced. */
function isFiniteNum(n: unknown): n is number {
  return typeof n === "number" && Number.isFinite(n);
}

function asObj(v: unknown): Record<string, unknown> | null {
  return v && typeof v === "object" && !Array.isArray(v) ? (v as Record<string, unknown>) : null;
}

/** ZeppBridge AI daily columns — same order as pull_zeppbridge COLLECTOR_DAILY_KEYS. */
const ZEPP_DAILY_ROWS: { key: string; label: string; hint?: string; digits?: number }[] = [
  { key: "readiness", label: "Readiness" },
  { key: "hrv_readiness", label: "HRV readiness" },
  { key: "rhr_readiness", label: "RHR readiness" },
  { key: "hybrid_charge", label: "Hybrid charge" },
  { key: "physical_charge", label: "Physical charge" },
  { key: "mental_charge", label: "Mental charge" },
  { key: "sleep_hrv", label: "Sleep HRV", hint: "ms" },
  { key: "hrv_baseline", label: "HRV baseline", hint: "ms" },
  { key: "resting_hr", label: "Resting HR", hint: "bpm" },
  { key: "sleep_rhr", label: "Sleep RHR", hint: "bpm" },
  { key: "rhr_baseline", label: "RHR baseline", hint: "bpm" },
  { key: "stress", label: "Stress" },
  { key: "stress_min", label: "Stress min" },
  { key: "stress_max", label: "Stress max" },
  { key: "respiratory_rate", label: "Resp. rate", hint: "/min", digits: 1 },
  { key: "training_load", label: "Training load", digits: 1 },
  { key: "pai_daily", label: "PAI today", digits: 1 },
  { key: "pai_total", label: "PAI total", digits: 1 },
  { key: "steps", label: "Steps" },
  { key: "active_minutes", label: "Active min" },
  { key: "active_calories", label: "Active kcal" },
  { key: "calories", label: "Calories" },
  { key: "distance", label: "Distance", hint: "m" },
  { key: "spo2_night_score", label: "SpO₂ night" },
  { key: "device_max_hr", label: "Max HR", hint: "bpm" },
];

function collectorBlock(day: WearableDay | null | undefined): Record<string, unknown> | null {
  return asObj(asObj(day?.payload)?.collector);
}

function collectorDailyMap(day: WearableDay | null | undefined): Record<string, number | null> {
  const daily = asObj(collectorBlock(day)?.daily);
  if (!daily) return {};
  const out: Record<string, number | null> = {};
  for (const [k, v] of Object.entries(daily)) {
    if (v == null) out[k] = null;
    else if (isFiniteNum(Number(v))) out[k] = Number(v);
  }
  return out;
}

/** Prefer Zepp collector value; never treat FE zero-fill as real without steps_ok / presence. */
function pickZeppMetric(
  daily: Record<string, number | null>,
  key: string,
  fallback: number | null | undefined,
  opts?: { requireOk?: boolean; ok?: boolean | null | undefined },
): number | null {
  if (isFiniteNum(daily[key] as number | null | undefined)) return daily[key] as number;
  if (opts?.requireOk && !opts.ok) return null;
  if (isFiniteNum(fallback)) return fallback as number;
  return null;
}

function fmtZeppValue(n: number, digits?: number): string {
  if (digits != null) return (Math.round(n * 10 ** digits) / 10 ** digits).toLocaleString();
  if (Math.abs(n) >= 100 || Number.isInteger(n)) return Math.round(n).toLocaleString();
  return (Math.round(n * 10) / 10).toLocaleString();
}

function shiftDateKey(day: string, deltaDays: number): string {
  const [y, m, d] = day.slice(0, 10).split("-").map(Number);
  if (!y || !m || !d) return day.slice(0, 10);
  const dt = new Date(y, m - 1, d);
  dt.setDate(dt.getDate() + deltaDays);
  return `${dt.getFullYear()}-${String(dt.getMonth() + 1).padStart(2, "0")}-${String(dt.getDate()).padStart(2, "0")}`;
}

function fmtMinutesClock(minOfDay: number): string {
  const m = ((Math.round(minOfDay) % 1440) + 1440) % 1440;
  const h = Math.floor(m / 60);
  const mm = m % 60;
  return `${String(h).padStart(2, "0")}:${String(mm).padStart(2, "0")}`;
}

function fmtShortDate(day: string): string {
  const [y, m, d] = day.slice(0, 10).split("-").map(Number);
  if (!y || !m || !d) return day.slice(0, 10);
  return new Date(y, m - 1, d).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

/** Map Zepp minute timeline → calendar clock. local_date is the dump/wake day. */
function resolveSleepInstant(localDate: string, timelineMin: number, endTimelineMin: number | null): SleepInstant {
  const raw = Math.round(timelineMin);
  const end = endTimelineMin != null && Number.isFinite(endTimelineMin) ? Math.round(endTimelineMin) : raw;
  let originShift = 0;
  if (end >= 1440 || raw >= 1440) {
    // Continuous timeline (stages often 1700–2300): origin is midnight of (local_date - floor(end/1440)).
    originShift = -Math.floor(Math.max(end, raw) / 1440);
  } else if (endTimelineMin != null && Number.isFinite(endTimelineMin) && raw > end && end >= 0) {
    // Classic overnight wrap inside 0–1439 (e.g. 1380→360): bedtime previous calendar day.
    originShift = -1;
  }
  const absFromLocal = raw + originShift * 1440;
  const dayOffset = Math.floor(absFromLocal / 1440);
  const clockMin = ((absFromLocal % 1440) + 1440) % 1440;
  const date = shiftDateKey(localDate, dayOffset);
  const clock = fmtMinutesClock(clockMin);
  const sameAsLocal = date === localDate.slice(0, 10);
  const label = sameAsLocal ? clock : `${fmtShortDate(date)} ${clock}`;
  const at = `${date}T${clock}:00`;
  return { absMin: raw, date, clock, label, at };
}

function validSleepBound(n: number | null | undefined): n is number {
  return typeof n === "number" && Number.isFinite(n) && n >= 0;
}

function fmtDuration(totalMin: number): string {
  return formatHoursMins(totalMin);
}

function fmtSitting(min: number): string {
  return formatHoursMins(min);
}

function normalizeLabel(raw: string | undefined): string {
  const s = String(raw || "stage").toLowerCase();
  if (s === "awake") return "wake";
  return s;
}

/** Unwrap overnight wrap (stop < start within a day) onto a continuous axis for the hypnogram. */
function unwrapStage(start: number, stop: number): { start: number; stop: number } | null {
  if (!Number.isFinite(start) || !Number.isFinite(stop)) return null;
  if (stop < 0 || start < 0) return null;
  if (stop > start) return { start, stop };
  // Overnight wrap inside one day (e.g. 1380→360).
  if (start < 1440 && stop < 1440 && stop < start) return { start, stop: stop + 1440 };
  return null;
}

function parseSleep(payload: Record<string, unknown> | null | undefined, day: WearableDay | null | undefined): SleepBlock {
  const sleep = asObj(payload?.sleep) || asObj(day?.sleep as unknown) || {};
  const localDate =
    (typeof day?.local_date === "string" && day.local_date.slice(0, 10)) ||
    (typeof sleep.local_date === "string" ? String(sleep.local_date).slice(0, 10) : "") ||
    new Date().toISOString().slice(0, 10);

  const stagesRaw = Array.isArray(sleep.stages) ? sleep.stages : [];
  let stages: SleepStage[] = stagesRaw
    .map((s) => {
      const row = asObj(s);
      if (!row) return null;
      const unwrapped = unwrapStage(Number(row.start), Number(row.stop));
      if (!unwrapped) return null;
      return {
        model: typeof row.model === "number" ? row.model : undefined,
        start: unwrapped.start,
        stop: unwrapped.stop,
        label: normalizeLabel(typeof row.label === "string" ? row.label : undefined),
      };
    })
    .filter((s): s is SleepStage => !!s);

  const startRaw = Number(sleep.start_min);
  const endRaw = Number(sleep.end_min);
  const start_min = validSleepBound(startRaw) ? startRaw : null;
  const end_min = validSleepBound(endRaw) ? endRaw : null;

  // Prefer host-stamped ISO if present.
  const stampedStart =
    typeof sleep.start_at === "string" && sleep.start_at.length >= 16
      ? String(sleep.start_at)
      : typeof day?.sleep_start_at === "string"
        ? day.sleep_start_at
        : null;
  const stampedEnd =
    typeof sleep.end_at === "string" && sleep.end_at.length >= 16
      ? String(sleep.end_at)
      : typeof day?.sleep_end_at === "string"
        ? day.sleep_end_at
        : null;

  let start: SleepInstant | null = null;
  let end: SleepInstant | null = null;
  if (start_min != null && end_min != null) {
    start = resolveSleepInstant(localDate, start_min, end_min);
    end = resolveSleepInstant(localDate, end_min, end_min);
    if (stampedStart && stampedStart.length >= 16) {
      const date = stampedStart.slice(0, 10);
      const clock = stampedStart.slice(11, 16);
      start = {
        ...start,
        date,
        clock,
        at: stampedStart.slice(0, 19),
        label: date === localDate ? clock : `${fmtShortDate(date)} ${clock}`,
      };
    }
    if (stampedEnd && stampedEnd.length >= 16) {
      const date = stampedEnd.slice(0, 10);
      const clock = stampedEnd.slice(11, 16);
      end = {
        ...end,
        date,
        clock,
        at: stampedEnd.slice(0, 19),
        label: date === localDate ? clock : `${fmtShortDate(date)} ${clock}`,
      };
    }
  }

  // No stage samples — still draw a time-based sleep bar from start/end.
  if (!stages.length && start_min != null && end_min != null) {
    const unwrapped = unwrapStage(start_min, end_min);
    if (unwrapped) {
      stages = [{ start: unwrapped.start, stop: unwrapped.stop, label: "asleep" }];
    } else if (end_min > start_min) {
      stages = [{ start: start_min, stop: end_min, label: "asleep" }];
    }
  }

  const totalFromStages = stages.reduce((a, s) => a + (s.stop - s.start), 0);
  const total_min =
    presentNum(Number(sleep.total_min))
      ? Number(sleep.total_min)
      : presentNum(day?.sleep_hours)
        ? Math.round(Number(day?.sleep_hours) * 60)
        : totalFromStages > 0
          ? totalFromStages
          : null;

  const windowLabel =
    start && end
      ? start.date === end.date
        ? `${start.clock}–${end.clock}`
        : `${start.label} → ${end.label}`
      : null;

  return {
    score: presentNum(Number(sleep.score)) ? Number(sleep.score) : presentNum(day?.sleep_score) ? Number(day?.sleep_score) : null,
    total_min,
    deep_min: presentNum(Number(sleep.deep_min))
      ? Number(sleep.deep_min)
      : presentNum(day?.sleep_deep_min)
        ? Number(day?.sleep_deep_min)
        : null,
    start_min,
    end_min,
    start,
    end,
    windowLabel,
    stages,
    naps: Array.isArray(sleep.naps) ? (sleep.naps as SleepBlock["naps"]) : [],
  };
}

function SleepHypnogram({
  stages,
  localDate,
  endMin,
}: {
  stages: SleepStage[];
  localDate: string;
  endMin: number | null;
}) {
  if (!stages.length) return null;
  const t0 = Math.min(...stages.map((s) => s.start));
  const t1 = Math.max(...stages.map((s) => s.stop));
  const span = Math.max(1, t1 - t0);
  const startInst = resolveSleepInstant(localDate, t0, endMin ?? t1);
  const endInst = resolveSleepInstant(localDate, t1, endMin ?? t1);

  return (
    <div className="space-y-1.5">
      <div className="flex h-10 w-full overflow-hidden rounded-lg border border-white/10 bg-black/30">
        {stages.map((s, i) => {
          const w = ((s.stop - s.start) / span) * 100;
          const color = STAGE_COLORS[s.label] || STAGE_COLORS.stage;
          const a = resolveSleepInstant(localDate, s.start, endMin ?? t1);
          const b = resolveSleepInstant(localDate, s.stop, endMin ?? t1);
          return (
            <div
              key={`${s.start}-${s.stop}-${i}`}
              title={`${s.label} · ${a.label}–${b.label} (${formatHoursMins(s.stop - s.start)})`}
              style={{ width: `${w}%`, background: color }}
              className="h-full min-w-[1px]"
            />
          );
        })}
      </div>
      <div className="flex justify-between text-[10px] tabular-nums text-muted-foreground">
        <span>{startInst.label}</span>
        <span>{endInst.label}</span>
      </div>
    </div>
  );
}

type HeartBlock = {
  last: number | null;
  resting: number | null;
  avg: number | null;
  max: number | null;
  series: number[];
};

function sampleSeriesFromCollector(
  collector: Record<string, unknown> | null,
  metric: string,
  opts?: { min?: number; max?: number },
): number[] {
  const samples = asObj(collector?.samples);
  const raw = samples?.[metric];
  if (!Array.isArray(raw)) return [];
  const lo = opts?.min ?? 0;
  const hi = opts?.max ?? 1e9;
  return raw
    .map((pt) => {
      const o = asObj(pt);
      return o ? Number(o.v) : Number(pt);
    })
    .filter((n) => Number.isFinite(n) && n >= lo && n <= hi);
}

function seriesStats(series: number[]): { last: number; min: number; max: number; avg: number } | null {
  if (series.length < 1) return null;
  const last = series[series.length - 1];
  const min = Math.min(...series);
  const max = Math.max(...series);
  const avg = series.reduce((a, b) => a + b, 0) / series.length;
  return { last, min, max, avg };
}

function parseHeart(payload: Record<string, unknown> | null | undefined, day: WearableDay | null | undefined): HeartBlock {
  const heart = asObj(payload?.heart) || {};
  const rawSeries = Array.isArray(heart.today_min) ? heart.today_min : [];
  let series = rawSeries
    .map((n) => Number(n))
    .filter((n) => Number.isFinite(n) && n > 0 && n < 250);
  if (series.length < 2) {
    const fromCollector = sampleSeriesFromCollector(collectorBlock(day), "heart_rate");
    if (fromCollector.length > series.length) series = fromCollector;
  }

  const fromSeriesAvg =
    series.length > 0 ? Math.round(series.reduce((a, b) => a + b, 0) / series.length) : null;
  const fromSeriesMax = series.length > 0 ? Math.max(...series) : null;

  return {
    last: presentNum(day?.hr_last)
      ? Number(day?.hr_last)
      : presentNum(Number(heart.last))
        ? Number(heart.last)
        : null,
    resting: presentNum(day?.hr_resting)
      ? Number(day?.hr_resting)
      : presentNum(Number(heart.resting))
        ? Number(heart.resting)
        : null,
    avg: presentNum(day?.hr_avg)
      ? Number(day?.hr_avg)
      : presentNum(Number(heart.avg))
        ? Number(heart.avg)
        : fromSeriesAvg,
    max: presentNum(day?.hr_max)
      ? Number(day?.hr_max)
      : presentNum(Number(heart.max))
        ? Number(heart.max)
        : fromSeriesMax,
    series,
  };
}

function hrZoneColor(bpm: number): string {
  if (bpm < 60) return "#38bdf8";
  if (bpm < 100) return "#34d399";
  if (bpm < 140) return "#fbbf24";
  return "#f87171";
}

function VitalSparkline({
  label,
  unit,
  series,
  accent = "rose",
  valueColor,
  digits = 0,
}: {
  label: string;
  unit: string;
  series: number[];
  accent?: "rose" | "violet" | "amber" | "sky";
  valueColor?: (v: number) => string;
  digits?: number;
}) {
  if (series.length < 2) return null;
  const stats = seriesStats(series);
  if (!stats) return null;
  const w = 320;
  const h = 64;
  const padY = 8;
  const pad = Math.max(1, (stats.max - stats.min) * 0.08);
  const lo = stats.min - pad;
  const hi = stats.max + pad;
  const span = Math.max(1e-6, hi - lo);
  const pts = series.map((v, i) => {
    const x = (i / (series.length - 1)) * w;
    const y = padY + (1 - (v - lo) / span) * (h - padY * 2);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });
  const avgY = padY + (1 - (stats.avg - lo) / span) * (h - padY * 2);
  const strokeId = `vital-${label.replace(/\s+/g, "-").toLowerCase()}`;
  const tone =
    accent === "violet"
      ? { border: "border-violet-400/25", bg: "bg-violet-500/5", ink: "text-violet-200/85", a: "#a78bfa", b: "#8b5cf6" }
      : accent === "amber"
        ? { border: "border-amber-400/25", bg: "bg-amber-500/5", ink: "text-amber-200/85", a: "#fbbf24", b: "#f59e0b" }
        : accent === "sky"
          ? { border: "border-sky-400/25", bg: "bg-sky-500/5", ink: "text-sky-200/85", a: "#38bdf8", b: "#0ea5e9" }
          : { border: "border-rose-400/20", bg: "bg-rose-500/5", ink: "text-rose-200/80", a: "#fb7185", b: "#f43f5e" };
  const fmt = (n: number) => (digits > 0 ? n.toFixed(digits) : String(Math.round(n)));

  return (
    <div className={`space-y-1.5 rounded-xl border ${tone.border} ${tone.bg} p-3`}>
      <div className="flex items-baseline justify-between gap-2">
        <div>
          <p className={`text-[10px] uppercase tracking-wide ${tone.ink}`}>{label}</p>
          <p
            className="text-lg font-semibold tabular-nums leading-tight"
            style={{ color: valueColor?.(stats.last) }}
          >
            {fmt(stats.last)}{" "}
            <span className="text-xs font-normal text-muted-foreground">{unit}</span>
          </p>
        </div>
        <p className="text-[11px] tabular-nums text-muted-foreground text-right">
          {series.length} pts · {fmt(stats.min)}–{fmt(stats.max)}
          <span className="block opacity-80">avg {fmt(stats.avg)}</span>
        </p>
      </div>
      <svg
        viewBox={`0 0 ${w} ${h}`}
        className="h-14 w-full"
        preserveAspectRatio="none"
        role="img"
        aria-label={`${label} sparkline`}
      >
        <line
          x1={0}
          x2={w}
          y1={avgY}
          y2={avgY}
          stroke={tone.a}
          strokeOpacity={0.35}
          strokeWidth={1}
          strokeDasharray="4 3"
        />
        <polyline
          fill="none"
          stroke={`url(#${strokeId})`}
          strokeWidth={2}
          strokeLinejoin="round"
          strokeLinecap="round"
          points={pts.join(" ")}
        />
        <defs>
          <linearGradient id={strokeId} x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor={tone.a} />
            <stop offset="100%" stopColor={tone.b} />
          </linearGradient>
        </defs>
      </svg>
      <div className="flex justify-between text-[10px] tabular-nums text-muted-foreground">
        <span>00:00</span>
        <span>24:00</span>
      </div>
    </div>
  );
}

function HeartSparkline({ series, avg }: { series: number[]; avg: number | null }) {
  void avg;
  return (
    <VitalSparkline label="Heart rate" unit="bpm" series={series} accent="rose" valueColor={hrZoneColor} />
  );
}

function HeartVitals({ heart }: { heart: HeartBlock }) {
  const tiles: Array<{ label: string; value: number; hint?: string }> = [];
  if (presentNum(heart.last)) tiles.push({ label: "Last", value: heart.last, hint: "bpm" });
  if (presentNum(heart.resting)) tiles.push({ label: "Resting", value: heart.resting, hint: "bpm" });
  if (presentNum(heart.avg)) tiles.push({ label: "Avg", value: heart.avg, hint: "today" });
  if (presentNum(heart.max)) tiles.push({ label: "Max", value: heart.max, hint: "today" });
  if (!tiles.length) return null;

  const gaugeMax = Math.max(120, ...(tiles.map((t) => t.value)), heart.max || 0);
  const barW = (v: number) => `${Math.min(100, Math.round((v / gaugeMax) * 100))}%`;

  return (
    <div className="space-y-2">
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        {tiles.map((t) => (
          <div key={t.label} className="rounded-xl border border-rose-400/20 bg-rose-500/5 px-3 py-2.5">
            <p className="text-[10px] uppercase tracking-wide text-muted-foreground">{t.label}</p>
            <p className="mt-0.5 text-lg font-semibold tabular-nums leading-tight" style={{ color: hrZoneColor(t.value) }}>
              {t.value}
            </p>
            {t.hint ? <p className="mt-0.5 text-[11px] text-muted-foreground">{t.hint}</p> : null}
            <div className="mt-2 h-1 overflow-hidden rounded-full bg-black/25">
              <div className="h-full rounded-full" style={{ width: barW(t.value), background: hrZoneColor(t.value) }} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function stageTotals(stages: SleepStage[], deepFallback: number | null) {
  const totals: Record<string, number> = { deep: 0, light: 0, rem: 0, wake: 0 };
  for (const s of stages) {
    const key = normalizeLabel(s.label);
    if (key in totals) totals[key] += s.stop - s.start;
  }
  if (totals.deep <= 0 && presentNum(deepFallback)) totals.deep = deepFallback;
  return totals;
}

export function WatchDayDumpCard({
  day,
  fallback,
  emptyHint = "No watch dump for this day — Sync from watch.",
  includeRaw = true,
  localDate,
  onSleepCorrected,
}: {
  day: WearableDay | null | undefined;
  fallback?: Fallback | null;
  emptyHint?: string;
  includeRaw?: boolean;
  localDate?: string;
  onSleepCorrected?: () => void;
}) {
  const [showRaw, setShowRaw] = useState(false);
  const [showAllZepp, setShowAllZepp] = useState(true);
  const fb = fallback || {};
  const payload = (day?.payload as Record<string, unknown> | null | undefined) || null;
  const collector = useMemo(() => collectorBlock(day), [day]);
  const daily = useMemo(() => collectorDailyMap(day), [day]);
  const coverage = asObj(collector?.coverage);

  const sleep = useMemo(() => parseSleep(payload, day ?? null), [payload, day]);
  const heart = useMemo(() => parseHeart(payload, day ?? null), [payload, day]);
  const hrSeries = heart.series;
  const hrvSeries = useMemo(
    () => {
      const rmssd = sampleSeriesFromCollector(collector, "hrv_rmssd", { min: 1, max: 400 });
      if (rmssd.length >= 2) return rmssd;
      return sampleSeriesFromCollector(collector, "hrv", { min: 1, max: 400 });
    },
    [collector],
  );
  const stressSeries = useMemo(
    () => sampleSeriesFromCollector(collector, "stress", { min: 0, max: 100 }),
    [collector],
  );
  const spo2Series = useMemo(
    () => sampleSeriesFromCollector(collector, "spo2", { min: 70, max: 100 }),
    [collector],
  );

  const activity = asObj(payload?.activity) || {};
  const calorie = asObj(payload?.calorie) || {};
  const distance = asObj(payload?.distance) || {};
  const quality = day?.data_quality || null;

  const steps = pickZeppMetric(daily, "steps", null, {
    requireOk: true,
    ok: quality?.steps_ok === true || isFiniteNum(daily.steps),
  });
  const stepTarget = presentNum(day?.step_target)
    ? Number(day?.step_target)
    : presentNum(Number(activity.target))
      ? Number(activity.target)
      : null;
  const kcal = pickZeppMetric(
    daily,
    "active_calories",
    pickZeppMetric(daily, "calories", presentNum(day?.calories) ? Number(day?.calories) : presentNum(Number(calorie.kcal)) ? Number(calorie.kcal) : null),
  );
  const kcalTarget = presentNum(day?.calorie_target)
    ? Number(day?.calorie_target)
    : presentNum(Number(calorie.target))
      ? Number(calorie.target)
      : null;
  const distM = pickZeppMetric(
    daily,
    "distance",
    presentNum(day?.distance_m)
      ? Number(day?.distance_m)
      : presentNum(Number(distance.meters))
        ? Number(distance.meters)
        : null,
  );

  const hr =
    pickZeppMetric(daily, "resting_hr", null) ??
    pickZeppMetric(daily, "sleep_rhr", null) ??
    (presentNum(heart.last) ? heart.last : presentNum(fb.last_hr) ? Number(fb.last_hr) : null);
  const spo2 = pickZeppMetric(
    daily,
    "spo2_night_score",
    presentNum(day?.spo2) ? Number(day?.spo2) : presentNum(fb.last_spo2) ? Number(fb.last_spo2) : null,
  );
  const stress = pickZeppMetric(
    daily,
    "stress",
    quality?.steps_ok === false && !isFiniteNum(daily.stress) && day?.stress === 0
      ? null
      : isFiniteNum(day?.stress) && (isFiniteNum(daily.stress) || (day?.stress ?? 0) > 0)
        ? Number(day?.stress)
        : presentNum(fb.last_stress)
          ? Number(fb.last_stress)
          : null,
  );
  const readiness = pickZeppMetric(daily, "readiness", day?.readiness);
  const trainingLoad = pickZeppMetric(daily, "training_load", day?.training_load);
  const sleepHrv = pickZeppMetric(daily, "sleep_hrv", day?.sleep_hrv);
  const physicalCharge = pickZeppMetric(daily, "physical_charge", day?.physical_charge);
  const hybridCharge = pickZeppMetric(daily, "hybrid_charge", day?.hybrid_charge);
  const mentalCharge = pickZeppMetric(daily, "mental_charge", day?.mental_charge);
  const pai = pickZeppMetric(
    daily,
    "pai_daily",
    presentNum(day?.pai_today) ? Number(day?.pai_today) : presentNum(fb.last_pai) ? Number(fb.last_pai) : null,
  );
  const stand = presentNum(day?.stand_hours) ? Number(day?.stand_hours) : presentNum(fb.last_stand) ? Number(fb.last_stand) : null;
  const sitting = presentNum(day?.sitting_min)
    ? Number(day?.sitting_min)
    : presentNum(fb.last_sitting_min)
      ? Number(fb.last_sitting_min)
      : null;
  const battery = presentNum(day?.battery_pct)
    ? Number(day?.battery_pct)
    : presentNum(fb.last_battery)
      ? Number(fb.last_battery)
      : null;

  const workouts = useMemo(() => {
    const raw = collector?.workouts ?? asObj(payload)?.workouts;
    return Array.isArray(raw) ? raw : [];
  }, [collector, payload]);

  const zeppRows = useMemo(() => {
    return ZEPP_DAILY_ROWS.map((row) => {
      const v = daily[row.key];
      if (!isFiniteNum(v)) return null;
      return { ...row, value: v as number };
    }).filter(Boolean) as Array<(typeof ZEPP_DAILY_ROWS)[number] & { value: number }>;
  }, [daily]);

  const hasSleep = presentNum(sleep.total_min) || presentNum(sleep.score) || (sleep.stages && sleep.stages.length > 0);
  const hasMove = isFiniteNum(steps) || isFiniteNum(kcal) || isFiniteNum(distM);
  const hasHeart =
    isFiniteNum(hr) ||
    presentNum(heart.resting) ||
    presentNum(heart.avg) ||
    presentNum(heart.max) ||
    hrSeries.length > 0;
  const hasVitalSeries =
    hrSeries.length > 1 || hrvSeries.length > 1 || stressSeries.length > 1 || spo2Series.length > 1;
  const hasCollector = zeppRows.length > 0;
  const hasExtras =
    isFiniteNum(spo2) ||
    isFiniteNum(stress) ||
    isFiniteNum(pai) ||
    presentNum(stand) ||
    presentNum(sitting) ||
    presentNum(battery) ||
    hasCollector ||
    workouts.length > 0;
  const hasAnything = hasSleep || hasMove || hasHeart || hasExtras || !!day?.local_date;

  const qualityNotes: string[] = [];
  if (hasSleep && !sleep.windowLabel) qualityNotes.push("Sleep time not dated — Dump & Send again");
  if (hasSleep && (sleep.stages?.length ?? 0) <= 1 && !(quality?.sleep_stages && quality.sleep_stages > 1))
    qualityNotes.push("Sleep stages thin — use full Dump on watch");
  if (hasHeart && heart.series.length < 2) qualityNotes.push("HR series missing — pull again after ZeppBridge syncs samples");
  if (quality && quality.sleep_ok === false && hasMove) qualityNotes.push("Sleep incomplete for this day");
  if (hasSleep && !hasCollector && !hasVitalSeries)
    qualityNotes.push("Recovery / HR samples not in ZeppBridge yet for this day — sleep only so far");

  const dayKey =
    (typeof localDate === "string" && localDate.slice(0, 10)) ||
    (typeof day?.local_date === "string" && day.local_date.slice(0, 10)) ||
    new Date().toISOString().slice(0, 10);

  if (!hasAnything && fb.last_sleep_hours == null && fb.last_steps == null) {
    return (
      <div className="space-y-3">
        <p className="text-sm text-muted-foreground">{emptyHint}</p>
        <SleepCorrectForm day={day} localDate={dayKey} onSaved={onSleepCorrected} />
      </div>
    );
  }

  const totals = stageTotals(sleep.stages || [], sleep.deep_min ?? null);
  const stageSum = STAGE_ORDER.reduce((a, k) => a + (totals[k] || 0), 0);
  const stepPct =
    isFiniteNum(steps) && presentNum(stepTarget)
      ? Math.round(Math.min(100, (steps / stepTarget) * 100))
      : null;

  const metrics: Array<{ key: string; label: string; value: string; hint?: string; accent?: string }> = [];
  if (presentNum(sleep.score)) {
    metrics.push({ key: "score", label: "Sleep score", value: String(sleep.score), accent: "sky" });
  }
  if (presentNum(sleep.total_min)) {
    metrics.push({
      key: "duration",
      label: "Asleep",
      value: fmtDuration(sleep.total_min),
      hint: sleep.windowLabel || undefined,
    });
  }
  if (isFiniteNum(steps)) {
    metrics.push({
      key: "steps",
      label: "Steps",
      value: Math.round(steps).toLocaleString(),
      hint: presentNum(stepTarget) ? `of ${stepTarget.toLocaleString()}` : undefined,
      accent: "emerald",
    });
  }
  if (isFiniteNum(kcal)) {
    metrics.push({
      key: "kcal",
      label: "Calories",
      value: `${Math.round(kcal).toLocaleString()}`,
      hint: presentNum(kcalTarget) ? `of ${kcalTarget.toLocaleString()}` : "kcal",
    });
  }
  if (isFiniteNum(distM)) {
    metrics.push({
      key: "dist",
      label: "Distance",
      value: `${(distM / 1000).toFixed(2)}`,
      hint: "km",
    });
  }
  if (isFiniteNum(hr)) {
    metrics.push({
      key: "hr",
      label: "Resting HR",
      value: String(Math.round(hr)),
      hint: "bpm",
      accent: "rose",
    });
  }
  if (isFiniteNum(readiness)) {
    metrics.push({
      key: "readiness",
      label: "Readiness",
      value: String(Math.round(readiness)),
      hint: "Zepp",
      accent: "sky",
    });
  }
  if (isFiniteNum(sleepHrv)) {
    metrics.push({
      key: "sleep_hrv",
      label: "Sleep HRV",
      value: String(Math.round(sleepHrv)),
      hint: "ms",
    });
  }
  if (isFiniteNum(hybridCharge)) {
    metrics.push({
      key: "hybrid",
      label: "Hybrid",
      value: String(Math.round(hybridCharge)),
      hint: "charge",
    });
  }
  if (isFiniteNum(physicalCharge)) {
    metrics.push({
      key: "physical",
      label: "Physical",
      value: String(Math.round(physicalCharge)),
      hint: "charge",
      accent: "emerald",
    });
  }
  if (isFiniteNum(mentalCharge)) {
    metrics.push({
      key: "mental",
      label: "Mental",
      value: String(Math.round(mentalCharge)),
      hint: "charge",
    });
  }
  if (isFiniteNum(trainingLoad)) {
    metrics.push({
      key: "training",
      label: "Training load",
      value: String(Math.round(trainingLoad * 10) / 10),
    });
  }
  if (isFiniteNum(stress)) {
    const sMin = pickZeppMetric(daily, "stress_min", day?.stress_min);
    const sMax = pickZeppMetric(daily, "stress_max", day?.stress_max);
    metrics.push({
      key: "stress",
      label: "Stress",
      value: String(Math.round(stress)),
      hint: isFiniteNum(sMin) || isFiniteNum(sMax) ? `${sMin ?? "—"}–${sMax ?? "—"}` : undefined,
    });
  }

  return (
    <div className="space-y-4">
      {qualityNotes.length > 0 ? (
        <div className="rounded-lg border border-amber-400/25 bg-amber-500/10 px-3 py-2 text-[11px] text-amber-100/90 space-y-0.5">
          {qualityNotes.map((n) => (
            <p key={n}>{n}</p>
          ))}
        </div>
      ) : hasSleep && sleep.windowLabel && (heart.series.length > 1 || presentNum(hr)) ? (
        <p className="text-[11px] text-emerald-200/80">Watch data looks complete for this day</p>
      ) : null}
      {metrics.length > 0 ? (
        <div className="watch-insight-strip grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5">
          {metrics.map((m) => (
            <div
              key={m.key}
              className={`rounded-xl border border-border/40 bg-background/25 px-3 py-2.5 ${
                m.accent === "sky"
                  ? "border-sky-400/25 bg-sky-500/5"
                  : m.accent === "emerald"
                    ? "border-emerald-400/25 bg-emerald-500/5"
                    : m.accent === "rose"
                      ? "border-rose-400/25 bg-rose-500/5"
                      : ""
              }`}
            >
              <p className="text-[10px] uppercase tracking-wide text-muted-foreground">{m.label}</p>
              <p className="mt-0.5 text-lg font-semibold tabular-nums leading-tight">{m.value}</p>
              {m.hint ? <p className="mt-0.5 text-[11px] text-muted-foreground tabular-nums">{m.hint}</p> : null}
            </div>
          ))}
        </div>
      ) : null}

      {hasHeart || hasVitalSeries ? (
        <div className="space-y-3">
          <div className="flex items-baseline justify-between gap-2">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
                Vitals
              </p>
              <p className="text-[11px] text-muted-foreground">
                ZeppBridge samples · HR · HRV · Stress · SpO₂
              </p>
            </div>
          </div>
          <div className="grid gap-2 sm:grid-cols-2">
            {hrSeries.length > 1 ? (
              <HeartSparkline series={hrSeries} avg={heart.avg} />
            ) : null}
            {hrvSeries.length > 1 ? (
              <VitalSparkline label="HRV (RMSSD)" unit="ms" series={hrvSeries} accent="violet" />
            ) : null}
            {stressSeries.length > 1 ? (
              <VitalSparkline label="Stress" unit="" series={stressSeries} accent="amber" />
            ) : null}
            {spo2Series.length > 1 ? (
              <VitalSparkline label="SpO₂" unit="%" series={spo2Series} accent="sky" />
            ) : null}
          </div>
          {hasHeart ? <HeartVitals heart={{ ...heart, last: hr }} /> : null}
          {!hasVitalSeries ? (
            <p className="text-[11px] text-muted-foreground">
              No HR / HRV / stress / SpO₂ samples for this day yet — pull after ZeppBridge syncs.
            </p>
          ) : null}
        </div>
      ) : null}

      {(sleep.stages?.length ?? 0) > 0 ? (
        <div className="space-y-2">
          {sleep.windowLabel ? (
            <p className="text-xs tabular-nums text-sky-100/90">
              Sleep window · {sleep.windowLabel}
              {sleep.start?.date && sleep.end?.date && sleep.start.date !== sleep.end.date
                ? ` · ${fmtShortDate(sleep.start.date)} → ${fmtShortDate(sleep.end.date)}`
                : sleep.start?.date
                  ? ` · ${fmtShortDate(sleep.start.date)}`
                  : ""}
            </p>
          ) : null}
          <SleepHypnogram
            stages={sleep.stages!}
            localDate={
              (typeof day?.local_date === "string" && day.local_date.slice(0, 10)) ||
              new Date().toISOString().slice(0, 10)
            }
            endMin={sleep.end_min ?? null}
          />
          {stageSum > 0 ? (
            <div className="flex flex-wrap gap-2">
              {STAGE_ORDER.map((key) => {
                const mins = totals[key] || 0;
                if (mins <= 0) return null;
                const pct = Math.round((mins / stageSum) * 100);
                return (
                  <span
                    key={key}
                    className="inline-flex items-center gap-1.5 rounded-full border border-border/40 bg-background/20 px-2.5 py-1 text-[11px] tabular-nums"
                  >
                    <span className="h-2 w-2 rounded-full" style={{ background: STAGE_COLORS[key] }} />
                    <span className="capitalize text-muted-foreground">{key}</span>
                    <span className="font-medium">{fmtDuration(mins)}</span>
                    <span className="text-muted-foreground">{pct}%</span>
                  </span>
                );
              })}
              {stepPct != null ? (
                <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-400/25 bg-emerald-500/10 px-2.5 py-1 text-[11px] tabular-nums text-emerald-200">
                  Move {stepPct}% of step target
                </span>
              ) : null}
            </div>
          ) : null}
        </div>
      ) : presentNum(sleep.deep_min) || stepPct != null ? (
        <div className="flex flex-wrap gap-2">
          {presentNum(sleep.deep_min) ? (
            <span className="inline-flex items-center gap-1.5 rounded-full border border-border/40 bg-background/20 px-2.5 py-1 text-[11px] tabular-nums">
              Deep {fmtDuration(sleep.deep_min)}
            </span>
          ) : null}
          {stepPct != null ? (
            <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-400/25 bg-emerald-500/10 px-2.5 py-1 text-[11px] tabular-nums text-emerald-200">
              Move {stepPct}% of step target
            </span>
          ) : null}
        </div>
      ) : null}

      {hasExtras ? (
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground tabular-nums border-t border-border/30 pt-3">
          {isFiniteNum(spo2) ? <span>SpO₂ {Math.round(spo2)}</span> : null}
          {isFiniteNum(pai) ? <span>PAI {fmtZeppValue(pai, 1)}</span> : null}
          {presentNum(stand) ? (
            <span>
              Stand {stand}
              {presentNum(day?.stand_target) ? ` / ${day?.stand_target}` : ""}h
            </span>
          ) : null}
          {presentNum(sitting) ? <span>Sitting {fmtSitting(sitting)}</span> : null}
          {presentNum(battery) ? <span>Battery {battery}%</span> : null}
        </div>
      ) : null}

      {hasCollector ? (
        <div className="space-y-2 border-t border-border/30 pt-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
                Zepp daily
              </p>
              <p className="text-[11px] text-muted-foreground">
                From ZeppBridge · null cells stay empty (not zero)
              </p>
            </div>
            <button
              type="button"
              className="text-[11px] text-muted-foreground underline-offset-2 hover:underline"
              onClick={() => setShowAllZepp((v) => !v)}
            >
              {showAllZepp ? "Collapse" : "Show all"}
            </button>
          </div>
          {coverage ? (
            <div className="flex flex-wrap gap-1.5">
              {(
                [
                  ["sleep", "Sleep"],
                  ["recovery", "Recovery"],
                  ["resting_hr", "RHR"],
                  ["heart_rate", "HR"],
                  ["training", "Training"],
                ] as const
              ).map(([k, label]) => {
                const on = coverage[k] === true;
                return (
                  <span
                    key={k}
                    className={`rounded-full border px-2 py-0.5 text-[10px] tabular-nums ${
                      on
                        ? "border-emerald-400/30 bg-emerald-500/10 text-emerald-100/90"
                        : "border-border/40 bg-background/20 text-muted-foreground"
                    }`}
                  >
                    {label}
                  </span>
                );
              })}
            </div>
          ) : null}
          {showAllZepp ? (
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">
              {zeppRows.map((row) => (
                <div
                  key={row.key}
                  className="rounded-xl border border-border/35 bg-background/20 px-2.5 py-2"
                >
                  <p className="text-[10px] uppercase tracking-wide text-muted-foreground">{row.label}</p>
                  <p className="mt-0.5 text-[15px] font-semibold tabular-nums leading-tight">
                    {fmtZeppValue(row.value, row.digits)}
                    {row.hint ? (
                      <span className="ml-1 text-[10px] font-normal text-muted-foreground">{row.hint}</span>
                    ) : null}
                  </p>
                </div>
              ))}
            </div>
          ) : null}
        </div>
      ) : null}

      {workouts.length > 0 ? (
        <div className="space-y-2 border-t border-border/30 pt-3">
          <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
            Workouts
          </p>
          <ul className="space-y-1.5">
            {workouts.map((w, i) => {
              const o = asObj(w) || {};
              const type = String(o.type || o.workout_type || "Workout");
              const dur = isFiniteNum(Number(o.duration_min)) ? Number(o.duration_min) : null;
              const cal = isFiniteNum(Number(o.calories)) ? Number(o.calories) : null;
              const avgHr = isFiniteNum(Number(o.avg_hr)) ? Number(o.avg_hr) : null;
              return (
                <li
                  key={`${type}-${i}`}
                  className="flex flex-wrap items-baseline justify-between gap-2 rounded-lg border border-border/35 bg-background/20 px-3 py-2 text-[12px] tabular-nums"
                >
                  <span className="font-medium text-foreground">{type}</span>
                  <span className="text-muted-foreground">
                    {dur != null ? fmtDuration(dur) : "—"}
                    {cal != null ? ` · ${Math.round(cal)} kcal` : ""}
                    {avgHr != null ? ` · avg ${Math.round(avgHr)} bpm` : ""}
                  </span>
                </li>
              );
            })}
          </ul>
        </div>
      ) : null}

      <SleepCorrectForm day={day} localDate={dayKey} onSaved={onSleepCorrected} />

      {includeRaw && day?.payload ? (
        <div>
          <button
            type="button"
            className="text-xs text-muted-foreground underline-offset-2 hover:underline"
            onClick={() => setShowRaw((v) => !v)}
          >
            {showRaw ? "Hide raw payload" : "Show raw payload"}
          </button>
          {showRaw ? (
            <pre className="mt-2 max-h-56 overflow-auto rounded-lg bg-black/30 p-2 text-[10px] leading-snug text-muted-foreground">
              {JSON.stringify(day.payload, null, 2)}
            </pre>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
