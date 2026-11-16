import { useEffect, useRef } from "react";
import {
  loadEmailReportPrefs,
  markEmailReportSentToday,
  sendEmailReportNow,
  shouldAutoSendEmailReport,
} from "../lib/focusEmailReport";
import { isFocusDesktopShell } from "../utils/focusDesktopShell";

/**
 * While Focus is open, fire the daily email report once in the send-time window.
 */
export function useEmailDailyReport(enabled = true): void {
  const sending = useRef(false);

  useEffect(() => {
    if (!enabled || !isFocusDesktopShell()) return;

    const tick = async () => {
      if (sending.current) return;
      const prefs = loadEmailReportPrefs();
      if (!shouldAutoSendEmailReport(prefs)) return;
      sending.current = true;
      try {
        const r = await sendEmailReportNow(prefs);
        if (r.ok) markEmailReportSentToday();
      } finally {
        sending.current = false;
      }
    };

    void tick();
    const id = window.setInterval(() => void tick(), 60_000);
    return () => window.clearInterval(id);
  }, [enabled]);
}
