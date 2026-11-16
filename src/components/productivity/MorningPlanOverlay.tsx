import { useEffect } from "react";
import { useLocation, useNavigate } from "react-router";
import { isFocusDesktopShell } from "../../utils/focusDesktopShell";
import { useFocusStatus } from "../../hooks/useFocusStatus";
import { invalidateFocusStatusBus } from "../../lib/focusStatusBus";
import { dueBibleSlot, planConfirmedToday } from "../../lib/dayGate";
import { MORNING_UPDATED_EVENT } from "./ConfirmPlanButton";
import DayGateStrip from "./DayGateStrip";

function routeBlob(pathname: string, search: string, hash: string): string {
  return `${pathname || ""}${search || ""}${hash || ""}`.toLowerCase();
}

/**
 * After the due Bible slot: stay on the plan until it is confirmed.
 * Settings / Home / other tabs cannot stay open — use Planning prefs sheet on Plan.
 * SoftLand ≠ Arm. Day path: Bible → Plan → Apply/Confirm.
 */
export default function MorningPlanOverlay() {
  const focus = isFocusDesktopShell();
  const status = useFocusStatus();
  const location = useLocation();
  const navigate = useNavigate();

  useEffect(() => {
    if (!focus) return;
    const kick = () => invalidateFocusStatusBus({ pipe: false });
    kick();
    // After Confirm / plan writes — one pipe reconcile is enough (not a poll loop).
    const onMorning = () => invalidateFocusStatusBus({ pipe: true });
    window.addEventListener(MORNING_UPDATED_EVENT, onMorning);
    return () => window.removeEventListener(MORNING_UPDATED_EVENT, onMorning);
  }, [focus]);

  const blob = routeBlob(location.pathname, location.search, location.hash);
  const onPlan = blob.includes("tab=plan");
  const blocking =
    focus &&
    !status.dayLoop?.bedtime_active &&
    Boolean(status.dayLoop || status.softland?.goals) &&
    !dueBibleSlot(status) &&
    !planConfirmedToday(status);

  useEffect(() => {
    if (!blocking || onPlan) return;
    navigate("/productivity?tab=plan", { replace: true });
  }, [blocking, onPlan, navigate, blob]);

  if (!blocking) return null;
  return <DayGateStrip />;
}
