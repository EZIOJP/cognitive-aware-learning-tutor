/**
 * Applies Game Sleeper across the Focus shell (status bus + document flag).
 * BodyCareVisionHost / BodyCareRuntime subscribe separately.
 */
import { useEffect } from "react";
import {
  loadFocusSleeper,
  subscribeFocusSleeper,
} from "../../lib/focusSleeper";
import { setFocusStatusSleeper } from "../../lib/focusStatusBus";

export function FocusSleeperRuntime() {
  useEffect(() => {
    const apply = (active: boolean) => {
      setFocusStatusSleeper(active);
      try {
        document.documentElement.dataset.focusSleeper = active ? "1" : "0";
      } catch {
        /* ignore */
      }
    };
    apply(loadFocusSleeper().active);
    return subscribeFocusSleeper((s) => apply(s.active));
  }, []);

  return null;
}

export default FocusSleeperRuntime;
