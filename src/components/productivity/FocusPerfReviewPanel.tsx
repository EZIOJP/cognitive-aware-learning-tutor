import { useEffect, useState } from "react";
import {
  FOCUS_PERF_THRESHOLDS,
  clearFocusPerfLog,
  focusPerfLevel,
  focusPerfSummary,
  getFocusPerfReview,
  getFocusPerfRing,
  subscribeFocusPerf,
  type FocusPerfEntry,
} from "../../lib/focusPerfLog";

function levelClass(level: string): string {
  switch (level) {
    case "error":
      return "text-red-400";
    case "critical":
      return "text-orange-400";
    case "high":
      return "text-amber-300";
    case "warn":
      return "text-yellow-200/90";
    default:
      return "text-muted-foreground";
  }
}

function fmtTs(ts: number): string {
  try {
    return new Date(ts).toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return "—";
  }
}

/**
 * Settings → Tools: filtered high-latency + error review from Focus perf log.
 */
export function FocusPerfReviewPanel() {
  const [, bump] = useState(0);
  useEffect(() => subscribeFocusPerf(() => bump((n) => n + 1)), []);

  const summary = focusPerfSummary();
  const review = getFocusPerfReview().slice().reverse();
  const recent = getFocusPerfRing().slice(-12).reverse();

  const copyReview = async () => {
    const payload = {
      when: new Date().toISOString(),
      thresholds: FOCUS_PERF_THRESHOLDS,
      summary,
      review,
    };
    try {
      await navigator.clipboard.writeText(JSON.stringify(payload, null, 2));
    } catch {
      /* ignore */
    }
  };

  return (
    <div className="space-y-3 rounded-xl border border-border/60 bg-card/40 p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h3 className="text-[12px] font-semibold text-foreground">Perf review (latency + errors)</h3>
          <p className="text-[11px] text-muted-foreground mt-0.5 max-w-xl">
            Enforcer cmds are serialized on one pipe — overlapping Home/Settings polls queue up and
            feel like UI lag. Review = latency ≥ {FOCUS_PERF_THRESHOLDS.highMs}ms or any error.
            Warn ≥ {FOCUS_PERF_THRESHOLDS.warnMs}ms · critical ≥ {FOCUS_PERF_THRESHOLDS.criticalMs}ms.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => void copyReview()}
            className="rounded-lg border border-border/60 px-2.5 py-1 text-[11px] hover:bg-accent/50"
          >
            Copy review JSON
          </button>
          <button
            type="button"
            onClick={() => clearFocusPerfLog()}
            className="rounded-lg border border-border/60 px-2.5 py-1 text-[11px] hover:bg-accent/50"
          >
            Clear
          </button>
        </div>
      </div>

      <div className="flex flex-wrap gap-3 text-[11px] tabular-nums text-muted-foreground">
        <span>
          samples <b className="text-foreground">{summary.total}</b>
        </span>
        <span>
          review <b className="text-amber-300">{summary.review}</b>
        </span>
        <span>
          errors <b className="text-red-400">{summary.errors}</b>
        </span>
        <span>
          high+ <b className="text-orange-400">{summary.high}</b>
        </span>
        <span>
          p50 <b className="text-foreground">{summary.p50}ms</b>
        </span>
        <span>
          p95 <b className="text-foreground">{summary.p95}ms</b>
        </span>
        {summary.slowest ? (
          <span>
            slowest{" "}
            <b className="text-foreground">
              {summary.slowest.name} {summary.slowest.latencyMs}ms
            </b>
          </span>
        ) : null}
      </div>

      <ReviewTable title="Filtered for review (high latency / errors)" rows={review} empty="No high-latency or errors yet — use the app for a minute." />
      <ReviewTable title="Recent samples (last 12)" rows={recent} empty="No samples yet." />
    </div>
  );
}

function ReviewTable({
  title,
  rows,
  empty,
}: {
  title: string;
  rows: FocusPerfEntry[];
  empty: string;
}) {
  return (
    <div>
      <h4 className="text-[11px] font-medium text-foreground/90 mb-1.5">{title}</h4>
      {!rows.length ? (
        <p className="text-[11px] text-muted-foreground">{empty}</p>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-border/40">
          <table className="w-full text-[10px] text-left">
            <thead className="bg-muted/30 text-muted-foreground">
              <tr>
                <th className="px-2 py-1.5 font-medium">Time</th>
                <th className="px-2 py-1.5 font-medium">Lvl</th>
                <th className="px-2 py-1.5 font-medium">Kind</th>
                <th className="px-2 py-1.5 font-medium">Name</th>
                <th className="px-2 py-1.5 font-medium">ms</th>
                <th className="px-2 py-1.5 font-medium">queue</th>
                <th className="px-2 py-1.5 font-medium">rt</th>
                <th className="px-2 py-1.5 font-medium">Error</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((e) => {
                const lvl = focusPerfLevel(e);
                return (
                  <tr key={e.id} className="border-t border-border/30">
                    <td className="px-2 py-1 tabular-nums whitespace-nowrap">{fmtTs(e.ts)}</td>
                    <td className={`px-2 py-1 font-semibold uppercase ${levelClass(lvl)}`}>{lvl}</td>
                    <td className="px-2 py-1">{e.kind}</td>
                    <td className="px-2 py-1 font-mono">{e.name}</td>
                    <td className="px-2 py-1 tabular-nums">{e.latencyMs}</td>
                    <td className="px-2 py-1 tabular-nums">
                      {e.queueWaitMs != null ? e.queueWaitMs : "—"}
                    </td>
                    <td className="px-2 py-1 tabular-nums">
                      {e.roundTripMs != null ? e.roundTripMs : "—"}
                    </td>
                    <td className="px-2 py-1 text-red-300/90 max-w-[10rem] truncate">
                      {e.error || "—"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
