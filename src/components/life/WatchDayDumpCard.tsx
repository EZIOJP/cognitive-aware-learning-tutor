import { useMemo, useState } from "react";
import type { WearableDay } from "../../api/wearablesClient";
import { formatHoursMins } from "../../utils/formatDuration";

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

type SleepBlock = {
  score?: number | null;
  total_min?: number | null;
  deep_min?: number | null;
  start_min?: number | null;
  end_min?: number | null;
  stages?: SleepStage[];
  naps?: Array<{ start?: number; stop?: number; length?: number }>;
};

const STAGE_COLORS: Record<string, string> = {
  wake: "#f59e0b",
  awake: "#f59e0b",
  light: "#60a5fa",
  rem: "#a78bfa",
  deep: "#312e81",
  stage: "#64748b",
};

const STAGE_ORDER = ["deep", "light", "rem", "wake"] as const;

function presentNum(n: number | null | undefined): n is number {
  return typeof n === "number" && Number.isFinite(n) && n > 0;
}

function asObj(v: unknown): Record<string, unknown> | null {
  return v && typeof v === "object" && !Array.isArray(v) ? (v as Record<string, unknown>) : null;
}

function fmtMinutesClock(minOfDay: number): string {
  const m = ((Math.round(minOfDay) % 1440) + 1440) % 1440;
  const h = Math.floor(m / 60);
  const mm = m % 60;
  return `${String(h).padStart(2, "0")}:${String(mm).padStart(2, "0")}`;
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

function parseSleep(payload: Record<string, unknown> | null | undefined, day: WearableDay | null | undefined): SleepBlock {
  const sleep = asObj(payload?.sleep) || {};
  const stagesRaw = Array.isArray(sleep.stages) ? sleep.stages : [];
  const stages: SleepStage[] = stagesRaw
    .map((s) => {
      const row = asObj(s);
      if (!row) return null;
      const start = Number(row.start);
      const stop = Number(row.stop);
      if (!Number.isFinite(start) || !Number.isFinite(stop) || stop <= start) return null;
      return {
        model: typeof row.model === "number" ? row.model : undefined,
        start,
        stop,
        label: normalizeLabel(typeof row.label === "string" ? row.label : undefined),
      };
    })
    .filter((s): s is SleepStage => !!s);

  const totalFromStages = stages.reduce((a, s) => a + (s.stop - s.start), 0);
  const total_min =
    presentNum(Number(sleep.total_min))
      ? Number(sleep.total_min)
      : presentNum(day?.sleep_hours)
        ? Math.round(Number(day?.sleep_hours) * 60)
        : totalFromStages > 0
          ? totalFromStages
          : null;

  return {
    score: presentNum(Number(sleep.score)) ? Number(sleep.score) : presentNum(day?.sleep_score) ? Number(day?.sleep_score) : null,
    total_min,
    deep_min: presentNum(Number(sleep.deep_min))
      ? Number(sleep.deep_min)
      : presentNum(day?.sleep_deep_min)
        ? Number(day?.sleep_deep_min)
        : null,
    start_min: Number.isFinite(Number(sleep.start_min)) ? Number(sleep.start_min) : null,
    end_min: Number.isFinite(Number(sleep.end_min)) ? Number(sleep.end_min) : null,
    stages,
    naps: Array.isArray(sleep.naps) ? (sleep.naps as SleepBlock["naps"]) : [],
  };
}

function SleepHypnogram({ stages }: { stages: SleepStage[] }) {
  if (!stages.length) return null;
  const t0 = Math.min(...stages.map((s) => s.start));
  const t1 = Math.max(...stages.map((s) => s.stop));
  const span = Math.max(1, t1 - t0);

  return (
    <div className="space-y-1.5">
      <div className="flex h-10 w-full overflow-hidden rounded-lg border border-white/10 bg-black/30">
        {stages.map((s, i) => {
          const w = ((s.stop - s.start) / span) * 100;
          const color = STAGE_COLORS[s.label] || STAGE_COLORS.stage;
          return (
            <div
              key={`${s.start}-${s.stop}-${i}`}
              title={`${s.label} · ${fmtMinutesClock(s.start)}–${fmtMinutesClock(s.stop)} (${formatHoursMins(s.stop - s.start)})`}
              style={{ width: `${w}%`, background: color }}
              className="h-full min-w-[1px]"
            />
          );
        })}
      </div>
      <div className="flex justify-between text-[10px] tabular-nums text-muted-foreground">
        <span>{fmtMinutesClock(t0)}</span>
        <span>{fmtMinutesClock(t1)}</span>
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
}: {
  day: WearableDay | null | undefined;
  fallback?: Fallback | null;
  emptyHint?: string;
  includeRaw?: boolean;
}) {
  const [showRaw, setShowRaw] = useState(false);
  const fb = fallback || {};
  const payload = (day?.payload as Record<string, unknown> | null | undefined) || null;

  const sleep = useMemo(() => parseSleep(payload, day ?? null), [payload, day]);

  const activity = asObj(payload?.activity) || {};
  const calorie = asObj(payload?.calorie) || {};
  const distance = asObj(payload?.distance) || {};

  const steps = presentNum(day?.steps)
    ? Number(day?.steps)
    : presentNum(Number(activity.steps))
      ? Number(activity.steps)
      : presentNum(fb.last_steps)
        ? Number(fb.last_steps)
        : null;
  const stepTarget = presentNum(day?.step_target)
    ? Number(day?.step_target)
    : presentNum(Number(activity.target))
      ? Number(activity.target)
      : null;
  const kcal = presentNum(day?.calories)
    ? Number(day?.calories)
    : presentNum(Number(calorie.kcal))
      ? Number(calorie.kcal)
      : presentNum(fb.last_calories)
        ? Number(fb.last_calories)
        : null;
  const kcalTarget = presentNum(day?.calorie_target)
    ? Number(day?.calorie_target)
    : presentNum(Number(calorie.target))
      ? Number(calorie.target)
      : null;
  const distM = presentNum(day?.distance_m)
    ? Number(day?.distance_m)
    : presentNum(Number(distance.meters))
      ? Number(distance.meters)
      : presentNum(fb.last_distance_m)
        ? Number(fb.last_distance_m)
        : null;

  const hr = presentNum(day?.hr_last) ? Number(day?.hr_last) : presentNum(fb.last_hr) ? Number(fb.last_hr) : null;
  const spo2 = presentNum(day?.spo2) ? Number(day?.spo2) : presentNum(fb.last_spo2) ? Number(fb.last_spo2) : null;
  const stress = presentNum(day?.stress) ? Number(day?.stress) : presentNum(fb.last_stress) ? Number(fb.last_stress) : null;
  const pai = presentNum(day?.pai_today) ? Number(day?.pai_today) : presentNum(fb.last_pai) ? Number(fb.last_pai) : null;
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

  const hasSleep = presentNum(sleep.total_min) || presentNum(sleep.score) || (sleep.stages && sleep.stages.length > 0);
  const hasMove = presentNum(steps) || presentNum(kcal) || presentNum(distM);
  const hasExtras = presentNum(hr) || presentNum(spo2) || presentNum(stress) || presentNum(pai) || presentNum(stand) || presentNum(sitting) || presentNum(battery);
  const hasAnything = hasSleep || hasMove || hasExtras || !!day?.local_date;

  if (!hasAnything && fb.last_sleep_hours == null && fb.last_steps == null) {
    return <p className="text-sm text-muted-foreground">{emptyHint}</p>;
  }

  const totals = stageTotals(sleep.stages || [], sleep.deep_min ?? null);
  const stageSum = STAGE_ORDER.reduce((a, k) => a + (totals[k] || 0), 0);
  const stepPct =
    presentNum(steps) && presentNum(stepTarget) ? Math.round(Math.min(100, (steps / stepTarget) * 100)) : null;

  const metrics: Array<{ key: string; label: string; value: string; hint?: string; accent?: string }> = [];
  if (presentNum(sleep.score)) {
    metrics.push({ key: "score", label: "Sleep score", value: String(sleep.score), accent: "sky" });
  }
  if (presentNum(sleep.total_min)) {
    metrics.push({
      key: "duration",
      label: "Asleep",
      value: fmtDuration(sleep.total_min),
      hint:
        sleep.start_min != null && sleep.end_min != null
          ? `${fmtMinutesClock(sleep.start_min)}–${fmtMinutesClock(sleep.end_min)}`
          : undefined,
    });
  }
  if (presentNum(steps)) {
    metrics.push({
      key: "steps",
      label: "Steps",
      value: steps.toLocaleString(),
      hint: presentNum(stepTarget) ? `of ${stepTarget.toLocaleString()}` : undefined,
      accent: "emerald",
    });
  }
  if (presentNum(kcal)) {
    metrics.push({
      key: "kcal",
      label: "Calories",
      value: `${kcal.toLocaleString()}`,
      hint: presentNum(kcalTarget) ? `of ${kcalTarget.toLocaleString()}` : "kcal",
    });
  }
  if (presentNum(distM)) {
    metrics.push({
      key: "dist",
      label: "Distance",
      value: `${(distM / 1000).toFixed(2)}`,
      hint: "km",
    });
  }

  return (
    <div className="space-y-4">
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

      {(sleep.stages?.length ?? 0) > 0 ? (
        <div className="space-y-2">
          <SleepHypnogram stages={sleep.stages!} />
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
          {presentNum(hr) ? (
            <span>
              HR {hr}
              {presentNum(day?.hr_resting) ? ` / rest ${day?.hr_resting}` : ""}
            </span>
          ) : null}
          {presentNum(spo2) ? <span>SpO₂ {spo2}%</span> : null}
          {presentNum(stress) ? <span>Stress {stress}</span> : null}
          {presentNum(pai) ? <span>PAI {pai}</span> : null}
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
