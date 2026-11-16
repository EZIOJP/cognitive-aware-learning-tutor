import { useEffect, useState } from "react";
import {
  getFocusStatusSnapshot,
  isFreeDay,
  subscribeFocusStatus,
  type FocusStatusSnapshot,
} from "../lib/focusStatusBus";

/** React binding to the shared Focus status bus (Phase A). */
export function useFocusStatus(): FocusStatusSnapshot {
  const [snap, setSnap] = useState<FocusStatusSnapshot>(() => getFocusStatusSnapshot());
  useEffect(() => subscribeFocusStatus(setSnap), []);
  return snap;
}

/** True on a claimed free day or day pass. Gates Arm / SoftLand list surgery. */
export function useFreeDay(): boolean {
  const snap = useFocusStatus();
  return isFreeDay(snap.softland);
}
