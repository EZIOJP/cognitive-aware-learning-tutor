/**
 * Health card — body-care day rollup from Python sidecar mirrors.
 */
import { useEffect, useState } from "react";
import { ScanFace } from "lucide-react";
import {
  bodyCareMirrorIsLive,
  fetchBodyCareDay,
  fetchBodyCareMirror,
  type BodyCareDay,
  type BodyCareMirror,
} from "../../api/bodyCareClient";

export function BodyCareDayCard({ day }: { day: string }) {
  const [mirror, setMirror] = useState<BodyCareMirror | null>(null);
  const [dayRow, setDayRow] = useState<BodyCareDay | null>(null);

  useEffect(() => {
    let cancelled = false;
    const pull = async () => {
      const [m, d] = await Promise.all([fetchBodyCareMirror(), fetchBodyCareDay(day)]);
      if (cancelled) return;
      setMirror(m);
      setDayRow(d);
    };
    void pull();
    const id = window.setInterval(() => void pull(), 5_000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [day]);

  const live = bodyCareMirrorIsLive(mirror);
  const sample = mirror?.sample;
  const row = dayRow || mirror?.day;

  return (
    <div className="rounded-xl border border-border/50 bg-background/30 p-3 space-y-2">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
          <ScanFace size={13} /> Body care
        </h3>
        <span
          className={
            live
              ? "text-[10px] text-emerald-300/90"
              : "text-[10px] text-muted-foreground/70"
          }
        >
          {live ? "sidecar live" : "sidecar offline"}
        </span>
      </div>

      {live && sample ? (
        <p className="text-[11px] tabular-nums text-foreground/85">
          Now
          {sample.present === false ? " · away" : " · present"}
          {typeof sample.attention_pct === "number"
            ? ` · attn ${Math.round(sample.attention_pct)}%`
            : ""}
          {typeof sample.posture_score === "number"
            ? ` · posture ${Math.round(sample.posture_score)}`
            : ""}
          {typeof sample.distance_proxy === "number"
            ? ` · dist ${sample.distance_proxy.toFixed(2)}`
            : ""}
          {typeof sample.blink_rate === "number"
            ? ` · blink ${Math.round(sample.blink_rate)}/m`
            : ""}
          {sample.sit_stand_hint && sample.sit_stand_hint !== "unknown"
            ? ` · ${sample.sit_stand_hint}`
            : ""}
          {mirror?.calibration?.sit_stand_ready === false
            ? " · calibrate sit+stand"
            : ""}
        </p>
      ) : null}

      {row && (row.samples || 0) > 0 ? (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px]">
          <Metric label="Present" value={fmtMin(row.present_minutes)} />
          <Metric
            label="Attention"
            value={
              row.attention_pct_avg != null ? `${Math.round(row.attention_pct_avg)}%` : "—"
            }
          />
          <Metric
            label="Posture"
            value={row.posture_score_avg != null ? `${Math.round(row.posture_score_avg)}` : "—"}
          />
          <Metric label="Slouch" value={fmtMin(row.slouch_minutes)} />
          <Metric label="Sit hint" value={fmtSecAsMin(row.sit_hint_sec)} />
          <Metric label="Stand hint" value={fmtSecAsMin(row.stand_hint_sec)} />
          <Metric
            label="Blink avg"
            value={
              row.blink_rate_avg != null ? `${Math.round(row.blink_rate_avg)}/m` : "—"
            }
          />
        </div>
      ) : (
        <p className="text-[11px] text-muted-foreground">
          No body-care samples for this day. Run{" "}
          <span className="font-mono">scripts\run\run_bodycare_sidecar.bat</span> (opt-in
          webcam).
        </p>
      )}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border/40 bg-black/20 px-2 py-1.5">
      <p className="text-[9px] uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="text-sm font-medium tabular-nums text-foreground/90">{value}</p>
    </div>
  );
}

function fmtMin(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return "—";
  return `${Number(v).toFixed(1)}m`;
}

function fmtSecAsMin(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v) || v <= 0) return "—";
  return `${(Number(v) / 60).toFixed(1)}m`;
}

export default BodyCareDayCard;
