import { useEffect } from "react";
import { isFocusDesktopShell } from "../../utils/focusDesktopShell";
import { useFocusStatus } from "../../hooks/useFocusStatus";
import { invalidateFocusStatusBus } from "../../lib/focusStatusBus";
import {
  bibleDoneToday,
  planConfirmedToday,
  planningEnabled,
} from "../../lib/dayGate";
import { MORNING_UPDATED_EVENT } from "./ConfirmPlanButton";
import DayGateStrip from "./DayGateStrip";

/**
 * After Bible (when planning_enabled): show DayGateStrip, not a full-screen trap.
 * Plan tab / routines stay editable. Confirm couples SoftLand + Arm (SoftLand ≠ Arm).
 * planning_enabled defaults false (session-first) — this overlay is a no-op then.
 */
export default function MorningPlanOverlay() {
  const focus = isFocusDesktopShell();
  const status = useFocusStatus();

  useEffect(() => {
    if (!focus) return;
    const kick = () => invalidateFocusStatusBus({ pipe: false });
    kick();
    const onMorning = () => invalidateFocusStatusBus({ pipe: true });
    window.addEventListener(MORNING_UPDATED_EVENT, onMorning);
    return () => window.removeEventListener(MORNING_UPDATED_EVENT, onMorning);
  }, [focus]);

  if (!focus) return null;
  if (status.dayLoop?.bedtime_active) return null;
  if (!planningEnabled(status)) return null;
  if (!bibleDoneToday(status)) return null;
  if (planConfirmedToday(status)) return null;
  if (!status.dayLoop && !status.softland?.goals) return null;

  // Bible strip already covers pre-bible; here we show plan-pending strip.
  // DayGateStrip hides itself when lock clears.
  return <DayGateStrip />;
}
