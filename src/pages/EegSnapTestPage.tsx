import { Esp32LedPlay } from "../components/hardware/Esp32LedPlay";
import { Esp32SnapCheck } from "../components/hardware/Esp32SnapCheck";
import { EegDashboardWidget } from "../components/dashboard/EegDashboardWidget";

/** Simple EEG bring-up — LED play over USB first, optional UDP snap later. */
export function EegSnapTestPage() {
  return (
    <div className="mx-auto max-w-2xl space-y-6 p-6">
      <div className="space-y-1">
        <h1 className="text-xl font-semibold text-foreground">EEG / ESP32</h1>
        <p className="text-sm text-muted-foreground">
          Play with the board LED from this page (USB). WiFi snaps are optional next.
        </p>
      </div>
      <Esp32LedPlay />
      <Esp32SnapCheck />
      <div className="gloss-panel rounded-xl border border-white/10 p-4 space-y-2">
        <p className="text-xs font-medium text-foreground">Bands (when UDP streaming)</p>
        <EegDashboardWidget />
      </div>
    </div>
  );
}
