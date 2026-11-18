/**
 * Game Sleeper — keep Focus under low CPU while you game.
 * SoftLand ≠ Arm: this does not free SoftLand or pause Arm; it only lights down Focus UI/models.
 */
import { useCallback, useEffect, useState } from "react";
import { Moon, Sun, Loader2 } from "lucide-react";
import {
  loadFocusSleeper,
  saveFocusSleeper,
  subscribeFocusSleeper,
  postFocusSleeperShell,
  type FocusSleeperState,
} from "../../lib/focusSleeper";
import { cn } from "../../app/components/ui/utils";

export function FocusSleeperPanel() {
  const [state, setState] = useState<FocusSleeperState>(() => loadFocusSleeper());
  const [busy, setBusy] = useState(false);

  useEffect(() => subscribeFocusSleeper(setState), []);

  const apply = useCallback((next: FocusSleeperState) => {
    setBusy(true);
    saveFocusSleeper(next);
    setState(next);
    postFocusSleeperShell(next.active, next.hideToTray);
    window.setTimeout(() => setBusy(false), 200);
  }, []);

  const active = state.active;

  return (
    <div className="space-y-3 p-1">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            {active ? (
              <Moon size={15} className="shrink-0 text-sky-500" />
            ) : (
              <Sun size={15} className="shrink-0 text-muted-foreground" />
            )}
            <h3 className="text-[13px] font-semibold tracking-tight">Game sleeper</h3>
          </div>
          <p className="mt-1 text-[11px] leading-snug text-muted-foreground">
            Low-CPU Focus while you game — unloads webcam attention models and slows UI polls.
            SoftLand and Arm stay as you left them. Enforcer keeps running quietly.
          </p>
        </div>
        <button
          type="button"
          disabled={busy}
          onClick={() => apply({ ...state, active: !active })}
          className={cn(
            "shrink-0 rounded-md px-3 py-1.5 text-[12px] font-medium transition-colors",
            active
              ? "bg-sky-600 text-white hover:bg-sky-500"
              : "bg-primary text-primary-foreground hover:bg-primary/90",
            busy && "opacity-70",
          )}
        >
          {busy ? (
            <Loader2 size={14} className="animate-spin" />
          ) : active ? (
            "Wake Focus"
          ) : (
            "Sleep for gaming"
          )}
        </button>
      </div>

      {active ? (
        <p className="rounded-md border border-sky-500/30 bg-sky-500/10 px-2.5 py-1.5 text-[11px] text-sky-100">
          Sleeper on — no attention models, slow status ticks
          {state.hideToTray ? ", window → tray" : ""}. Open from tray anytime; tap Wake when done.
        </p>
      ) : null}

      <label className="flex cursor-pointer items-center gap-2 text-[11px] text-muted-foreground">
        <input
          type="checkbox"
          className="rounded border-border"
          checked={state.hideToTray}
          onChange={(e) => {
            const hideToTray = e.target.checked;
            const next = { ...state, hideToTray };
            saveFocusSleeper(next);
            setState(next);
            if (state.active) postFocusSleeperShell(true, hideToTray);
          }}
        />
        Hide Focus to tray when sleeper starts (saves GPU compositing)
      </label>
    </div>
  );
}

export default FocusSleeperPanel;
