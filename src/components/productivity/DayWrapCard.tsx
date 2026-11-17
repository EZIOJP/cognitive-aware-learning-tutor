/**
 * End-of-day wrap — plan vs actual, distraction during plan, sleep, sit/stand.
 * Plus: Tomorrow’s one fix + Close the day seal (local). No “focus quality” jargon.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { Check, Moon, RefreshCw, Sparkles } from "lucide-react";
import { useNavigate } from "react-router";
import type { DesktopStats } from "../../api/behaviorClient";
import {
  fetchBodyCareDay,
  type BodyCareDay,
} from "../../api/bodyCareClient";
import type { AdherenceSummary, PlanDriftSummary } from "../../api/plannerClient";
import {
  buildDayWrapInsight,
  fmtHoursFromMinutes,
} from "../../lib/dayWrapInsight";
import {
  DAY_WRAP_UPDATED_EVENT,
  loadDayWrap,
  saveDayWrap,
  type DayWrapRecord,
  yesterdayTomorrowFix,
} from "../../lib/dayWrapPrefs";
import { cn } from "../../app/components/ui/utils";

function toDayIso(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

type Props = {
  day: Date;
  adherence: AdherenceSummary | null;
  planDrift: PlanDriftSummary | null;
  desktop: DesktopStats | null;
  sleepHours: number | null;
  refreshKey?: number;
};

export function DayWrapCard({
  day,
  adherence,
  planDrift,
  desktop,
  sleepHours,
  refreshKey = 0,
}: Props) {
  const nav = useNavigate();
  const dayIso = toDayIso(day);
  const [body, setBody] = useState<BodyCareDay | null>(null);
  const [wrap, setWrap] = useState<DayWrapRecord>(() => loadDayWrap(dayIso));
  const [note, setNote] = useState("");
  const [morningFix, setMorningFix] = useState(() => yesterdayTomorrowFix());

  useEffect(() => {
    const w = loadDayWrap(dayIso);
    setWrap(w);
    setNote(w.note || "");
  }, [dayIso, refreshKey]);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      const d = await fetchBodyCareDay(dayIso);
      if (!cancelled) setBody(d);
    })();
    return () => {
      cancelled = true;
    };
  }, [dayIso, refreshKey]);

  useEffect(() => {
    const sync = () => {
      setWrap(loadDayWrap(dayIso));
      setMorningFix(yesterdayTomorrowFix());
    };
    window.addEventListener(DAY_WRAP_UPDATED_EVENT, sync as EventListener);
    return () => window.removeEventListener(DAY_WRAP_UPDATED_EVENT, sync as EventListener);
  }, [dayIso]);

  const productiveMin =
    desktop?.productive_seconds != null
      ? desktop.productive_seconds / 60
      : adherence?.productive_minutes ?? null;

  const insight = useMemo(
    () =>
      buildDayWrapInsight({
        adherence,
        planDrift,
        body,
        sleepHours,
        productiveMinutes: productiveMin,
      }),
    [adherence, planDrift, body, sleepHours, productiveMin],
  );

  const pinFix = useCallback(() => {
    const next = saveDayWrap(dayIso, {
      tomorrow_fix: insight.tomorrowFix,
      note: note.trim(),
      closed: wrap.closed,
      closed_at: wrap.closed_at,
    });
    setWrap(next);
  }, [dayIso, insight.tomorrowFix, note, wrap.closed, wrap.closed_at]);

  const closeDay = useCallback(() => {
    const next = saveDayWrap(dayIso, {
      closed: true,
      closed_at: new Date().toISOString(),
      note: note.trim(),
      tomorrow_fix: wrap.tomorrow_fix.trim() || insight.tomorrowFix,
    });
    setWrap(next);
  }, [dayIso, note, wrap.tomorrow_fix, insight.tomorrowFix]);

  const reopen = useCallback(() => {
    const next = saveDayWrap(dayIso, {
      closed: false,
      closed_at: null,
      note: note.trim(),
      tomorrow_fix: wrap.tomorrow_fix,
    });
    setWrap(next);
  }, [dayIso, note, wrap.tomorrow_fix]);

  const planned = adherence?.planned_minutes ?? 0;
  const onPlan = adherence?.effective_focus_minutes ?? 0;
  const distracted = adherence?.distraction_on_plan_minutes ?? 0;
  const sitM = (body?.sit_hint_sec ?? 0) / 60;
  const standM = (body?.stand_hint_sec ?? 0) / 60;
  const hasBody = (body?.samples ?? 0) > 0;

  return (
    <div
      className={cn(
        "rounded-2xl border p-4 space-y-4",
        wrap.closed
          ? "border-emerald-500/30 bg-emerald-500/[0.06]"
          : "border-border/50 bg-background/30",
      )}
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold tracking-tight text-foreground flex items-center gap-2">
            <Moon size={15} className="text-sky-300/90" />
            End of day
            {wrap.closed ? (
              <span className="rounded-md bg-emerald-500/20 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-emerald-200">
                Closed
              </span>
            ) : null}
          </h3>
          <p className="mt-0.5 text-[11px] text-muted-foreground">
            {insight.headline}
            {wrap.close_streak > 1 ? ` · ${wrap.close_streak}-day close streak` : ""}
          </p>
        </div>
        <button
          type="button"
          onClick={() => nav("/productivity?tab=analytics")}
          className="text-[11px] text-muted-foreground hover:text-foreground"
        >
          Full plan vs actual →
        </button>
      </div>

      {morningFix ? (
        <div className="rounded-xl border border-amber-500/25 bg-amber-500/[0.07] px-3 py-2">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-amber-200/90">
            From yesterday
          </p>
          <p className="mt-0.5 text-[12px] text-foreground/90">{morningFix.fix}</p>
        </div>
      ) : null}

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
        <Stat
          label="Planned"
          value={fmtHoursFromMinutes(planned)}
          sub={planned > 0 ? `${Math.round(adherence?.adherence_pct ?? 0)}% landed` : "no blocks"}
        />
        <Stat
          label="On-plan"
          value={fmtHoursFromMinutes(onPlan)}
          sub="during your blocks"
        />
        <Stat
          label="Off-plan in blocks"
          value={fmtHoursFromMinutes(distracted)}
          sub="distraction during plan"
          warn={distracted >= 35}
        />
        <Stat
          label="Sleep"
          value={sleepHours != null && sleepHours > 0 ? `${sleepHours.toFixed(1)}h` : "—"}
          sub="last night"
        />
        <Stat
          label="Sat"
          value={hasBody ? fmtHoursFromMinutes(sitM) : "—"}
          sub="camera hint"
        />
        <Stat
          label="Stood"
          value={hasBody ? fmtHoursFromMinutes(standM) : "—"}
          sub="camera hint"
        />
        <Stat
          label="Productive"
          value={fmtHoursFromMinutes(productiveMin)}
          sub="tracked time"
        />
        <Stat
          label="Blocks"
          value={String(adherence?.block_count ?? 0)}
          sub={`${adherence?.session_count ?? 0} sessions`}
        />
      </div>

      {planDrift?.lines?.length ? (
        <ul className="text-[11px] text-amber-100/85 space-y-0.5 list-disc list-inside">
          {planDrift.lines.slice(0, 3).map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
      ) : null}

      <div className="rounded-xl border border-border/40 bg-black/20 px-3 py-2.5 space-y-2">
        <div className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
          <Sparkles size={12} className="text-violet-300/90" />
          Tomorrow’s one fix
        </div>
        <p className="text-[13px] text-foreground/90 leading-snug">
          {wrap.tomorrow_fix.trim() || insight.tomorrowFix}
        </p>
        <p className="text-[10px] text-muted-foreground">{insight.why}</p>
        <div className="flex flex-wrap gap-2 pt-1">
          <button
            type="button"
            onClick={pinFix}
            className="rounded-lg border border-border/50 bg-background/40 px-2.5 py-1 text-[11px] hover:bg-accent/40"
          >
            Pin this fix
          </button>
          <button
            type="button"
            onClick={() =>
              setWrap(
                saveDayWrap(dayIso, {
                  tomorrow_fix: insight.tomorrowFix,
                  note: note.trim(),
                  closed: wrap.closed,
                  closed_at: wrap.closed_at,
                }),
              )
            }
            className="inline-flex items-center gap-1 rounded-lg border border-border/50 bg-background/40 px-2.5 py-1 text-[11px] hover:bg-accent/40"
          >
            <RefreshCw size={11} />
            Refresh suggestion
          </button>
        </div>
      </div>

      <label className="block">
        <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
          Optional note
        </span>
        <textarea
          className="mt-1 w-full rounded-xl border border-border/50 bg-background/50 px-3 py-2 text-[12px] text-foreground outline-none focus:border-primary/40 min-h-[2.75rem] resize-y"
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="One line for yourself…"
          disabled={wrap.closed}
        />
      </label>

      <div className="flex flex-wrap items-center gap-2">
        {!wrap.closed ? (
          <button
            type="button"
            onClick={closeDay}
            className="focus-btn-primary inline-flex items-center gap-1.5 px-3 text-xs"
          >
            <Check size={14} />
            Close the day
          </button>
        ) : (
          <button
            type="button"
            onClick={reopen}
            className="focus-btn-ghost inline-flex px-3 text-xs"
          >
            Reopen
          </button>
        )}
        {wrap.closed_at ? (
          <span className="text-[10px] text-muted-foreground">
            Sealed {new Date(wrap.closed_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
          </span>
        ) : (
          <span className="text-[10px] text-muted-foreground">
            Closes locally on this PC — pins tomorrow’s fix for morning Home.
          </span>
        )}
      </div>
    </div>
  );
}

function Stat({
  label,
  value,
  sub,
  warn,
}: {
  label: string;
  value: string;
  sub: string;
  warn?: boolean;
}) {
  return (
    <div
      className={cn(
        "rounded-xl border px-2.5 py-2",
        warn ? "border-amber-500/35 bg-amber-500/[0.08]" : "border-border/40 bg-black/15",
      )}
    >
      <p className="text-[9px] uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="text-sm font-semibold tabular-nums text-foreground/95">{value}</p>
      <p className="text-[10px] text-muted-foreground truncate">{sub}</p>
    </div>
  );
}

export default DayWrapCard;
