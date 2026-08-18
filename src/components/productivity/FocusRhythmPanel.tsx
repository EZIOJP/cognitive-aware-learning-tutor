import { Brain, Clock3, MousePointer2 } from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { ActualSession, PlannerBlock } from "../../api/plannerClient";
import {
  buildFocusRhythm,
  fmtDurationMinutes,
  type FocusRhythmView,
} from "./planVsActualUtils";

type Props = {
  blocks: PlannerBlock[];
  sessions: ActualSession[];
  from: Date;
  to: Date;
  view: FocusRhythmView;
  loading?: boolean;
};

type BalanceItemProps = {
  icon: typeof Brain;
  label: string;
  detail: string;
  minutes: number;
  tone: "emerald" | "rose" | "sky";
};

const TONE = {
  emerald: "text-emerald-300 border-emerald-500/25 bg-emerald-500/10",
  rose: "text-rose-300 border-rose-500/25 bg-rose-500/10",
  sky: "text-sky-300 border-sky-500/25 bg-sky-500/10",
};

function BalanceItem({ icon: Icon, label, detail, minutes, tone }: BalanceItemProps) {
  return (
    <div className={`rounded-xl border p-3 ${TONE[tone]}`}>
      <div className="flex items-center gap-1.5 text-xs font-medium">
        <Icon size={14} aria-hidden />
        {label}
      </div>
      <p className="mt-1 text-xl font-semibold tabular-nums text-foreground">
        {fmtDurationMinutes(minutes)}
      </p>
      <p className="mt-1 text-[10px] leading-snug text-muted-foreground">{detail}</p>
    </div>
  );
}

function strongestLabel(
  bucket: { label: string; zoneMinutes: number; pulledAwayMinutes: number } | null,
  kind: "zoneMinutes" | "pulledAwayMinutes",
): string | null {
  if (!bucket || bucket[kind] < 1) return null;
  return `${bucket.label} (${fmtDurationMinutes(bucket[kind])})`;
}

