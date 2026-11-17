import { useEffect, useState } from "react";
import { Link } from "react-router";
import { Shield } from "lucide-react";
import { fetchEnforcerStatusMirror } from "../../api/focusMirrors";
import { focusDataUrl } from "../../utils/focusDataUrl";
import { cn } from "../../app/components/ui/utils";

const SETTINGS_SITES = "/productivity?tab=settings&section=sites";
const SETTINGS_REVIEW = "/productivity?tab=settings&section=review";

/**
 * Plan/Goals keeps SoftLand≠Arm status only — site/app rule editors live in Settings → Blocks.
 */
export function PlanRulesSettingsCue() {
  const [softlandOn, setSoftlandOn] = useState<boolean | null>(null);
  const [armed, setArmed] = useState<boolean | null>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        let soft: boolean | null = null;
        try {
          const sr = await fetch(focusDataUrl("softland_policy.json"), { cache: "no-store" });
          if (sr.ok) {
            const sj = (await sr.json()) as { softland_enabled?: boolean };
            if (typeof sj.softland_enabled === "boolean") soft = sj.softland_enabled;
          }
        } catch {
          /* fall through */
        }
        const m = await fetchEnforcerStatusMirror();
        if (cancelled) return;
        if (soft == null && m) {
          soft = Boolean(
            (m as { softland_enabled?: boolean }).softland_enabled ??
              (m as { softland?: { softland_enabled?: boolean } }).softland?.softland_enabled,
          );
        }
        if (soft != null) setSoftlandOn(soft);
        if (m) {
          setArmed(
            Boolean(
              m.armed ||
                (m as { enforcer_policy?: { hard_block_armed?: boolean } }).enforcer_policy
                  ?.hard_block_armed,
            ),
          );
        }
        try {
          const pr = await fetch(focusDataUrl("enforcer_policy.json"), { cache: "no-store" });
          if (pr.ok) {
            const pj = (await pr.json()) as { hard_block_armed?: boolean };
            if (typeof pj.hard_block_armed === "boolean") setArmed(pj.hard_block_armed);
          }
        } catch {
          /* ignore */
        }
      } catch {
        /* ignore */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <section className="goals-blocker space-y-2 rounded-xl border border-white/10 bg-black/20 px-3 py-2.5">
      <div className="flex flex-wrap items-center gap-2">
        <Shield size={13} className="text-sky-300 shrink-0" aria-hidden />
        <h4 className="text-[11px] font-semibold text-foreground">Blocker</h4>
        {softlandOn != null ? (
          <span
            className={cn(
              "text-[9px] font-mono px-1.5 py-0.5 rounded border",
              softlandOn
                ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
                : "border-white/10 text-muted-foreground",
            )}
          >
            SoftLand {softlandOn ? "on" : "off"}
          </span>
        ) : null}
        {armed != null ? (
          <span
            className={cn(
              "text-[9px] font-mono px-1.5 py-0.5 rounded border",
              armed
                ? "border-rose-500/30 bg-rose-500/10 text-rose-300"
                : "border-white/10 text-muted-foreground",
            )}
          >
            {armed ? "Armed" : "Disarmed"}
          </span>
        ) : null}
      </div>
      <p className="text-[11px] text-muted-foreground leading-snug">
        Board + Limits + Review live in Settings — SoftLand ON ≠ Armed. Sleep (Day) blocks Focus
        items while bedtime is active.
      </p>
      <div className="flex flex-wrap gap-2">
        <Link
          to={SETTINGS_SITES}
          className="inline-flex items-center rounded-lg border border-sky-400/30 bg-sky-500/10 px-2.5 py-1 text-[11px] text-sky-100 hover:bg-sky-500/20"
        >
          Blocks board
        </Link>
        <Link
          to={SETTINGS_REVIEW}
          className="inline-flex items-center rounded-lg border border-white/15 px-2.5 py-1 text-[11px] text-muted-foreground hover:bg-white/5 hover:text-foreground"
        >
          Classify review
        </Link>
      </div>
    </section>
  );
}

export default PlanRulesSettingsCue;
