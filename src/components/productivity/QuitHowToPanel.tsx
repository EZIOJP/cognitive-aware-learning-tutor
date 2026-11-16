import { DoorOpen, Lock, Shield } from "lucide-react";
import { useFocusStatus } from "../../hooks/useFocusStatus";
import { isFocusDesktopShell } from "../../utils/focusDesktopShell";

/**
 * Explains why tray Quit is refused while SoftLand or Arm is on.
 * No bypass — only guidance (checklist Phase G).
 */
export function QuitHowToPanel() {
  const status = useFocusStatus();
  const softlandOn = Boolean(status.softland?.softland_enabled);
  const armed = Boolean(status.enforcerStatus?.armed);
  const quitBlocked =
    Boolean(status.enforcerStatus?.softland_or_armed) || softlandOn || armed;
  const relaunches = status.enforcerStatus?.focus_relaunch_count;
  const suppressed = status.enforcerStatus?.focus_relaunch_suppressed;

  if (!isFocusDesktopShell()) {
    return (
      <p className="text-sm text-muted-foreground">
        Quit rules apply in the Focus desktop shell (tray), not the design host.
      </p>
    );
  }

  return (
    <div className="space-y-3">
      <div>
        <h3 className="font-semibold flex items-center gap-2 text-sm">
          <DoorOpen size={16} className="text-primary" />
          Quit Focus
        </h3>
        <p className="mt-1 text-sm text-muted-foreground">
          Tray Quit is refused while SoftLand or Arm is on so the watchdog cannot be
          escaped mid-day. SoftLand ≠ Arm — turn both off (or unlock Arm) first.
        </p>
      </div>

      <div
        className={`rounded-xl border px-3 py-2.5 text-sm ${
          quitBlocked
            ? "border-amber-400/30 bg-amber-500/10 text-amber-50"
            : "border-emerald-400/30 bg-emerald-500/10 text-emerald-50"
        }`}
      >
        {quitBlocked ? (
          <p>
            Quit blocked now —{" "}
            {softlandOn ? "SoftLand ON" : "SoftLand off"}
            {" · "}
            {armed ? "Arm armed" : "Arm disarmed"}
          </p>
        ) : (
          <p>Quit allowed — SoftLand off and Arm disarmed.</p>
        )}
        {typeof relaunches === "number" && relaunches > 0 ? (
          <p className="mt-1 text-[11px] opacity-80">
            Watchdog relaunches: {relaunches}
            {suppressed ? " (suppressed)" : ""}
          </p>
        ) : null}
      </div>

      <ol className="list-decimal pl-5 space-y-1.5 text-[13px] text-muted-foreground">
        <li className="flex gap-2">
          <Shield size={14} className="mt-0.5 shrink-0 text-sky-300/80" aria-hidden />
          <span>
            Settings → Overview / Sites → turn SoftLand off (type <strong className="text-foreground/90">UNLOCK</strong>).
          </span>
        </li>
        <li className="flex gap-2">
          <Lock size={14} className="mt-0.5 shrink-0 text-rose-300/80" aria-hidden />
          <span>
            Settings → Blocks → Apps (or Unlock) → Disarm. Strong lock needs your password/phrase.
          </span>
        </li>
        <li>
          Tray icon → <strong className="text-foreground/90">Quit</strong>. Do not use{" "}
          <code className="text-[11px]">stop_calt_enforcer</code> unless you intend a full escape hatch.
        </li>
      </ol>
    </div>
  );
}

export default QuitHowToPanel;
