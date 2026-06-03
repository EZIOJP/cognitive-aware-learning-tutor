import { Wifi, WifiOff, Activity } from "lucide-react";
import { Badge } from "./ui/badge";

interface ConnectionStatusProps {
  isConnected: boolean;
  deviceName?: string;
  sampleRate?: number;
}

export function ConnectionStatus({
  isConnected,
  deviceName = "ESP32-S3",
  sampleRate = 250,
}: ConnectionStatusProps) {
  return (
    <div className="flex items-center gap-3 p-3 border rounded-lg bg-card">
      {isConnected ? (
        <>
          <Wifi className="w-5 h-5 text-green-600" />
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium">{deviceName} Connected</span>
              <Badge variant="secondary" className="bg-green-100 dark:bg-green-900 text-green-700 dark:text-green-300">
                <Activity className="w-3 h-3 mr-1" />
                {sampleRate}Hz
              </Badge>
            </div>
            <div className="text-xs text-muted-foreground">
              Receiving EEG data via UDP
            </div>
          </div>
        </>
      ) : (
        <>
          <WifiOff className="w-5 h-5 text-red-600" />
          <div className="flex-1">
            <div className="text-sm font-medium text-red-600">Disconnected</div>
            <div className="text-xs text-muted-foreground">
              Waiting for {deviceName}...
            </div>
          </div>
        </>
      )}
    </div>
  );
}
