import { useEffect, useState } from "react";
import {
  getFocusStatusSnapshot,
  subscribeFocusStatus,
  type FocusStatusSnapshot,
} from "../lib/focusStatusBus";

/** React binding to the shared Focus status bus (Phase A). */
export function useFocusStatus(): FocusStatusSnapshot {
  const [snap, setSnap] = useState<FocusStatusSnapshot>(() => getFocusStatusSnapshot());
  useEffect(() => subscribeFocusStatus(setSnap), []);
  return snap;
}