export function FocusRhythmPanel({ blocks, sessions, from, to, view, loading = false }: Props) {
  const rhythm = buildFocusRhythm(blocks, sessions, from, to, view);
  const total = rhythm.totals.zoneMinutes + rhythm.totals.pulledAwayMinutes + rhythm.totals.focusedElsewhereMinutes;
  const strongestZone = strongestLabel(rhythm.strongestZone, "zoneMinutes");
  const strongestPulledAway = strongestLabel(rhythm.strongestPulledAway, "pulledAwayMinutes");
  const period = view === "day" ? "today" : view === "week" ? "this week" : "this month";

  return (
    <section className="space-y-4 rounded-xl border border-white/10 bg-white/[0.025] p-4 sm:p-5" aria-labelledby="focus-rhythm-heading">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h3 id="focus-rhythm-heading" className="flex items-center gap-2 text-sm font-medium">
            <Brain size={16} className="text-violet-300" aria-hidden />
            Focus rhythm
          </h3>
          {loading ? (
            <div className="mt-1 h-3 w-64 max-w-full animate-pulse rounded bg-white/10" />
          ) : total > 0 ? (
            <p className="mt-1 text-xs text-muted-foreground">
              {strongestZone ? <>Most in the zone: <span className="text-emerald-200">{strongestZone}</span></> : "No clear focus window yet"}
              {strongestZone && strongestPulledAway ? " · " : ""}
              {strongestPulledAway ? <>Most pulled away: <span className="text-rose-200">{strongestPulledAway}</span></> : null}
            </p>
          ) : (
            <p className="mt-1 text-xs text-muted-foreground">Your focus story will appear here as you plan and track time.</p>
          )}
        </div>
        <span className="rounded-full border border-white/10 bg-white/5 px-2.5 py-1 text-[10px] uppercase tracking-wider text-muted-foreground">
          {view}
        </span>
      </div>

      {loading ? (
        <div className="grid gap-2 sm:grid-cols-3">
          {[0, 1, 2].map((n) => <div key={n} className="h-24 animate-pulse rounded-xl bg-white/5" />)}
        </div>
      ) : total === 0 ? (
        <div className="rounded-xl border border-dashed border-white/15 bg-white/[0.02] px-4 py-6 text-center">
          <Clock3 size={22} className="mx-auto mb-2 text-muted-foreground/60" aria-hidden />
          <p className="text-sm text-muted-foreground">Add planned blocks and keep the tracker running to see your focus rhythm.</p>
        </div>
      ) : (
        <>
          <div className="grid gap-2 sm:grid-cols-3">
            <BalanceItem icon={Brain} label="In the zone" detail="Focused time that matched your plan" minutes={rhythm.totals.zoneMinutes} tone="emerald" />
            <BalanceItem icon={MousePointer2} label="Pulled away" detail="Low-focus time during planned work" minutes={rhythm.totals.pulledAwayMinutes} tone="rose" />
            <BalanceItem icon={Clock3} label="Focused elsewhere" detail="Useful work outside the plan" minutes={rhythm.totals.focusedElsewhereMinutes} tone="sky" />
          </div>

          <div className="h-2.5 overflow-hidden rounded-full bg-white/5" role="img" aria-label={`Focus balance for ${period}`}>
            {(["zoneMinutes", "pulledAwayMinutes", "focusedElsewhereMinutes"] as const).map((key) => {
              const colors = {
                zoneMinutes: "bg-emerald-400",
                pulledAwayMinutes: "bg-rose-400",
                focusedElsewhereMinutes: "bg-sky-400",
              };
              return (
                <div
                  key={key}
                  className={`inline-block h-full ${colors[key]}`}
                  style={{ width: `${(rhythm.totals[key] / total) * 100}%` }}
                />
              );
            })}
          </div>

          <div className="space-y-2">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h4 className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">When it happened</h4>
              <span className="text-[10px] text-muted-foreground">Green = zone · Rose = pulled away</span>
            </div>
            <ResponsiveContainer width="100%" height={210}>
              <BarChart data={rhythm.buckets} margin={{ top: 4, right: 8, left: -14, bottom: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" vertical={false} />
                <XAxis dataKey="label" tick={{ fill: "rgba(255,255,255,0.55)", fontSize: 10 }} interval={view === "month" ? "preserveStartEnd" : 0} />
                <YAxis tick={{ fill: "rgba(255,255,255,0.55)", fontSize: 10 }} tickFormatter={(value) => `${value}m`} width={32} />
                <Tooltip
                  contentStyle={{ background: "rgba(15,15,20,0.96)", border: "1px solid rgba(255,255,255,0.12)", borderRadius: 8, fontSize: 12 }}
                  formatter={(value: number, name: string) => [fmtDurationMinutes(value), name === "zoneMinutes" ? "In the zone" : "Pulled away"]}
                />
                <Bar dataKey="zoneMinutes" stackId="rhythm" fill="#34d399" radius={[3, 3, 0, 0]} />
                <Bar dataKey="pulledAwayMinutes" stackId="rhythm" fill="#fb7185" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="border-t border-white/10 pt-3">
            <h4 className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">What pulled you away</h4>
            {rhythm.topDistractions.length > 0 ? (
              <div className="mt-2 flex flex-wrap gap-2">
                {rhythm.topDistractions.map((source) => (
                  <span key={source.name} className="rounded-full border border-rose-500/20 bg-rose-500/10 px-2.5 py-1 text-xs text-rose-100">
                    {source.name} <span className="text-rose-200/70">· {fmtDurationMinutes(source.minutes)}</span>
                  </span>
                ))}
              </div>
            ) : (
              <p className="mt-1 text-xs text-muted-foreground">No clear low-focus source was recorded during planned work.</p>
            )}
          </div>
        </>
      )}
    </section>
  );
}

export default FocusRhythmPanel;
