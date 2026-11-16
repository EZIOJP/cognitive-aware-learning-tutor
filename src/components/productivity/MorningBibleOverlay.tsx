import { useEffect } from "react";
import { useLocation, useNavigate } from "react-router";
import { isFocusDesktopShell } from "../../utils/focusDesktopShell";
import { isFocusEnforcerBridgeAvailable } from "../../lib/enforcerNativeCmd";
import { useFocusStatus } from "../../hooks/useFocusStatus";
import { invalidateFocusStatusBus } from "../../lib/focusStatusBus";
import { dueBibleSlot } from "../../lib/dayGate";
import { MORNING_UPDATED_EVENT } from "./ConfirmPlanButton";
import DayGateStrip from "./DayGateStrip";

function routeBlob(pathname: string, search: string, hash: string): string {
  return `${pathname || ""}${search || ""}${hash || ""}`.toLowerCase();
}

/**
 * Due Bible slot holds the shell on /bible (morning; afternoon 12:00; evening 17:00).
 * SoftLand ≠ Arm. Day path: Bible → Plan → Apply/Confirm.
 */
export default function MorningBibleOverlay() {
  const focus = isFocusDesktopShell();
  const bridge = isFocusEnforcerBridgeAvailable();
  const status = useFocusStatus();
  const location = useLocation();
  const navigate = useNavigate();

  useEffect(() => {
    if (!focus) return;
    // Mirrors-first. Forced pipe probes during Bible reading queued behind mark-done
    // and timed out → false "Enforcer down" flicker.
    const kick = () => invalidateFocusStatusBus({ pipe: false });
    kick();
    const onMorning = () => invalidateFocusStatusBus({ pipe: true });
    window.addEventListener(MORNING_UPDATED_EVENT, onMorning);
    const id = window.setInterval(kick, 15_000);
    return () => {
      window.removeEventListener(MORNING_UPDATED_EVENT, onMorning);
      window.clearInterval(id);
    };
  }, [focus]);

  const blob = routeBlob(location.pathname, location.search, location.hash);
  const onBible = blob.includes("/bible") || blob.includes("#/bible");
  const slot =
    focus &&
    bridge &&
    !status.dayLoop?.bedtime_active &&
    Boolean(status.dayLoop || status.softland?.goals)
      ? dueBibleSlot(status)
      : null;

  useEffect(() => {
    if (!slot) return;
    const want = `slot=${slot}`;
    if (onBible && blob.includes(want)) return;
    navigate(`/bible?slot=${slot}`, { replace: true });
  }, [slot, onBible, blob, navigate]);

  if (!slot) return null;
  return <DayGateStrip />;
}
