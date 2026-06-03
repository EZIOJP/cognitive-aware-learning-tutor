import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from "recharts";
import { TrendingUp, AlertTriangle, CheckCircle, Brain } from "lucide-react";
import { Button } from "./ui/button";
import { Card } from "./ui/card";
import { Badge } from "./ui/badge";

interface StressPoint {
  concept: string;
  stressLevel: number;
  timestamp: string;
}

interface SessionSummary {
  duration: number;
  totalProblems: number;
  interventions: number;
  stressPoints: StressPoint[];
  overallPerformance: "excellent" | "good" | "needs-improvement";
}

interface PostSessionDiagnosticsProps {
  summary: SessionSummary;
  onClose: () => void;
  onNewSession: () => void;
}

export function PostSessionDiagnostics({
  summary,
  onClose,
  onNewSession,
}: PostSessionDiagnosticsProps) {
  const chartData = summary.stressPoints.map((point) => ({
    name: point.concept,
    stress: point.stressLevel,
  }));

  const getPerformanceIcon = () => {
    switch (summary.overallPerformance) {
      case "excellent":
        return <CheckCircle className="w-5 h-5 text-green-600" />;
      case "good":
        return <TrendingUp className="w-5 h-5 text-blue-600" />;
      case "needs-improvement":
        return <AlertTriangle className="w-5 h-5 text-amber-600" />;
    }
  };

  const getPerformanceBadge = () => {
    switch (summary.overallPerformance) {
      case "excellent":
        return <Badge className="bg-green-600">Excellent</Badge>;
      case "good":
        return <Badge className="bg-blue-600">Good</Badge>;
      case "needs-improvement":
        return <Badge className="bg-amber-600">Needs Improvement</Badge>;
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <Card className="w-full max-w-4xl max-h-[90vh] overflow-y-auto p-6">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <div className="p-3 bg-primary/10 rounded-full">
              <Brain className="w-6 h-6" />
            </div>
            <div>
              <h2>Session Complete!</h2>
              <p className="text-sm text-muted-foreground">
                Great work on this study session
              </p>
            </div>
          </div>
          {getPerformanceBadge()}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          <Card className="p-4">
            <div className="text-sm text-muted-foreground mb-1">Duration</div>
            <div className="text-2xl font-bold">{Math.floor(summary.duration / 60)} min</div>
          </Card>

          <Card className="p-4">
            <div className="text-sm text-muted-foreground mb-1">AI Interventions</div>
            <div className="text-2xl font-bold">{summary.interventions}</div>
          </Card>

          <Card className="p-4">
            <div className="text-sm text-muted-foreground mb-1">Overall Performance</div>
            <div className="flex items-center gap-2 mt-1">
              {getPerformanceIcon()}
              <span className="text-lg font-medium capitalize">
                {summary.overallPerformance.replace("-", " ")}
              </span>
            </div>
          </Card>
        </div>

        <Card className="p-6 mb-6">
          <h3 className="mb-4">Cognitive Load by Concept</h3>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
              <XAxis dataKey="name" angle={-45} textAnchor="end" height={80} />
              <YAxis label={{ value: "Stress Level", angle: -90, position: "insideLeft" }} />
              <Tooltip />
              <Bar dataKey="stress" radius={[8, 8, 0, 0]}>
                {chartData.map((entry, index) => (
                  <Cell
                    key={`cell-${index}`}
                    fill={
                      entry.stress > 80
                        ? "#ef4444"
                        : entry.stress > 50
                        ? "#f59e0b"
                        : "#22c55e"
                    }
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Card>

        <Card className="p-6 mb-6 bg-blue-50 dark:bg-blue-950 border-blue-200 dark:border-blue-800">
          <h3 className="mb-3 flex items-center gap-2">
            <Lightbulb className="w-5 h-5 text-blue-600" />
            Recommendations for Next Session
          </h3>
          <ul className="space-y-2 text-sm">
            {summary.stressPoints
              .filter((p) => p.stressLevel > 70)
              .map((point, idx) => (
                <li key={idx} className="flex items-start gap-2">
                  <span className="text-blue-600 mt-0.5">•</span>
                  <span>
                    Review <span className="font-medium">{point.concept}</span> - you showed
                    high cognitive load here. Consider breaking this down into smaller steps.
                  </span>
                </li>
              ))}
            {summary.interventions > 5 && (
              <li className="flex items-start gap-2">
                <span className="text-blue-600 mt-0.5">•</span>
                <span>
                  Take more frequent breaks - {summary.interventions} interventions suggests
                  you might benefit from shorter, more focused sessions.
                </span>
              </li>
            )}
            <li className="flex items-start gap-2">
              <span className="text-blue-600 mt-0.5">•</span>
              <span>
                Your focus was strongest in the first 15 minutes. Consider using that
                pattern for tackling difficult concepts.
              </span>
            </li>
          </ul>
        </Card>

        <div className="flex justify-end gap-3">
          <Button onClick={onClose} variant="outline">
            Close
          </Button>
          <Button onClick={onNewSession}>Start New Session</Button>
        </div>
      </Card>
    </div>
  );
}

function Lightbulb({ className }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      <path d="M15 14c.2-1 .7-1.7 1.5-2.5 1-.9 1.5-2.2 1.5-3.5A6 6 0 0 0 6 8c0 1 .2 2.2 1.5 3.5.7.7 1.3 1.5 1.5 2.5" />
      <path d="M9 18h6" />
      <path d="M10 22h4" />
    </svg>
  );
}
