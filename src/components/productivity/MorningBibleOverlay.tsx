import { useEffect } from "react";
import { useLocation, useNavigate } from "react-router";
import { isFocusDesktopShell } from "../../utils/focusDesktopShell";
import { isFocusEnforcerBridgeAvailable } from "../../lib/enforcerNativeCmd";
import { useFocusStatus } from "../../hooks/useFocusStatus";
import { invalidateFocusStatusBus } from "../../lib/focusStatusBus";
import { bibleDoneToday } from "../../lib/dayGate";
import { MORNING_UPDATED_EVENT } from "./ConfirmPlanButton";
import DayGateStrip from "./DayGateStrip";

/**
 * Morning Bible: compact DayGateStrip — do not trap Plan/Calendar/Home.
 * SoftLand host gate still blocks distraction sites until chapter is marked done.
 * SoftLand ≠ Arm.
 */
export default function MorningBibleOverlay() {
  const focus = isFocusDesktopShell();
  const bridge = isFocusEnforcerBridgeAvailable();
  const status = useFocusStatus();
  const location = useLocation();
  const navigate = useNavigate();

  useEffect(() => {
    if (!focus) return;
    const kickPipe = () => invalidateFocusStatusBus({ pipe: true });
    kickPipe();
    const onMorning = () => kickPipe();
    window.addEventListener(MORNING_UPDATED_EVENT, onMorning);
    const id = window.setInterval(() => invalidateFocusStatusBus({ pipe: false }), 12_000);
    return () => {
      window.removeEventListener(MORNING_UPDATED_EVENT, onMorning);
      window.clearInterval(id);
    };
  }, [focus]);

  const path = (location.pathname || "").toLowerCase();
  const onBible = path.includes("bible");
  const blocking =
    focus &&
    bridge &&
    !status.dayLoop?.bedtime_active &&
    Boolean(status.dayLoop || status.softland?.goals) &&
    !bibleDoneToday(status);

  // First open of the day on Home only — nudge to Bible once, never yank Plan/Calendar away.
  useEffect(() => {
    if (!blocking || onBible) return;
    const onPlan =
      path.includes("tab=plan") ||
      path.includes("/calendar") ||
      path.includes("tab=calendar") ||
      path.includes("/journal") ||
      path.includes("/life") ||
      path.includes("/nutrition") ||
      path.includes("/settings");
    if (onPlan) return;
    const key = `calt:bible-nudge:${new Date().toISOString().slice(0, 10)}`;
    try {
      if (sessionStorage.getItem(key)) return;
      sessionStorage.setItem(key, "1");
    } catch {
      /* ignore */
    }
    if (path === "/" || path.includes("/productivity")) {
      navigate("/bible", { replace: true });
    }
  }, [blocking, onBible, navigate, path]);

  if (!blocking || onBible) return null;

  return <DayGateStrip />;
}
