/**
 * Minimal Home control: end a leftover work session only.
 * Plan-first — no short/dynamic session create on Home.
 */
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router";
import { CalendarDays, Loader2, Square } from "lucide-react";
import { isFocusEnforcerBridgeAvailable } from "../../lib/enforcerNativeCmd";
import { focusDataUrl } from "../../utils/focusDataUrl";
import { isFocusDesktopShell } from "../../utils/focusDesktopShell";
import { WORK_SESSION_UPDATED_EVENT } from "./workSessionEvents";

type SessionDoc = {
  active?: boolean;
  ends_at?: string;
  apps?: string[];
  sites?: string[];
};

function endsLabel(endsAt: string): string {
  if (!endsAt) return "open";
  const t = Date.parse(endsAt);
  if (!Number.isFinite(t)) return "open";
  return new Date(t).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export function ActiveWorkSessionEnd() {
  const [active, setActive] = useState(false);
  const [endsAt, setEndsAt] = useState("");
  const [apps, setApps] = useState<string[]>([]);
  const [sites, setSites] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const res = await fetch(focusDataUrl("work_session.json"), { cache: "no-store" });
      if (!res.ok) {
        setActive(false);
        return;
      }
      const doc = (await res.json()) as SessionDoc;
      setActive(Boolean(doc.active));
      setEndsAt(doc.ends_at || "");
      setApps(Array.isArray(doc.apps) ? doc.apps.map(String) : []);
      setSites(Array.isArray(doc.sites) ? doc.sites.map(String) : []);
    } catch {
      setActive(false);
    }
  }, []);

  useEffect(() => {
    void load();
    const onUpd = () => void load();
    window.addEventListener(WORK_SESSION_UPDATED_EVENT, onUpd);
    const id = window.setInterval(() => void load(), 15_000);
    return () => {
      window.removeEventListener(WORK_SESSION_UPDATED_EVENT, onUpd);
      window.clearInterval(id);
    };
  }, [load]);

  const endSession = async () => {
    setBusy(true);
    setError(null);
    try {
      if (isFocusDesktopShell() && isFocusEnforcerBridgeAvailable()) {
        const { enforcerNativeCmd } = await import("../../lib/enforcerNativeCmd");
        const native = await enforcerNativeCmd("session.set", {
          active: false,
          minutes: 0,
          apps,
          sites,
        });
        if (!native || native.ok === false) {
          throw new Error(String(native?.error || "enforcer_cmd_failed"));
        }
      }
      setActive(false);
      window.dispatchEvent(new CustomEvent(WORK_SESSION_UPDATED_EVENT));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Could not end session");
      await load();
    } finally {
      setBusy(false);
    }
  };

  if (!active) return null;

  return (
    <section className="gloss-panel overflow-hidden rounded-2xl border border-amber-400/25 bg-amber-500/[0.06]">
      <div className="flex flex-wrap items-center gap-2 px-3.5 py-2.5">
        <div className="min-w-0 flex-1">
          <p className="text-[13px] font-medium text-foreground/90">Work session still live</p>
          <p className="mt-0.5 text-[11px] text-muted-foreground">
            Ends {endsLabel(endsAt)}. Day flow is Bible → Plan → Apply/Confirm — no new sessions from
            Home.
          </p>
        </div>
        <Link
          to="/productivity?tab=plan"
          className="inline-flex items-center gap-1.5 rounded-lg border border-border/50 bg-background/40 px-2.5 py-1 text-[11px] hover:bg-accent/40"
        >
          <CalendarDays size={12} /> Plan
        </Link>
        <button
          type="button"
          disabled={busy}
          onClick={() => void endSession()}
          className="inline-flex items-center gap-1.5 rounded-lg border border-rose-400/40 bg-rose-500/15 px-2.5 py-1 text-[11px] text-rose-100 disabled:opacity-50"
        >
          {busy ? <Loader2 size={11} className="animate-spin" /> : <Square size={11} />}
          {busy ? "Ending…" : "End"}
        </button>
      </div>
      {error ? <p className="border-t border-border/30 px-3.5 py-2 text-xs text-rose-300">{error}</p> : null}
    </section>
  );
}

export default ActiveWorkSessionEnd;
