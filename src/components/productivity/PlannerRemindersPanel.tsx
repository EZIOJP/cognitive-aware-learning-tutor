/**
 * Desktop/web local notifications for upcoming planner blocks (P4).
 * Phone APK can reuse the same schedule later; browser Notification API for now.
 */
import { useEffect, useRef, useState } from "react";
import { Bell, BellOff } from "lucide-react";
import { fetchPlannerBlocks, type PlannerBlock } from "../../api/plannerClient";

const LS_ENABLED = "calt:planner:reminders";
const LS_LEAD = "calt:planner:reminderLeadMin";
const DEFAULT_LEAD = 10;

function remindersEnabled(): boolean {
  try {
    return localStorage.getItem(LS_ENABLED) === "1";
  } catch {
    return false;
  }
}

function leadMinutes(): number {
  try {
    const n = Number(localStorage.getItem(LS_LEAD) || DEFAULT_LEAD);
    return Number.isFinite(n) ? Math.max(1, Math.min(60, n)) : DEFAULT_LEAD;
  } catch {
    return DEFAULT_LEAD;
  }
}

function setRemindersEnabled(on: boolean) {
  try {
    localStorage.setItem(LS_ENABLED, on ? "1" : "0");
  } catch {
    /* ignore */
  }
}

function notificationSupported(): boolean {
  return typeof window !== "undefined" && "Notification" in window;
}

export function PlannerRemindersPanel() {
  const [enabled, setEnabled] = useState(remindersEnabled);
  const [lead, setLead] = useState(leadMinutes);
  const [perm, setPerm] = useState<NotificationPermission | "unsupported">(
    notificationSupported() ? Notification.permission : "unsupported",
  );
  const [nextHint, setNextHint] = useState<string | null>(null);
  const firedRef = useRef<Set<string>>(new Set());
  const blocksRef = useRef<PlannerBlock[]>([]);

  useEffect(() => {
    if (!enabled || !notificationSupported()) return;

    let cancelled = false;

    const load = async () => {
      try {
        const now = new Date();
        const from = new Date(now);
        from.setHours(0, 0, 0, 0);
        const to = new Date(now);
        to.setHours(23, 59, 59, 999);
        const rows = await fetchPlannerBlocks(from, to);
        if (cancelled) return;
        blocksRef.current = (rows || []).filter(
          (b) => b.status !== "cancelled" && b.status !== "done" && b.status !== "rolled",
        );
        const upcoming = blocksRef.current
          .map((b) => ({ b, t: new Date(b.start_at).getTime() }))
          .filter((x) => x.t > Date.now())
          .sort((a, c) => a.t - c.t)[0];
        if (upcoming) {
          const when = new Date(upcoming.b.start_at).toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
          });
          setNextHint(`Next: ${upcoming.b.title} @ ${when} (−${lead}m alert)`);
        } else {
          setNextHint("No more blocks today");
        }
      } catch {
        if (!cancelled) setNextHint("Could not load today’s plan");
      }
    };

    void load();
    const reloadId = window.setInterval(() => void load(), 5 * 60_000);

    const tick = () => {
      if (Notification.permission !== "granted") return;
      const leadMs = lead * 60_000;
      const now = Date.now();
      for (const b of blocksRef.current) {
        const start = new Date(b.start_at).getTime();
        const key = `${b.id}:${b.start_at}`;
        if (firedRef.current.has(key)) continue;
        if (start - leadMs <= now && now < start + 60_000) {
          firedRef.current.add(key);
          try {
            new Notification("CALT · upcoming block", {
              body: `${b.title} starts soon (${new Date(b.start_at).toLocaleTimeString([], {
                hour: "2-digit",
                minute: "2-digit",
              })})`,
              tag: key,
            });
          } catch {
            /* ignore */
          }
        }
      }
    };

    const tickId = window.setInterval(tick, 30_000);
    tick();

    return () => {
      cancelled = true;
      window.clearInterval(reloadId);
      window.clearInterval(tickId);
    };
  }, [enabled, lead]);

  const enable = async () => {
    if (!notificationSupported()) return;
    const p = await Notification.requestPermission();
    setPerm(p);
    if (p === "granted") {
      setRemindersEnabled(true);
      setEnabled(true);
    }
  };

  const disable = () => {
    setRemindersEnabled(false);
    setEnabled(false);
  };

  if (!notificationSupported()) {
    return (
      <p className="text-xs text-muted-foreground">
        Browser notifications unsupported here — use a Chromium desktop or the future phone app.
      </p>
    );
  }

  return (
    <div className="space-y-3 text-xs">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="font-medium text-sm text-foreground flex items-center gap-1.5">
            {enabled ? <Bell size={14} className="text-primary" /> : <BellOff size={14} />}
            Plan reminders
          </p>
          <p className="text-muted-foreground mt-0.5">
            Desktop notification before each study block (from CALT planner — not Google).
          </p>
        </div>
        {enabled ? (
          <button
            type="button"
            onClick={disable}
            className="rounded-lg border border-white/10 px-3 py-1.5 hover:bg-white/5"
          >
            Disable
          </button>
        ) : (
          <button
            type="button"
            onClick={() => void enable()}
            className="rounded-lg bg-primary px-3 py-1.5 text-primary-foreground hover:bg-primary/90"
          >
            Enable
          </button>
        )}
      </div>
      <label className="flex items-center gap-2 text-muted-foreground">
        Lead minutes
        <input
          type="number"
          min={1}
          max={60}
          value={lead}
          onChange={(e) => {
            const v = Number(e.target.value) || DEFAULT_LEAD;
            setLead(v);
            try {
              localStorage.setItem(LS_LEAD, String(v));
            } catch {
              /* ignore */
            }
          }}
          className="w-16 rounded border border-white/10 bg-black/30 px-2 py-1 text-foreground"
        />
      </label>
      <p className="text-muted-foreground">
        Permission: <span className="text-foreground">{perm}</span>
        {nextHint ? ` · ${nextHint}` : ""}
      </p>
    </div>
  );
}

export default PlannerRemindersPanel;
