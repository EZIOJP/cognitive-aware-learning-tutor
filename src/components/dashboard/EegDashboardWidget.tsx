import { Activity } from "lucide-react";
import { useStudySession } from "../../context/StudySessionContext";
import { usePlugins } from "../../plugins/registry";

/** Shown on home dashboard when EEG plugin is enabled. */
export function EegDashboardWidget() {
  const { biometricData, cognitiveLoad, isConnected } = useStudySession();
  const { enabledIds } = usePlugins();
  const latest = biometricData[biometricData.length - 1];

  if (!enabledIds.includes("eeg")) {
    return <p className="text-xs text-muted-foreground">Enable the EEG plugin in Settings.</p>;
  }

  if (!isConnected) {
    return (
      <p className="text-xs text-muted-foreground">
        Starting simulation… No ESP32 needed. After you buy boards, set{" "}
        <code className="text-[10px]">EEG_ENABLED=1</code> — see docs/firmware/EEG_ESP32.md.
      </p>
    );
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 text-xs text-emerald-400">
        <Activity className="w-3.5 h-3.5" />
        <span>Live · load: {cognitiveLoad}</span>
      </div>
      <div className="flex gap-3 font-mono text-sm">
        <span className="text-blue-400">α {latest?.alpha.toFixed(0) ?? "—"}</span>
        <span className="text-green-400">β {latest?.beta.toFixed(0) ?? "—"}</span>
        <span className="text-red-400">γ {latest?.gamma.toFixed(0) ?? "—"}</span>
      </div>
      <p className="text-[10px] text-muted-foreground">Feeds math tutor hints when load is high.</p>
    </div>
  );
}
