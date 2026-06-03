import { useEffect, useState } from "react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from "recharts";
import { Brain, Activity } from "lucide-react";
import { Card } from "./ui/card";
import { Badge } from "./ui/badge";
import {
  COGNITIVE_LOAD_BADGE,
  COGNITIVE_LOAD_PERCENT,
} from "../../lib/cognitiveLoadDisplay";

interface BiometricData {
  alpha: number;
  beta: number;
  gamma: number;
  timestamp: number;
}

interface BiometricMonitorProps {
  data: BiometricData[];
  cognitiveLoad: "low" | "medium" | "high";
}

export function BiometricMonitor({ data, cognitiveLoad }: BiometricMonitorProps) {
  const [chartData, setChartData] = useState<any[]>([]);

  useEffect(() => {
    const formattedData = data.slice(-30).map((d, idx) => ({
      time: idx,
      Alpha: d.alpha.toFixed(2),
      Beta: d.beta.toFixed(2),
      Gamma: d.gamma.toFixed(2),
    }));
    setChartData(formattedData);
  }, [data]);

  const latestData = data[data.length - 1];

  const getCognitiveLoadColor = () => {
    switch (cognitiveLoad) {
      case "low":
        return "bg-green-500";
      case "medium":
        return "bg-yellow-500";
      case "high":
        return "bg-red-500";
      default:
        return "bg-gray-500";
    }
  };

  const getCognitiveLoadBadgeVariant = () => {
    switch (cognitiveLoad) {
      case "high":
        return "destructive";
      default:
        return "secondary";
    }
  };

  return (
    <div className="flex flex-col gap-4 h-full">
      <Card className="p-4">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Brain className="w-5 h-5" />
            <h3>Brainwave Activity</h3>
          </div>
          <div className="flex items-center gap-2">
            <Activity className="w-4 h-4" />
            <Badge
              variant={getCognitiveLoadBadgeVariant()}
              className="min-w-[4.75rem] justify-center font-mono tabular-nums shrink-0"
            >
              {COGNITIVE_LOAD_BADGE[cognitiveLoad]}
            </Badge>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-4 mb-4">
          <div className="flex flex-col items-center p-3 bg-blue-50 dark:bg-blue-950 rounded-lg">
            <div className="text-xs text-muted-foreground mb-1">Alpha (Relaxed)</div>
            <div className="text-2xl font-bold text-blue-600 dark:text-blue-400">
              {latestData?.alpha.toFixed(1) || "0.0"}
            </div>
            <div className="text-xs text-muted-foreground">Hz</div>
          </div>

          <div className="flex flex-col items-center p-3 bg-green-50 dark:bg-green-950 rounded-lg">
            <div className="text-xs text-muted-foreground mb-1">Beta (Focused)</div>
            <div className="text-2xl font-bold text-green-600 dark:text-green-400">
              {latestData?.beta.toFixed(1) || "0.0"}
            </div>
            <div className="text-xs text-muted-foreground">Hz</div>
          </div>

          <div className="flex flex-col items-center p-3 bg-red-50 dark:bg-red-950 rounded-lg">
            <div className="text-xs text-muted-foreground mb-1">Gamma (Stressed)</div>
            <div className="text-2xl font-bold text-red-600 dark:text-red-400">
              {latestData?.gamma.toFixed(1) || "0.0"}
            </div>
            <div className="text-xs text-muted-foreground">Hz</div>
          </div>
        </div>

        <ResponsiveContainer width="100%" height={200}>
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
            <XAxis dataKey="time" hide />
            <YAxis domain={[0, 100]} />
            <Tooltip />
            <Legend />
            <Line type="monotone" dataKey="Alpha" stroke="#3b82f6" strokeWidth={2} dot={false} />
            <Line type="monotone" dataKey="Beta" stroke="#22c55e" strokeWidth={2} dot={false} />
            <Line type="monotone" dataKey="Gamma" stroke="#ef4444" strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </Card>

      <Card className="p-4">
        <div className="flex items-center gap-2 mb-3">
          <div className={`w-3 h-3 rounded-full ${getCognitiveLoadColor()}`}></div>
          <h4>Cognitive Load Status</h4>
        </div>
        <div className="space-y-2">
          <div className="flex justify-between text-sm">
            <span className="text-muted-foreground">Overall Load:</span>
            <span className="font-medium font-mono tabular-nums w-10 text-right shrink-0">
              {COGNITIVE_LOAD_PERCENT[cognitiveLoad]}
            </span>
          </div>
          <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
            <div
              className={`h-2 rounded-full transition-[width] duration-300 ${getCognitiveLoadColor()}`}
              style={{ width: COGNITIVE_LOAD_PERCENT[cognitiveLoad] }}
            ></div>
          </div>
        </div>
      </Card>
    </div>
  );
}
