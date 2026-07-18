import { useCallback, useEffect, useState } from "react";
import { CalendarDays, Download, ExternalLink, Loader2, Link2, Upload } from "lucide-react";
import {
  downloadPlannerIcs,
  fetchGoogleCalendarAuthUrl,
  fetchGoogleCalendarStatus,
  saveGoogleCalendarCredentials,
  syncPlannerToGoogleCalendar,
  type GoogleCalendarStatus,
} from "../../api/plannerClient";

type Props = {
  refreshKey?: number;
};

/**
 * Push CALT planner → Google Calendar (Amazfit picks up via phone sync).
 * Default path: Download .ics (no Google Cloud). Optional: OAuth auto-push.
 */
export function GoogleCalendarSyncPanel({ refreshKey = 0 }: Props) {
  const [status, setStatus] = useState<GoogleCalendarStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [hint, setHint] = useState<string | null>(null);
  const [clientId, setClientId] = useState("");
  const [clientSecret, setClientSecret] = useState("");
  const [showOauth, setShowOauth] = useState(false);

  const refresh = useCallback(async () => {
    try {
      setStatus(await fetchGoogleCalendarStatus());
    } catch {
      setStatus(null);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh, refreshKey]);

  useEffect(() => {
    if (status?.client_configured) setShowOauth(true);
  }, [status?.client_configured]);

  const flash = (msg: string, ms = 7000) => {
    setHint(msg);
    window.setTimeout(() => setHint(null), ms);
  };

  const saveCreds = async () => {
    setBusy(true);
    try {
      const next = await saveGoogleCalendarCredentials(clientId, clientSecret);
      setStatus(next);
      setClientSecret("");
      flash("Credentials saved. Connect Google is enabled — click it next.");
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Save failed";
      flash(
        msg.includes("404") || msg.includes("Not Found")
          ? "Save failed: backend is outdated. Restart API (run.bat / scripts\\run_backend.bat), then Save again."
          : msg,
      );
    } finally {
      setBusy(false);
    }
  };

  const connect = async () => {
    setBusy(true);
    try {
      const url = await fetchGoogleCalendarAuthUrl();
      window.open(url, "_blank", "noopener,noreferrer");
      flash("Finish Google sign-in in the new tab, then click Push.");
    } catch (e) {
      flash(e instanceof Error ? e.message : "Connect failed");
    } finally {
      setBusy(false);
      void refresh();
    }
  };

  const push = async () => {
    setBusy(true);
    try {
      const res = await syncPlannerToGoogleCalendar(14);
      if (!res.ok) {
        flash(res.error || res.hint || "Push failed — use Download .ics instead, or Connect Google");
        return;
      }
      flash(
        `Pushed to Google · ${res.created ?? 0} new · ${res.updated ?? 0} updated · ${res.block_count ?? 0} blocks`,
      );
    } catch (e) {
      flash(e instanceof Error ? e.message : "Push failed");
    } finally {
      setBusy(false);
      void refresh();
    }
  };

  const ics = () => {
    try {
      downloadPlannerIcs(14);
      window.open("https://calendar.google.com/calendar/u/0/r/settings/export", "_blank", "noopener,noreferrer");
      flash(
        "ICS downloaded. In Google Calendar: Settings → Import & export → Import → choose the .ics file. Same Google account on phone → Amazfit.",
      );
    } catch (e) {
      flash(e instanceof Error ? e.message : "ICS download failed");
    }
  };

  const connected = Boolean(status?.connected);
  const clientOk = Boolean(status?.client_configured);
  const redirectUri =
    status?.redirect_uri || "http://127.0.0.1:8000/api/planner/google-calendar/callback";
  const setupUrl = status?.setup_url || "https://console.cloud.google.com/apis/credentials";

  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4 space-y-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold flex items-center gap-2">
            <CalendarDays size={15} className="text-sky-400" />
            Google Calendar → Amazfit
          </h3>
          <p className="text-xs text-muted-foreground mt-1 max-w-xl">
            We can’t write Amazfit’s calendar directly. Put events in <b>your</b> Google Calendar
            (Gmail account) — phone sync + Zepp then show them on the watch.
          </p>
        </div>
        <span
          className={`text-[10px] uppercase tracking-wide px-2 py-0.5 rounded-full border ${
            connected
              ? "border-emerald-500/40 text-emerald-300 bg-emerald-500/10"
              : "border-sky-500/30 text-sky-200 bg-sky-500/10"
          }`}
        >
          {connected ? "Auto-push on" : "Use .ics (no Cloud)"}
        </span>
      </div>

      <div className="rounded-xl border border-sky-500/25 bg-sky-500/5 p-3 space-y-2">
        <p className="text-xs text-sky-50/95 font-medium">Recommended — no Google Cloud</p>
        <p className="text-[11px] text-muted-foreground leading-relaxed">
          Google blocks apps from opening your calendar with only a Gmail password. Easiest path:
          download a calendar file and import it while you’re signed into Gmail in the browser.
        </p>
        <button
          type="button"
          disabled={busy}
          onClick={ics}
          className="inline-flex items-center gap-1.5 rounded-lg border border-sky-500/40 bg-sky-500/20 px-3 py-2 text-xs font-medium text-sky-50 hover:bg-sky-500/30 disabled:opacity-40"
        >
          <Download size={13} />
          Download .ics + open Google Calendar import
        </button>
      </div>

      <details
        className="rounded-xl border border-white/10 bg-white/[0.02] open:pb-3"
        open={showOauth}
        onToggle={(e) => setShowOauth((e.target as HTMLDetailsElement).open)}
      >
        <summary className="cursor-pointer list-none px-3 py-2.5 text-xs text-muted-foreground hover:text-foreground">
          Optional: auto Push (needs Google Cloud OAuth once)
        </summary>
        <div className="px-3 space-y-2">
          <p className="text-[11px] text-muted-foreground leading-relaxed">
            “Sign in with Google” still needs a Client ID from Google Cloud — that’s Google’s rule for
            any app that writes Calendar events. It’s not hosting; it’s just registering this local
            app. Skip this if .ics import is enough.
          </p>
          {!clientOk && (
            <div className="space-y-2">
              <ol className="text-[11px] text-muted-foreground list-decimal list-inside space-y-0.5">
                <li>
                  <a
                    href={setupUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="text-sky-300 hover:underline inline-flex items-center gap-1"
                  >
                    Open Google Cloud credentials <ExternalLink size={10} />
                  </a>
                </li>
                <li>
                  Web client → redirect URI:{" "}
                  <code className="text-[10px] text-foreground/90 break-all">{redirectUri}</code>
                </li>
              </ol>
              <div className="grid gap-2 sm:grid-cols-2">
                <input
                  type="text"
                  value={clientId}
                  onChange={(e) => setClientId(e.target.value)}
                  placeholder="Client ID"
                  className="rounded-lg border border-white/15 bg-black/30 px-2.5 py-1.5 text-xs outline-none focus:border-sky-500/50"
                  autoComplete="off"
                />
                <input
                  type="password"
                  value={clientSecret}
                  onChange={(e) => setClientSecret(e.target.value)}
                  placeholder="Client secret"
                  className="rounded-lg border border-white/15 bg-black/30 px-2.5 py-1.5 text-xs outline-none focus:border-sky-500/50"
                  autoComplete="off"
                />
              </div>
              <button
                type="button"
                disabled={busy || !clientId.trim() || !clientSecret.trim()}
                onClick={() => void saveCreds()}
                className="inline-flex items-center gap-1.5 rounded-lg border border-white/15 bg-white/5 px-3 py-1.5 text-xs font-medium hover:bg-white/10 disabled:opacity-40"
              >
                {busy ? <Loader2 size={12} className="animate-spin" /> : null}
                Save credentials
              </button>
            </div>
          )}
          <div className="flex flex-wrap gap-2 pt-1">
            <button
              type="button"
              disabled={busy || !clientOk}
              onClick={() => void connect()}
              className="inline-flex items-center gap-1.5 rounded-lg border border-white/15 bg-white/5 px-3 py-1.5 text-xs font-medium hover:bg-white/10 disabled:opacity-40"
            >
              {busy ? <Loader2 size={12} className="animate-spin" /> : <Link2 size={12} />}
              {connected ? "Reconnect Google" : "Connect Google"}
            </button>
            <button
              type="button"
              disabled={busy || !connected}
              onClick={() => void push()}
              className="inline-flex items-center gap-1.5 rounded-lg border border-sky-500/40 bg-sky-500/15 px-3 py-1.5 text-xs font-medium text-sky-100 hover:bg-sky-500/25 disabled:opacity-40"
            >
              {busy ? <Loader2 size={12} className="animate-spin" /> : <Upload size={12} />}
              Push to Google
            </button>
          </div>
        </div>
      </details>

      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
    </div>
  );
}

export default GoogleCalendarSyncPanel;
