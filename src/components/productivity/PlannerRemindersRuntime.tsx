/**
 * Always-on plan block reminders (panel only edits prefs).
 * Previously only ran while Settings → Day was mounted.
 */
import { useEffect, useRef } from "react";
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

export function PlannerRemindersRuntime() {
  const firedRef = useRef<Set<string>>(new Set());
  const blocksRef = useRef<PlannerBlock[]>([]);

  useEffect(() => {
    if (typeof Notification === "undefined") return;

    let cancelled = false;
    let reloadId = 0;
    let tickId = 0;

    const load = async () => {
      if (!remindersEnabled()) {
        blocksRef.current = [];
        return;
      }
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
      } catch {
        /* keep last */
      }
    };

    const tick = () => {
      if (!remindersEnabled()) return;
      if (Notification.permission !== "granted") return;
      const leadMs = leadMinutes() * 60_000;
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

    void load();
    reloadId = window.setInterval(() => void load(), 5 * 60_000);
    tickId = window.setInterval(tick, 30_000);
    tick();

    const onStorage = (e: StorageEvent) => {
      if (e.key === LS_ENABLED || e.key === LS_LEAD) void load();
    };
    window.addEventListener("storage", onStorage);

    return () => {
      cancelled = true;
      window.clearInterval(reloadId);
      window.clearInterval(tickId);
      window.removeEventListener("storage", onStorage);
    };
  }, []);

  return null;
}

export default PlannerRemindersRuntime;
