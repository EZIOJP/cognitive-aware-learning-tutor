import { useCallback, useEffect, useState } from "react";
import { Moon, ShieldAlert } from "lucide-react";
import { emergencyWinddown } from "../../api/dayLoopClient";
import { isFocusDesktopShell } from "../../utils/focusDesktopShell";
import { isFocusEnforcerBridgeAvailable } from "../../lib/enforcerNativeCmd";
import { invalidateFocusStatusBus } from "../../lib/focusStatusBus";
import { useFocusStatus } from "../../hooks/useFocusStatus";

/**
 * Fullscreen sleep surface when SoftLand runtime.bedtime_active.
 * Emergency: opens web minus distraction lists (confirm EMERGENCY).
 */
export default function BedtimeOverlay() {
  const focus = isFocusDesktopShell();
  const status = useFocusStatus();
  const loop = status.dayLoop;
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [tomorrowTitles, setTomorrowTitles] = useState<string[]>([]);

  const refreshTomorrow = useCallback(async () => {
    if (!focus || !isFocusEnforcerBridgeAvailable()) return;
    if (!loop?.bedtime_active) return;
    try {
      const d = new Date();
      d.setDate(d.getDate() + 1);
      const y = d.getFullYear();
      const m = String(d.getMonth() + 1).padStart(2, "0");
      const day = String(d.getDate()).padStart(2, "0");
      const from = `${y}-${m}-${day}T00:00:00`;
      const to = `${y}-${m}-${day}T23:59:59`;
      const { enforcerNativeCmd } = await import("../../lib/enforcerNativeCmd");
      const r = await enforcerNativeCmd("plan.list", { from, to });
      const blocks = (r?.blocks as Array<{ title?: string; status?: string }>) || [];
      setTomorrowTitles(
        blocks
          .filter((b) => b.status !== "done" && b.status !== "cancelled")
          .map((b) => String(b.title || "Block"))
          .slice(0, 8),
      );
    } catch {
      setTomorrowTitles([]);
    }
  }, [focus, loop?.bedtime_active]);

  useEffect(() => {
    void refreshTomorrow();
  }, [refreshTomorrow, status.updatedAt]);

  if (!focus || !loop?.bedtime_active) return null;

  const doneTitles = (loop.tasks || []).filter((t) => t.done).map((t) => t.title);

  async function onEmergency() {
    const phrase = window.prompt("Type EMERGENCY to open the web (distractions still blocked):");
    if (phrase?.trim().toUpperCase() !== "EMERGENCY") return;
    setBusy(true);
    setErr(null);
    try {
      const r = await emergencyWinddown(30);
      if (!r.ok) throw new Error(r.error || "failed");
      invalidateFocusStatusBus({ pipe: true });
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-[200] flex flex-col items-center justify-center gap-6 px-6 text-center"
      style={{
        background:
          "radial-gradient(ellipse at 50% 20%, #1a2744 0%, #0b1020 55%, #05070f 100%)",
      }}
    >
      <Moon className="size-10 text-sky-200/80" aria-hidden />
      <div className="space-y-2 max-w-md">
        <h1 className="text-2xl font-semibold tracking-tight text-sky-50">Bedtime</h1>
        <p className="text-sm text-sky-100/70">
          SoftLand sleep window is active. Rest well — tomorrow’s plan is waiting.
        </p>
      </div>
      {doneTitles.length ? (
        <div className="text-left text-xs text-sky-100/60 max-w-sm w-full">
          <p className="uppercase tracking-wider text-[10px] mb-1">Done today</p>
          <ul className="space-y-0.5">
            {doneTitles.slice(0, 6).map((t) => (
              <li key={t}>· {t}</li>
            ))}
          </ul>
        </div>
      ) : null}
      {tomorrowTitles.length ? (
        <div className="text-left text-xs text-sky-100/60 max-w-sm w-full">
          <p className="uppercase tracking-wider text-[10px] mb-1">Tomorrow</p>
          <ul className="space-y-0.5">
            {tomorrowTitles.map((t) => (
              <li key={t}>· {t}</li>
            ))}
          </ul>
        </div>
      ) : null}
      {err ? <p className="text-xs text-rose-300">{err}</p> : null}
      <button
        type="button"
        disabled={busy}
        onClick={() => void onEmergency()}
        className="inline-flex items-center gap-2 rounded-xl border border-rose-400/40 bg-rose-500/15 px-4 py-2 text-sm text-rose-50 hover:bg-rose-500/25 disabled:opacity-50"
      >
        <ShieldAlert className="size-4" aria-hidden />
        Emergency open (type EMERGENCY)
      </button>
    </div>
  );
}
