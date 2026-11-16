import { useCallback, useEffect, useState } from "react";
import { Loader2, Mail, Send } from "lucide-react";
import {
  FOCUS_EMAIL_REPORT_EVENT,
  FOCUS_REPORT_EMAIL,
  composeDailyEmailReport,
  loadDailyReportContext,
  loadEmailReportPrefs,
  markEmailReportSentToday,
  saveEmailReportPrefs,
  sendEmailReportNow,
  type FocusEmailReportPrefs,
} from "../../lib/focusEmailReport";

type Props = {
  /** Compact strip for Home (Send report). */
  variant?: "settings" | "home";
};

/**
 * Settings → Advanced: daily report via mailto to FOCUS_REPORT_EMAIL.
 * Home: Send report button for quick testing.
 */
export function FocusEmailReportPanel({ variant = "settings" }: Props) {
  const [prefs, setPrefs] = useState<FocusEmailReportPrefs>(() => loadEmailReportPrefs());
  const [preview, setPreview] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<string | null>(null);

  useEffect(() => {
    const sync = () => setPrefs(loadEmailReportPrefs());
    window.addEventListener(FOCUS_EMAIL_REPORT_EVENT, sync);
    return () => window.removeEventListener(FOCUS_EMAIL_REPORT_EVENT, sync);
  }, []);

  const persist = (next: FocusEmailReportPrefs) => setPrefs(saveEmailReportPrefs(next));

  const refreshPreview = useCallback(async () => {
    setBusy(true);
    setStatus(null);
    try {
      const ctx = await loadDailyReportContext();
      setPreview(composeDailyEmailReport(ctx, prefs));
    } finally {
      setBusy(false);
    }
  }, [prefs]);

  const sendReport = async () => {
    setBusy(true);
    setStatus(null);
    try {
      const r = await sendEmailReportNow(prefs);
      setPreview(r.preview || preview);
      if (!r.ok) {
        setStatus("Could not open mail — try again from Focus desktop.");
      } else {
        markEmailReportSentToday();
        setStatus(`Opened email to ${r.to}. Tap Send in your mail app.`);
      }
    } finally {
      setBusy(false);
    }
  };

  if (variant === "home") {
    return (
      <section className="gloss-panel rounded-2xl border border-border/40 px-3.5 py-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="min-w-0">
            <p className="text-[13px] font-medium text-foreground/90 flex items-center gap-1.5">
              <Mail size={14} className="text-sky-400/90 shrink-0" />
              Daily report
            </p>
            <p className="text-[11px] text-muted-foreground mt-0.5 truncate">
              Email · {FOCUS_REPORT_EMAIL}
            </p>
          </div>
          <button
            type="button"
            disabled={busy}
            onClick={() => void sendReport()}
            className="inline-flex items-center gap-1.5 rounded-lg border border-sky-500/40 bg-sky-500/15 px-2.5 py-1.5 text-[11px] text-sky-50 hover:bg-sky-500/25 disabled:opacity-40"
          >
            {busy ? <Loader2 size={12} className="animate-spin" /> : <Send size={12} />}
            Send report
          </button>
        </div>
        {status ? <p className="mt-2 text-[11px] text-amber-100/90">{status}</p> : null}
      </section>
    );
  }

  return (
    <div className="space-y-4">
      <div>
        <h3 className="font-semibold flex items-center gap-2 text-sm">
          <Mail size={16} className="text-sky-400/90" />
          Email daily report
        </h3>
        <p className="mt-1 text-sm text-muted-foreground">
          Opens your mail app with today’s productive time + top apps to{" "}
          <span className="font-mono text-foreground/90">{FOCUS_REPORT_EMAIL}</span>. Tap Send.
        </p>
      </div>

      <label className="flex items-center justify-between gap-3 rounded-xl border border-white/10 bg-black/20 px-3 py-2.5 text-sm cursor-pointer">
        <span>
          <span className="block font-medium">Enable daily send</span>
          <span className="text-xs text-muted-foreground">
            Once per day at the time below (Focus must be running).
          </span>
        </span>
        <input
          type="checkbox"
          checked={prefs.enabled}
          onChange={(e) => persist({ ...prefs, enabled: e.target.checked })}
        />
      </label>

      <label className="block space-y-1.5">
        <span className="text-xs text-muted-foreground">Send time (local)</span>
        <input
          type="time"
          className="w-full max-w-[12rem] rounded-lg border border-white/10 bg-black/40 px-2.5 py-2 text-sm"
          value={prefs.sendTime}
          onChange={(e) => persist({ ...prefs, sendTime: e.target.value || "21:00" })}
        />
      </label>

      <div className="rounded-xl border border-white/10 bg-black/20 px-3 py-2.5 text-sm">
        <span className="text-xs text-muted-foreground">To</span>
        <p className="font-mono text-foreground/90 mt-0.5">{FOCUS_REPORT_EMAIL}</p>
      </div>

      <div className="flex flex-wrap gap-3">
        <label className="inline-flex items-center gap-2 text-xs text-muted-foreground cursor-pointer">
          <input
            type="checkbox"
            checked={prefs.includeActivities}
            onChange={(e) => persist({ ...prefs, includeActivities: e.target.checked })}
          />
          Top apps
        </label>
        <label className="inline-flex items-center gap-2 text-xs text-muted-foreground cursor-pointer">
          <input
            type="checkbox"
            checked={prefs.includeTodos}
            onChange={(e) => persist({ ...prefs, includeTodos: e.target.checked })}
          />
          Open todos
        </label>
      </div>

      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          disabled={busy}
          onClick={() => void refreshPreview()}
          className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-xs hover:bg-white/10 disabled:opacity-50"
        >
          {busy ? <Loader2 size={13} className="animate-spin" /> : null}
          Preview
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => void sendReport()}
          className="inline-flex items-center gap-1.5 rounded-lg border border-sky-500/40 bg-sky-500/15 px-3 py-1.5 text-xs text-sky-50 hover:bg-sky-500/25 disabled:opacity-50"
        >
          {busy ? <Loader2 size={13} className="animate-spin" /> : <Send size={13} />}
          Send report
        </button>
      </div>

      {status ? <p className="text-xs text-amber-100/90">{status}</p> : null}

      {preview ? (
        <pre className="whitespace-pre-wrap rounded-xl border border-white/10 bg-black/30 px-3 py-2.5 text-[12px] leading-relaxed text-foreground/90 max-h-64 overflow-y-auto">
          {preview}
        </pre>
      ) : null}
    </div>
  );
}

export default FocusEmailReportPanel;
